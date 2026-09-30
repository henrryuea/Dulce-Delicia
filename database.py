"""Persistencia, catálogos y archivos de Dulce Delicia."""

import os
import re
import sqlite3
from uuid import uuid4
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'dulce_delicia.db')
PRODUCT_IMAGE_DIR = os.path.join(BASE_DIR, 'static', 'img', 'productos')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
USE_POSTGRES = bool(DATABASE_URL)
DB_PATH = os.path.abspath(os.environ.get('SQLITE_DATABASE_PATH', DB_PATH))
INTEGRITY_ERRORS = (sqlite3.IntegrityError,)
if USE_POSTGRES:
    from psycopg import IntegrityError as PostgresIntegrityError
    INTEGRITY_ERRORS = (sqlite3.IntegrityError, PostgresIntegrityError)


class HybridRow(dict):
    """Fila con acceso por nombre e índice para mantener ambos drivers compatibles."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class CursorAdapter:
    def __init__(self, cursor, postgres=False):
        self._cursor = cursor
        self._postgres = postgres

    def execute(self, statement, parameters=()):
        if self._postgres:
            statement = statement.replace('?', '%s')
        self._cursor.execute(statement, parameters)
        return self

    def executemany(self, statement, parameters):
        if self._postgres:
            statement = statement.replace('?', '%s')
        self._cursor.executemany(statement, parameters)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if self._postgres and row is not None:
            return HybridRow(row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._postgres:
            return [HybridRow(row) for row in rows]
        return rows

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def rowcount(self):
        return self._cursor.rowcount


class ConnectionAdapter:
    def __init__(self, connection, postgres=False):
        self._connection = connection
        self._postgres = postgres

    def cursor(self):
        if self._postgres:
            from psycopg.rows import dict_row
            cursor = self._connection.cursor(row_factory=dict_row)
        else:
            cursor = self._connection.cursor()
        return CursorAdapter(cursor, self._postgres)

    def execute(self, statement, parameters=()):
        return self.cursor().execute(statement, parameters)

    def executemany(self, statement, parameters):
        return self.cursor().executemany(statement, parameters)

    def executescript(self, script):
        if not self._postgres:
            return self._connection.executescript(script)
        for statement in script.split(';'):
            if statement.strip():
                self.execute(statement)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc_value, _traceback):
        del _exc_value, _traceback
        if exc_type:
            self.rollback()
        self.close()


def obtener_conexion():
    if USE_POSTGRES:
        import psycopg
        database_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        return ConnectionAdapter(psycopg.connect(database_url, connect_timeout=10), postgres=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return ConnectionAdapter(conn)


def _schema_para_postgres(schema):
    schema = schema.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY')
    schema = schema.replace('INTEGER PRIMARY KEY', 'BIGSERIAL PRIMARY KEY')
    schema = re.sub(r'\bINTEGER NOT NULL REFERENCES\b', 'BIGINT NOT NULL REFERENCES', schema)
    schema = re.sub(r'\bINTEGER REFERENCES\b', 'BIGINT REFERENCES', schema)
    schema = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', schema)
    schema = schema.replace("datetime('now', 'localtime')", 'CURRENT_TIMESTAMP::text')
    schema = schema.replace('CREATE VIEW IF NOT EXISTS', 'CREATE OR REPLACE VIEW')
    return schema


def guardar_imagen_producto(archivo):
    """Guarda una imagen local y devuelve la ruta que se almacena en la base de datos."""
    if not archivo or not archivo.filename:
        return None

    nombre = secure_filename(archivo.filename)
    extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    if not nombre or extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('La imagen debe ser PNG, JPG, JPEG, WEBP o GIF.')

    os.makedirs(PRODUCT_IMAGE_DIR, exist_ok=True)
    nombre_final = f'{uuid4().hex[:12]}_{nombre}'
    archivo.save(os.path.join(PRODUCT_IMAGE_DIR, nombre_final))
    return f'img/productos/{nombre_final}'


def obtener_imagenes_producto():
    """Devuelve las imágenes disponibles para reutilizar en el catálogo."""
    imagenes = [
        ('img/CHEESCAKE.png', 'Cheesecake'),
        ('img/TARTADEFRUTA.png', 'Tarta de frutas'),
        ('img/MOUSSE.png', 'Mousse de chocolate'),
        ('img/DULCEDELICIA.png', 'Especialidad Dulce Delicia')
    ]
    if os.path.isdir(PRODUCT_IMAGE_DIR):
        for nombre in sorted(os.listdir(PRODUCT_IMAGE_DIR)):
            extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
            if extension in ALLOWED_IMAGE_EXTENSIONS:
                imagenes.append((f'img/productos/{nombre}', nombre))
    return imagenes


def _migrar_tipos_numericos_postgres(conn):
    tipos_objetivo = {
        'productos': {
            'precio_venta': (12, 2),
            'costo_referencial': (12, 2),
            'stock_actual': (12, 3),
            'stock_minimo': (12, 3),
        },
        'facturas': {'subtotal': (12, 2), 'iva': (12, 2), 'total': (12, 2)},
        'detalle_factura': {
            'cantidad': (12, 3),
            'precio_unitario': (12, 2),
            'descuento': (12, 2),
            'subtotal': (12, 2),
        },
    }
    cambios = {}
    for tabla, columnas_objetivo in tipos_objetivo.items():
        existentes = {
            row['column_name']: row
            for row in conn.execute('''
                SELECT column_name, data_type, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = ?
            ''', (tabla,)).fetchall()
        }
        for columna, (precision, escala) in columnas_objetivo.items():
            actual = existentes[columna]
            if (
                actual['data_type'] != 'numeric'
                or actual['numeric_precision'] != precision
                or actual['numeric_scale'] != escala
            ):
                cambios.setdefault(tabla, []).append((columna, escala, precision))

    if not cambios:
        return

    for vista in (
        'vw_ventas_por_producto',
        'vw_facturas_detalladas',
        'vw_productos_stock_bajo',
    ):
        conn.execute(f'DROP VIEW IF EXISTS {vista}')
    for tabla, columnas in cambios.items():
        cambios_columna = ', '.join(
            f'ALTER COLUMN {columna} TYPE NUMERIC({precision}, {escala}) '
            f'USING ROUND({columna}::numeric, {escala})'
            for columna, escala, precision in columnas
        )
        conn.execute(f'ALTER TABLE {tabla} {cambios_columna}')

    conn.execute('''
        CREATE OR REPLACE VIEW vw_productos_stock_bajo AS
            SELECT p.id_producto, p.codigo, p.nombre, cp.nombre AS categoria,
                   p.stock_actual, p.stock_minimo, u.abreviatura AS unidad
            FROM productos p
            JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
            JOIN unidades_medida u ON u.id_unidad = p.id_unidad
            WHERE p.activo = 1 AND p.stock_actual <= p.stock_minimo
    ''')
    conn.execute('''
        CREATE OR REPLACE VIEW vw_facturas_detalladas AS
            SELECT f.id_factura, f.numero, f.fecha_emision, c.nombre AS cliente,
                   c.cedula_ruc, mp.nombre AS metodo_pago, ef.nombre AS estado,
                   f.subtotal, f.iva, f.total, f.observaciones
            FROM facturas f
            JOIN clientes c ON c.id_cliente = f.id_cliente
            JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
            JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
    ''')
    conn.execute('''
        CREATE OR REPLACE VIEW vw_ventas_por_producto AS
            SELECT p.id_producto, p.codigo, p.nombre, cp.nombre AS categoria,
                   COALESCE(SUM(CASE WHEN ef.nombre = 'EMITIDA' THEN df.cantidad ELSE 0 END), 0) AS unidades_vendidas,
                   COALESCE(SUM(CASE WHEN ef.nombre = 'EMITIDA' THEN df.subtotal ELSE 0 END), 0) AS ventas
            FROM productos p
            JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
            LEFT JOIN detalle_factura df ON df.id_producto = p.id_producto
            LEFT JOIN facturas f ON f.id_factura = df.id_factura
            LEFT JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
            GROUP BY p.id_producto, p.codigo, p.nombre, cp.nombre
    ''')


def _asegurar_integridad_roles(conn):
    if USE_POSTGRES:
        restricciones = {
            'usuarios_rol_check': "CHECK (rol IN ('ADMIN', 'STAFF', 'CLIENTE'))",
            'usuarios_estado_check': "CHECK (estado IN ('PENDIENTE', 'ACTIVO', 'RECHAZADO'))",
            'usuarios_rol_cliente_check': (
                "CHECK ((rol = 'CLIENTE' AND id_cliente IS NOT NULL) "
                "OR (rol IN ('ADMIN', 'STAFF') AND id_cliente IS NULL))"
            ),
        }
        for nombre, expresion in restricciones.items():
            existe = conn.execute(
                "SELECT 1 FROM pg_constraint WHERE conrelid = 'usuarios'::regclass "
                'AND conname = ?',
                (nombre,)
            ).fetchone()
            if not existe:
                conn.execute(
                    f'ALTER TABLE usuarios ADD CONSTRAINT {nombre} {expresion}'
                )
        return

    condicion_invalida = '''
        NEW.rol NOT IN ('ADMIN', 'STAFF', 'CLIENTE')
        OR NEW.estado NOT IN ('PENDIENTE', 'ACTIVO', 'RECHAZADO')
        OR (NEW.rol = 'CLIENTE' AND NEW.id_cliente IS NULL)
        OR (NEW.rol IN ('ADMIN', 'STAFF') AND NEW.id_cliente IS NOT NULL)
    '''
    for operacion in ('INSERT', 'UPDATE'):
        nombre = f'trg_usuarios_roles_{operacion.lower()}'
        conn.execute(f'''
            CREATE TRIGGER IF NOT EXISTS {nombre}
            BEFORE {operacion} ON usuarios
            FOR EACH ROW
            WHEN {condicion_invalida}
            BEGIN
                SELECT RAISE(ABORT, 'Invalid account role, status, or customer link');
            END
        ''')


def inicializar_base_datos():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = obtener_conexion()
    if USE_POSTGRES:
        conn.execute('SELECT pg_advisory_xact_lock(731904215)')
    else:
        conn.execute('BEGIN IMMEDIATE')
    schema = '''
        CREATE TABLE IF NOT EXISTS tipos_cliente (
            id_tipo_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
        CREATE TABLE IF NOT EXISTS categorias_producto (
            id_categoria_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS unidades_medida (
            id_unidad INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            abreviatura TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS categorias_proveedor (
            id_categoria_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
        CREATE TABLE IF NOT EXISTS estados_proveedor (
            id_estado_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
        CREATE TABLE IF NOT EXISTS estados_factura (
            id_estado_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
        CREATE TABLE IF NOT EXISTS metodos_pago (
            id_metodo_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS tipos_movimiento_inventario (
            id_tipo_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            naturaleza TEXT NOT NULL CHECK (naturaleza IN ('E', 'S')),
            descripcion TEXT
        );
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            id_tipo_cliente INTEGER NOT NULL REFERENCES tipos_cliente(id_tipo_cliente),
            nombre TEXT NOT NULL,
            cedula_ruc TEXT UNIQUE,
            correo TEXT,
            telefono TEXT,
            direccion TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_registro TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria_proveedor INTEGER REFERENCES categorias_proveedor(id_categoria_proveedor),
            id_estado_proveedor INTEGER NOT NULL REFERENCES estados_proveedor(id_estado_proveedor),
            razon_social TEXT NOT NULL,
            ruc TEXT UNIQUE,
            contacto TEXT,
            telefono TEXT,
            correo TEXT,
            direccion TEXT,
            fecha_registro TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria_producto INTEGER NOT NULL REFERENCES categorias_producto(id_categoria_producto),
            id_unidad INTEGER NOT NULL REFERENCES unidades_medida(id_unidad),
            codigo TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio_venta NUMERIC(12, 2) NOT NULL CHECK (precio_venta >= 0),
            costo_referencial NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (costo_referencial >= 0),
            stock_actual NUMERIC(12, 3) NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
            stock_minimo NUMERIC(12, 3) NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
            imagen TEXT DEFAULT 'img/CHEESCAKE.png',
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_registro TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS pedidos (
            id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            clave_idempotencia TEXT NOT NULL,
            id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente),
            fecha_pedido TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
            iva NUMERIC(12, 2) NOT NULL CHECK (iva >= 0),
            total NUMERIC(12, 2) NOT NULL CHECK (total > 0),
            monto_pagado NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (monto_pagado >= 0 AND monto_pagado <= total),
            estado TEXT NOT NULL DEFAULT 'PENDIENTE'
                CHECK (estado IN ('PENDIENTE', 'PAGADO', 'ANULADO')),
            observaciones TEXT
        );
        CREATE TABLE IF NOT EXISTS detalle_pedido (
            id_detalle_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            codigo_producto TEXT,
            nombre_producto TEXT,
            cantidad NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),
            precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
            descuento NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
            subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0)
        );
        CREATE TABLE IF NOT EXISTS pagos_pedido (
            id_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
            numero_comprobante TEXT NOT NULL UNIQUE,
            clave_idempotencia TEXT NOT NULL,
            fecha_pago TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            monto NUMERIC(12, 2) NOT NULL CHECK (monto > 0),
            id_metodo_pago INTEGER NOT NULL REFERENCES metodos_pago(id_metodo_pago),
            observaciones TEXT
        );
        CREATE TABLE IF NOT EXISTS facturas (
            id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente),
            id_metodo_pago INTEGER NOT NULL REFERENCES metodos_pago(id_metodo_pago),
            id_estado_factura INTEGER NOT NULL REFERENCES estados_factura(id_estado_factura),
            fecha_emision TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
            iva NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (iva >= 0),
            total NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
            observaciones TEXT,
            id_pedido INTEGER REFERENCES pedidos(id_pedido)
        );
        CREATE TABLE IF NOT EXISTS detalle_factura (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_factura INTEGER NOT NULL REFERENCES facturas(id_factura) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            codigo_producto TEXT,
            nombre_producto TEXT,
            cantidad NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),
            precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
            descuento NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
            subtotal NUMERIC(12, 2) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS compras (
            id_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_documento TEXT NOT NULL UNIQUE,
            id_proveedor INTEGER NOT NULL REFERENCES proveedores(id_proveedor),
            fecha_compra TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            subtotal REAL NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
            iva REAL NOT NULL DEFAULT 0 CHECK (iva >= 0),
            total REAL NOT NULL DEFAULT 0 CHECK (total >= 0),
            estado TEXT NOT NULL DEFAULT 'RECIBIDA' CHECK (estado IN ('RECIBIDA', 'ANULADA')),
            observaciones TEXT
        );
        CREATE TABLE IF NOT EXISTS detalle_compra (
            id_detalle_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            id_compra INTEGER NOT NULL REFERENCES compras(id_compra) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            costo_unitario REAL NOT NULL CHECK (costo_unitario >= 0),
            subtotal REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS movimientos_inventario (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            id_tipo_movimiento INTEGER NOT NULL REFERENCES tipos_movimiento_inventario(id_tipo_movimiento),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            stock_anterior REAL NOT NULL CHECK (stock_anterior >= 0),
            stock_nuevo REAL NOT NULL CHECK (stock_nuevo >= 0),
            fecha_movimiento TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            referencia TEXT,
            observaciones TEXT
        );
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            correo TEXT UNIQUE,
            nombre TEXT,
            rol TEXT NOT NULL DEFAULT 'CLIENTE'
                CHECK (rol IN ('ADMIN', 'STAFF', 'CLIENTE')),
            estado TEXT NOT NULL DEFAULT 'PENDIENTE'
                CHECK (estado IN ('PENDIENTE', 'ACTIVO', 'RECHAZADO')),
            id_cliente BIGINT UNIQUE REFERENCES clientes(id_cliente),
            revisado_por BIGINT REFERENCES usuarios(id_usuario),
            fecha_revision TEXT,
            intentos_fallidos INTEGER NOT NULL DEFAULT 0,
            bloqueado_hasta TEXT,
            ultimo_acceso TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            CHECK (
                (rol = 'CLIENTE' AND id_cliente IS NOT NULL)
                OR (rol IN ('ADMIN', 'STAFF') AND id_cliente IS NULL)
            )
        );
        CREATE INDEX IF NOT EXISTS idx_detalle_factura_factura
            ON detalle_factura(id_factura);
        CREATE INDEX IF NOT EXISTS idx_movimientos_producto_fecha
            ON movimientos_inventario(id_producto, fecha_movimiento);
        CREATE INDEX IF NOT EXISTS idx_pedidos_estado_fecha
            ON pedidos(estado, fecha_pedido);
        CREATE INDEX IF NOT EXISTS idx_pagos_pedido_fecha
            ON pagos_pedido(id_pedido, fecha_pago);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_detalle_pedido_producto
            ON detalle_pedido(id_pedido, id_producto);
        CREATE VIEW IF NOT EXISTS vw_productos_stock_bajo AS
            SELECT p.id_producto, p.codigo, p.nombre, cp.nombre AS categoria,
                   p.stock_actual, p.stock_minimo, u.abreviatura AS unidad
            FROM productos p
            JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
            JOIN unidades_medida u ON u.id_unidad = p.id_unidad
            WHERE p.activo = 1 AND p.stock_actual <= p.stock_minimo;
        CREATE VIEW IF NOT EXISTS vw_facturas_detalladas AS
            SELECT f.id_factura, f.numero, f.fecha_emision, c.nombre AS cliente,
                   c.cedula_ruc, mp.nombre AS metodo_pago, ef.nombre AS estado,
                   f.subtotal, f.iva, f.total, f.observaciones
            FROM facturas f
            JOIN clientes c ON c.id_cliente = f.id_cliente
            JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
            JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura;
        CREATE VIEW IF NOT EXISTS vw_ventas_por_producto AS
            SELECT p.id_producto, p.codigo, p.nombre, cp.nombre AS categoria,
                   COALESCE(SUM(CASE WHEN ef.nombre = 'EMITIDA' THEN df.cantidad ELSE 0 END), 0) AS unidades_vendidas,
                   COALESCE(SUM(CASE WHEN ef.nombre = 'EMITIDA' THEN df.subtotal ELSE 0 END), 0) AS ventas
            FROM productos p
            JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
            LEFT JOIN detalle_factura df ON df.id_producto = p.id_producto
            LEFT JOIN facturas f ON f.id_factura = df.id_factura
            LEFT JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
            GROUP BY p.id_producto, p.codigo, p.nombre, cp.nombre;
    '''
    conn.executescript(_schema_para_postgres(schema) if USE_POSTGRES else schema)
    if not USE_POSTGRES:
        conn.execute('BEGIN IMMEDIATE')
    if USE_POSTGRES:
        conn.execute(
            'ALTER TABLE facturas ADD COLUMN IF NOT EXISTS '
            'id_pedido BIGINT REFERENCES pedidos(id_pedido)'
        )
        conn.execute(
            'ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS clave_idempotencia TEXT'
        )
        conn.execute(
            'ALTER TABLE pagos_pedido ADD COLUMN IF NOT EXISTS clave_idempotencia TEXT'
        )
        conn.execute('''
            ALTER TABLE usuarios
                ADD COLUMN IF NOT EXISTS correo TEXT,
                ADD COLUMN IF NOT EXISTS nombre TEXT,
                ADD COLUMN IF NOT EXISTS rol TEXT NOT NULL DEFAULT 'ADMIN',
                ADD COLUMN IF NOT EXISTS estado TEXT NOT NULL DEFAULT 'ACTIVO',
                ADD COLUMN IF NOT EXISTS id_cliente BIGINT REFERENCES clientes(id_cliente),
                ADD COLUMN IF NOT EXISTS revisado_por BIGINT REFERENCES usuarios(id_usuario),
                ADD COLUMN IF NOT EXISTS fecha_revision TEXT
        ''')
        conn.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_correo_unico
            ON usuarios(correo) WHERE correo IS NOT NULL
        ''')
        conn.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_cliente_unico
            ON usuarios(id_cliente) WHERE id_cliente IS NOT NULL
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_usuarios_rol_estado
            ON usuarios(rol, estado)
        ''')
        conn.execute(
            "ALTER TABLE usuarios ALTER COLUMN rol SET DEFAULT 'CLIENTE'"
        )
        conn.execute(
            "ALTER TABLE usuarios ALTER COLUMN estado SET DEFAULT 'PENDIENTE'"
        )
        _migrar_tipos_numericos_postgres(conn)
        for tabla in ('detalle_pedido', 'detalle_factura'):
            conn.execute(
                f'ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS codigo_producto TEXT'
            )
            conn.execute(
                f'ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS nombre_producto TEXT'
            )
    else:
        invoice_columns = conn.execute('PRAGMA table_info(facturas)').fetchall()
        invoice_order_column = next(
            (column for column in invoice_columns if column['name'] == 'id_pedido'),
            None
        )
        if not invoice_order_column:
            conn.execute(
                'ALTER TABLE facturas ADD COLUMN id_pedido INTEGER '
                'REFERENCES pedidos(id_pedido)'
            )
        for tabla in ('pedidos', 'pagos_pedido'):
            columnas = {
                column['name']
                for column in conn.execute(f'PRAGMA table_info({tabla})').fetchall()
            }
            if 'clave_idempotencia' not in columnas:
                conn.execute(
                    f'ALTER TABLE {tabla} ADD COLUMN clave_idempotencia TEXT'
                )
        columnas_usuario = {
            column['name']
            for column in conn.execute('PRAGMA table_info(usuarios)').fetchall()
        }
        if 'correo' not in columnas_usuario:
            conn.execute('ALTER TABLE usuarios ADD COLUMN correo TEXT')
        if 'nombre' not in columnas_usuario:
            conn.execute('ALTER TABLE usuarios ADD COLUMN nombre TEXT')
        if 'rol' not in columnas_usuario:
            conn.execute(
                "ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'ADMIN'"
            )
        if 'estado' not in columnas_usuario:
            conn.execute(
                "ALTER TABLE usuarios ADD COLUMN estado TEXT NOT NULL DEFAULT 'ACTIVO'"
            )
        if 'id_cliente' not in columnas_usuario:
            conn.execute(
                'ALTER TABLE usuarios ADD COLUMN id_cliente INTEGER REFERENCES clientes(id_cliente)'
            )
        if 'revisado_por' not in columnas_usuario:
            conn.execute(
                'ALTER TABLE usuarios ADD COLUMN revisado_por INTEGER REFERENCES usuarios(id_usuario)'
            )
        if 'fecha_revision' not in columnas_usuario:
            conn.execute('ALTER TABLE usuarios ADD COLUMN fecha_revision TEXT')
        conn.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_correo_unico
            ON usuarios(correo) WHERE correo IS NOT NULL
        ''')
        conn.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_cliente_unico
            ON usuarios(id_cliente) WHERE id_cliente IS NOT NULL
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_usuarios_rol_estado
            ON usuarios(rol, estado)
        ''')
        for tabla in ('detalle_pedido', 'detalle_factura'):
            columnas = {
                column['name']
                for column in conn.execute(f'PRAGMA table_info({tabla})').fetchall()
            }
            if 'codigo_producto' not in columnas:
                conn.execute(f'ALTER TABLE {tabla} ADD COLUMN codigo_producto TEXT')
            if 'nombre_producto' not in columnas:
                conn.execute(f'ALTER TABLE {tabla} ADD COLUMN nombre_producto TEXT')
    _asegurar_integridad_roles(conn)
    conn.execute('''
        UPDATE detalle_pedido
        SET codigo_producto = (SELECT codigo FROM productos WHERE productos.id_producto = detalle_pedido.id_producto),
            nombre_producto = (SELECT nombre FROM productos WHERE productos.id_producto = detalle_pedido.id_producto)
        WHERE codigo_producto IS NULL OR nombre_producto IS NULL
    ''')
    conn.execute('''
        UPDATE detalle_factura
        SET codigo_producto = (SELECT codigo FROM productos WHERE productos.id_producto = detalle_factura.id_producto),
            nombre_producto = (SELECT nombre FROM productos WHERE productos.id_producto = detalle_factura.id_producto)
        WHERE codigo_producto IS NULL OR nombre_producto IS NULL
    ''')
    conn.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_facturas_pedido_unico
        ON facturas(id_pedido) WHERE id_pedido IS NOT NULL
    ''')
    conn.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pedidos_clave_idempotencia
        ON pedidos(clave_idempotencia)
    ''')
    conn.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pagos_clave_idempotencia
        ON pagos_pedido(clave_idempotencia)
    ''')
    catalogos = {
        'tipos_cliente': [('PERSONA NATURAL', 'Cliente consumidor final o persona natural'), ('EMPRESA', 'Cliente empresarial corporativo')],
        'categorias_producto': [('TORTAS', 'Tortas y pasteles tradicionales y de autor'), ('POSTRES', 'Postres individuales y dulces finos'), ('PANADERIA', 'Productos de panadería artesanal y hojaldres'), ('BEBIDAS', 'Bebidas frías y cafetería de especialidad'), ('OTROS', 'Otros productos y complementos')],
        'unidades_medida': [('UNIDAD', 'UND'), ('KILOGRAMO', 'KG'), ('LITRO', 'L'), ('PORCION', 'POR')],
        'categorias_proveedor': [('MATERIA PRIMA', 'Harina, azúcar, huevos, lácteos y otros insumos'), ('EMPAQUES', 'Cajas, fundas, vasos y empaques ecológicos'), ('BEBIDAS', 'Proveedores de granos de café y bebidas'), ('OTROS', 'Otros proveedores de suministros')],
        'estados_proveedor': [('ACTIVO', 'Proveedor homologado y habilitado'), ('INACTIVO', 'Proveedor temporalmente no habilitado')],
        'estados_factura': [('EMITIDA', 'Factura válida y cobrada'), ('ANULADA', 'Factura anulada'), ('PENDIENTE', 'Factura pendiente de pago o confirmación')],
        'metodos_pago': [('EFECTIVO',), ('TRANSFERENCIA',), ('TARJETA',), ('DEPOSITO',)],
    }
    for tabla, valores in catalogos.items():
        if conn.execute(f'SELECT COUNT(*) FROM {tabla}').fetchone()[0] == 0:
            if tabla == 'unidades_medida':
                conn.executemany(f'INSERT INTO {tabla} (nombre, abreviatura) VALUES (?, ?)', valores)
            elif tabla == 'metodos_pago':
                conn.executemany(f'INSERT INTO {tabla} (nombre, activo) VALUES (?, 1)', valores)
            else:
                conn.executemany(f'INSERT INTO {tabla} (nombre, descripcion) VALUES (?, ?)', valores)
    conn.execute('''
        INSERT INTO metodos_pago (nombre, activo)
        SELECT 'VARIOS', 1
        WHERE NOT EXISTS (SELECT 1 FROM metodos_pago WHERE nombre = 'VARIOS')
    ''')

    if conn.execute('SELECT COUNT(*) FROM tipos_movimiento_inventario').fetchone()[0] == 0:
        conn.executemany('INSERT INTO tipos_movimiento_inventario (nombre, naturaleza, descripcion) VALUES (?, ?, ?)', [
            ('COMPRA', 'E', 'Ingreso por compra a proveedor'), ('VENTA', 'S', 'Salida por venta a cliente'),
            ('AJUSTE ENTRADA', 'E', 'Ajuste positivo de inventario'), ('AJUSTE SALIDA', 'S', 'Ajuste negativo de inventario')
        ])
    conn.execute('''
        INSERT INTO tipos_movimiento_inventario (nombre, naturaleza, descripcion)
        SELECT 'RESERVA PEDIDO', 'S', 'Stock reservado al crear un pedido pendiente'
        WHERE NOT EXISTS (
            SELECT 1 FROM tipos_movimiento_inventario WHERE nombre = 'RESERVA PEDIDO'
        )
    ''')

    if conn.execute('SELECT COUNT(*) FROM productos').fetchone()[0] == 0:
        conn.executemany('''
            INSERT INTO productos (
                id_categoria_producto, id_unidad, codigo, nombre, descripcion,
                precio_venta, costo_referencial, stock_actual, stock_minimo, imagen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (1, 1, 'TOR-001', 'Torta de chocolate fino', 'Torta de chocolate decorada con cacao fino de aroma y ganache artesanal.', 18.00, 10.00, 10.0, 3.0, 'img/MOUSSE.png'),
            (1, 1, 'TOR-002', 'Torta clásica de vainilla', 'Torta esponjosa de vainilla rellena con crema diplomática y fresas.', 16.00, 9.00, 8.0, 3.0, 'img/TARTADEFRUTA.png'),
            (2, 4, 'POS-001', 'Cheesecake clásico de frutos rojos', 'Porción cremosa de cheesecake horneado estilo New York con coulis artesanal.', 3.50, 1.80, 20.0, 5.0, 'img/CHEESCAKE.png'),
            (2, 1, 'POS-002', 'Cupcake artesanal decorado', 'Cupcake suave de autor decorado con crema chantilly y perlas comestibles.', 2.00, 0.90, 25.0, 8.0, 'img/DULCEDELICIA.png'),
            (3, 1, 'PAN-001', 'Croissant francés de mantequilla', 'Croissant hojaldrado con mantequilla pura importada de masa madre.', 1.50, 0.70, 30.0, 10.0, 'img/CHEESCAKE.png'),
            (4, 1, 'BEB-001', 'Café americano de especialidad', 'Café arábigo lojano de especialidad tostado artesanalmente.', 1.50, 0.50, 50.0, 10.0, 'img/DULCEDELICIA.png')
        ])

    if conn.execute('SELECT COUNT(*) FROM clientes').fetchone()[0] == 0:
        conn.executemany('''
            INSERT INTO clientes (id_tipo_cliente, nombre, cedula_ruc, correo, telefono, direccion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [
            (1, 'Consumidor Final', '9999999999999', 'final@dulcedelicia.ec', '0999999999', 'Quito - Ecuador'),
            (1, 'Ana Torres Mendoza', '1718293841', 'ana.torres@email.com', '0991112233', 'Av. República y Eloy Alfaro N34-12, Quito')
        ])

    if conn.execute('SELECT COUNT(*) FROM proveedores').fetchone()[0] == 0:
        conn.executemany('''
            INSERT INTO proveedores (
                id_categoria_proveedor, id_estado_proveedor, razon_social, ruc,
                contacto, telefono, correo, direccion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (1, 1, 'Lácteos Andinos Cía. Ltda.', '1791234567001', 'Ing. María León', '0224588990', 'ventas@lacteosandinos.com', 'Parque Industrial Machachi, Pichincha'),
            (1, 1, 'Frutas del Valle Ecuador', '1792345678001', 'Lic. Carlos Ruiz', '0987654321', 'pedidos@frutasdelvalle.ec', 'Valle de los Chillos, Sangolquí')
        ])

    if conn.execute('SELECT COUNT(*) FROM facturas').fetchone()[0] == 0:
        conn.executemany('''
            INSERT INTO facturas (
                numero, id_cliente, id_metodo_pago, id_estado_factura,
                fecha_emision, subtotal, iva, total, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            ('FAC-001', 2, 2, 1, '2026-08-20', 32.17, 4.83, 37.00, '2x Torta de chocolate para evento familiar.'),
            ('FAC-002', 1, 1, 1, '2026-08-22', 23.48, 3.52, 27.00, 'Cheesecake clásico y café americano.')
        ])

    tipo_entrada = conn.execute(
        "SELECT id_tipo_movimiento FROM tipos_movimiento_inventario WHERE nombre = 'AJUSTE ENTRADA'"
    ).fetchone()
    productos_sin_historial = conn.execute('''
        SELECT p.id_producto, p.codigo, p.stock_actual
        FROM productos p
        WHERE p.stock_actual > 0
          AND NOT EXISTS (
              SELECT 1 FROM movimientos_inventario m WHERE m.id_producto = p.id_producto
          )
    ''').fetchall()
    conn.executemany('''
        INSERT INTO movimientos_inventario (
            id_producto, id_tipo_movimiento, cantidad, stock_anterior,
            stock_nuevo, referencia, observaciones
        ) VALUES (?, ?, ?, 0, ?, ?, ?)
    ''', [
        (
            producto['id_producto'], tipo_entrada['id_tipo_movimiento'],
            producto['stock_actual'], producto['stock_actual'], producto['codigo'],
            'Saldo de apertura del inventario'
        )
        for producto in productos_sin_historial
    ])
    conn.commit()
    conn.close()


def sincronizar_opciones_producto(form):
    conn = obtener_conexion()
    form.id_categoria_producto.choices = [(r['id_categoria_producto'], f"🎂 {r['nombre']}") for r in conn.execute('SELECT id_categoria_producto, nombre FROM categorias_producto WHERE activo = 1 ORDER BY id_categoria_producto')]
    form.id_unidad.choices = [(r['id_unidad'], r['etiqueta']) for r in conn.execute("SELECT id_unidad, nombre || ' (' || abreviatura || ')' AS etiqueta FROM unidades_medida ORDER BY id_unidad")]
    conn.close()
    form.imagen_existente.choices = [('', 'No seleccionar una imagen existente')] + obtener_imagenes_producto()


def sincronizar_opciones_cliente(form):
    conn = obtener_conexion()
    form.id_tipo_cliente.choices = [(r['id_tipo_cliente'], f"👤 {r['nombre']}") for r in conn.execute('SELECT id_tipo_cliente, nombre FROM tipos_cliente ORDER BY id_tipo_cliente')]
    conn.close()


def sincronizar_opciones_proveedor(form):
    conn = obtener_conexion()
    form.id_categoria_proveedor.choices = [(r['id_categoria_proveedor'], f"🌾 {r['nombre']}") for r in conn.execute('SELECT id_categoria_proveedor, nombre FROM categorias_proveedor ORDER BY id_categoria_proveedor')]
    form.id_estado_proveedor.choices = [(r['id_estado_proveedor'], f"✅ {r['nombre']}") for r in conn.execute('SELECT id_estado_proveedor, nombre FROM estados_proveedor ORDER BY id_estado_proveedor')]
    conn.close()


def sincronizar_opciones_factura(form):
    conn = obtener_conexion()
    form.id_cliente.choices = [(r['id_cliente'], r['etiqueta']) for r in conn.execute("SELECT id_cliente, nombre || ' (' || COALESCE(cedula_ruc, 'S/N') || ')' AS etiqueta FROM clientes ORDER BY nombre")]
    form.id_metodo_pago.choices = [(r['id_metodo_pago'], f"💵 {r['nombre']}") for r in conn.execute('SELECT id_metodo_pago, nombre FROM metodos_pago WHERE activo = 1 ORDER BY id_metodo_pago')]
    form.id_estado_factura.choices = [(r['id_estado_factura'], f"📌 {r['nombre']}") for r in conn.execute('SELECT id_estado_factura, nombre FROM estados_factura ORDER BY id_estado_factura')]
    conn.close()


inicializar_base_datos()
