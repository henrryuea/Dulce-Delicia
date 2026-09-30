"""Persistencia, catálogos y archivos de Dulce Delicia."""

import os
import sqlite3
from uuid import uuid4
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'dulce_delicia.db')
PRODUCT_IMAGE_DIR = os.path.join(BASE_DIR, 'static', 'img', 'productos')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def obtener_conexion():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def guardar_imagen_producto(archivo):
    """Guarda una imagen local y devuelve la ruta que se almacena en SQLite."""
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


def inicializar_base_datos():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = obtener_conexion()
    conn.executescript('''
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
            precio_venta REAL NOT NULL CHECK (precio_venta >= 0),
            costo_referencial REAL NOT NULL DEFAULT 0 CHECK (costo_referencial >= 0),
            stock_actual REAL NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
            stock_minimo REAL NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
            imagen TEXT DEFAULT 'img/CHEESCAKE.png',
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_registro TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE TABLE IF NOT EXISTS facturas (
            id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente),
            id_metodo_pago INTEGER NOT NULL REFERENCES metodos_pago(id_metodo_pago),
            id_estado_factura INTEGER NOT NULL REFERENCES estados_factura(id_estado_factura),
            fecha_emision TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            subtotal REAL NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
            iva REAL NOT NULL DEFAULT 0 CHECK (iva >= 0),
            total REAL NOT NULL DEFAULT 0 CHECK (total >= 0),
            observaciones TEXT
        );
        CREATE TABLE IF NOT EXISTS detalle_factura (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_factura INTEGER NOT NULL REFERENCES facturas(id_factura) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
            descuento REAL NOT NULL DEFAULT 0 CHECK (descuento >= 0),
            subtotal REAL NOT NULL
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

    if conn.execute('SELECT COUNT(*) FROM tipos_movimiento_inventario').fetchone()[0] == 0:
        conn.executemany('INSERT INTO tipos_movimiento_inventario (nombre, naturaleza, descripcion) VALUES (?, ?, ?)', [
            ('COMPRA', 'E', 'Ingreso por compra a proveedor'), ('VENTA', 'S', 'Salida por venta a cliente'),
            ('AJUSTE ENTRADA', 'E', 'Ajuste positivo de inventario'), ('AJUSTE SALIDA', 'S', 'Ajuste negativo de inventario')
        ])

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
