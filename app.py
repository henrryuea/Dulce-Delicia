"""
================================================================================
PROYECTO: Dulce Delicia - Sistema de Gestión de Pastelería Artesanal
ASIGNATURA: Desarrollo de Aplicaciones Web
UNIVERSIDAD: Universidad Estatal Amazónica (UEA)
CARRERA: Tecnologías de la Información
AVANCE: Semana 12 - Proyecto Integrador U3 (12/16)
TEMA: Persistencia de datos en un entorno local con SQLite (3FN)
ESTUDIANTE: Desarrollo Web 2026
================================================================================
DESCRIPCIÓN GENERAL:
Este archivo constituye el núcleo backend del sistema web Dulce Delicia,
desarrollado en Python con el framework Flask. Integra formularios seguros con
validación del lado del servidor (Flask-WTF) y persistencia física en una base
de datos local SQLite (dulce_delicia.db), estructurada estrictamente bajo el
modelo relacional normalizado en Tercera Forma Normal (3FN).

ARQUITECTURA DEL MODELO NORMALIZADO (3FN):
  1. Catálogos base:
     - tipos_cliente (PERSONA NATURAL, EMPRESA)
     - categorias_producto (TORTAS, POSTRES, PANADERIA, BEBIDAS, OTROS)
     - unidades_medida (UNIDAD, KILOGRAMO, LITRO, PORCION)
     - categorias_proveedor (MATERIA PRIMA, EMPAQUES, BEBIDAS, OTROS)
     - estados_proveedor (ACTIVO, INACTIVO)
     - estados_factura (EMITIDA, ANULADA, PENDIENTE)
     - metodos_pago (EFECTIVO, TRANSFERENCIA, TARJETA, DEPOSITO)
     - tipos_movimiento_inventario (COMPRA, VENTA, AJUSTES)
  2. Tablas transaccionales:
     - productos (claves foráneas a categorías y unidades de medida)
     - clientes (clave foránea a tipos de cliente)
     - proveedores (claves foráneas a categorías y estados)
     - facturas y detalle_factura
     - compras y detalle_compra
     - movimientos_inventario
  3. Vistas relacionales:
     - vw_productos_stock_bajo
     - vw_facturas_detalladas
     - vw_ventas_por_producto

FLUJO DE PERSISTENCIA (CRUD DE LA SEMANA 12):
  1. Formulario Web con Token CSRF (Flask-WTF / WTForms).
  2. Validación estricta en servidor con form.validate_on_submit().
  3. Consultas SQL parametrizadas con '?' para evitar ataques de inyección SQL.
  4. Confirmación de transacciones con conn.commit().
  5. Recuperación con cursor.fetchall() y mapeo con sqlite3.Row.
  6. Renderizado dinámico en plantillas Jinja2 y Bootstrap 5.
================================================================================
"""

# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS Y MÓDULOS DE PYTHON Y FLASK
# ==============================================================================
import os                            # Operaciones del sistema de archivos y rutas
import sqlite3                       # Controlador nativo para SQLite
from datetime import date, datetime  # Manipulación de fechas para comprobantes
from functools import wraps          # Utilidad para construir decoradores en Python
from flask import (
    Flask,                           # Clase constructora de la app web
    render_template,                 # Procesamiento de plantillas HTML con Jinja2
    request,                         # Acceso a los datos de peticiones HTTP
    redirect,                        # Redireccionamiento entre vistas
    url_for,                         # Generador de rutas seguras por nombre de función
    flash,                           # Envío de notificaciones temporales al usuario
    session                          # Almacén de sesiones cifradas del navegador
)

# Importamos las clases de formularios desarrolladas en la carpeta forms/
from forms import (
    ProductoForm,                    # Formulario para postres (3FN)
    ClienteForm,                     # Formulario para clientes (3FN)
    ProveedorForm,                   # Formulario para proveedores (3FN)
    FacturacionForm,                 # Formulario para facturación (3FN)
    LoginForm                        # Formulario para autenticación administrativa
)


# ==============================================================================
# 2. INICIALIZACIÓN Y CONFIGURACIÓN DE FLASK
# ==============================================================================
app = Flask(__name__)

# Clave secreta para la firma criptográfica de sesiones y protección CSRF
app.config['SECRET_KEY'] = 'dulce-delicia-pasteleria-semana12-sqlite-uea-2026'

# Determinación de rutas absolutas para asegurar portabilidad en cualquier equipo
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'dulce_delicia.db')


# ==============================================================================
# 3. CONTROLADOR DE CONEXIÓN CON SQLITE
# ==============================================================================
def obtener_conexion():
    """
    Establece y retorna una conexión activa con el archivo SQLite local.
    
    Características:
      - Activa el soporte de claves foráneas con PRAGMA foreign_keys = ON.
      - Establece row_factory = sqlite3.Row para acceder a los campos
        por nombre de columna (ej. producto['precio_venta']).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # En SQLite las claves foráneas deben activarse explícitamente por conexión
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ==============================================================================
# 4. INICIALIZACIÓN DE LA BASE DE DATOS LOCAL NORMALIZADA (3FN)
# ==============================================================================
def inicializar_base_datos():
    """
    Crea la estructura relacional normalizada en Tercera Forma Normal (3FN)
    dentro de data/dulce_delicia.db y carga los datos de catálogo iniciales.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = obtener_conexion()
    cursor = conn.cursor()

    # --------------------------------------------------------------------------
    # A. TABLAS DE CATÁLOGOS BASE (3FN)
    # --------------------------------------------------------------------------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tipos_cliente (
            id_tipo_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias_producto (
            id_categoria_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unidades_medida (
            id_unidad INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            abreviatura TEXT NOT NULL UNIQUE
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias_proveedor (
            id_categoria_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estados_proveedor (
            id_estado_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estados_factura (
            id_estado_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metodos_pago (
            id_metodo_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tipos_movimiento_inventario (
            id_tipo_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            naturaleza TEXT NOT NULL CHECK (naturaleza IN ('E','S')),
            descripcion TEXT
        );
    ''')

    # --------------------------------------------------------------------------
    # B. TABLAS PRINCIPALES DEL SISTEMA (3FN)
    # --------------------------------------------------------------------------
    cursor.execute('''
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
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalle_factura (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_factura INTEGER NOT NULL REFERENCES facturas(id_factura) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
            descuento REAL NOT NULL DEFAULT 0 CHECK (descuento >= 0),
            subtotal REAL NOT NULL
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_documento TEXT NOT NULL UNIQUE,
            id_proveedor INTEGER NOT NULL REFERENCES proveedores(id_proveedor),
            fecha_compra TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            subtotal REAL NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
            iva REAL NOT NULL DEFAULT 0 CHECK (iva >= 0),
            total REAL NOT NULL DEFAULT 0 CHECK (total >= 0),
            estado TEXT NOT NULL DEFAULT 'RECIBIDA' CHECK (estado IN ('RECIBIDA','ANULADA')),
            observaciones TEXT
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalle_compra (
            id_detalle_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            id_compra INTEGER NOT NULL REFERENCES compras(id_compra) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            costo_unitario REAL NOT NULL CHECK (costo_unitario >= 0),
            subtotal REAL NOT NULL
        );
    ''')

    cursor.execute('''
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
    ''')

    # --------------------------------------------------------------------------
    # C. VISTAS RELACIONALES DEL SISTEMA
    # --------------------------------------------------------------------------
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS vw_productos_stock_bajo AS
        SELECT
            p.id_producto,
            p.codigo,
            p.nombre,
            cp.nombre AS categoria,
            p.stock_actual,
            p.stock_minimo,
            u.abreviatura AS unidad
        FROM productos p
        JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
        JOIN unidades_medida u ON u.id_unidad = p.id_unidad
        WHERE p.activo = 1
          AND p.stock_actual <= p.stock_minimo;
    ''')

    cursor.execute('''
        CREATE VIEW IF NOT EXISTS vw_facturas_detalladas AS
        SELECT
            f.id_factura,
            f.numero,
            f.fecha_emision,
            c.nombre AS cliente,
            c.cedula_ruc,
            mp.nombre AS metodo_pago,
            ef.nombre AS estado,
            f.subtotal,
            f.iva,
            f.total,
            f.observaciones
        FROM facturas f
        JOIN clientes c ON c.id_cliente = f.id_cliente
        JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
        JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura;
    ''')

    cursor.execute('''
        CREATE VIEW IF NOT EXISTS vw_ventas_por_producto AS
        SELECT
            p.id_producto,
            p.codigo,
            p.nombre,
            cp.nombre AS categoria,
            COALESCE(SUM(df.cantidad), 0) AS unidades_vendidas,
            COALESCE(SUM(df.subtotal), 0) AS ventas
        FROM productos p
        JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
        LEFT JOIN detalle_factura df ON df.id_producto = p.id_producto
        LEFT JOIN facturas f ON f.id_factura = df.id_factura
        LEFT JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura AND ef.nombre = 'EMITIDA'
        GROUP BY p.id_producto, p.codigo, p.nombre, cp.nombre;
    ''')

    # --------------------------------------------------------------------------
    # D. POBLADO DE CATÁLOGOS BASE (SI ESTÁN VACÍOS)
    # --------------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) FROM tipos_cliente")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO tipos_cliente (nombre, descripcion) VALUES (?, ?)", [
            ('PERSONA NATURAL', 'Cliente consumidor final o persona natural'),
            ('EMPRESA', 'Cliente empresarial corporativo')
        ])

    cursor.execute("SELECT COUNT(*) FROM categorias_producto")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO categorias_producto (nombre, descripcion, activo) VALUES (?, ?, 1)", [
            ('TORTAS', 'Tortas y pasteles tradicionales y de autor'),
            ('POSTRES', 'Postres individuales y dulces finos'),
            ('PANADERIA', 'Productos de panadería artesanal y hojaldres'),
            ('BEBIDAS', 'Bebidas frías y cafetería de especialidad'),
            ('OTROS', 'Otros productos y complementos')
        ])

    cursor.execute("SELECT COUNT(*) FROM unidades_medida")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO unidades_medida (nombre, abreviatura) VALUES (?, ?)", [
            ('UNIDAD', 'UND'),
            ('KILOGRAMO', 'KG'),
            ('LITRO', 'L'),
            ('PORCION', 'POR')
        ])

    cursor.execute("SELECT COUNT(*) FROM categorias_proveedor")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO categorias_proveedor (nombre, descripcion) VALUES (?, ?)", [
            ('MATERIA PRIMA', 'Harina, azúcar, huevos, lácteos y otros insumos'),
            ('EMPAQUES', 'Cajas, fundas, vasos y empaques ecológicos'),
            ('BEBIDAS', 'Proveedores de granos de café y bebidas'),
            ('OTROS', 'Otros proveedores de suministros')
        ])

    cursor.execute("SELECT COUNT(*) FROM estados_proveedor")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO estados_proveedor (nombre, descripcion) VALUES (?, ?)", [
            ('ACTIVO', 'Proveedor homologado y habilitado'),
            ('INACTIVO', 'Proveedor temporalmente no habilitado')
        ])

    cursor.execute("SELECT COUNT(*) FROM estados_factura")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO estados_factura (nombre, descripcion) VALUES (?, ?)", [
            ('EMITIDA', 'Factura válida y cobrada'),
            ('ANULADA', 'Factura anulada'),
            ('PENDIENTE', 'Factura pendiente de pago o confirmación')
        ])

    cursor.execute("SELECT COUNT(*) FROM metodos_pago")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO metodos_pago (nombre, activo) VALUES (?, 1)", [
            ('EFECTIVO',),
            ('TRANSFERENCIA',),
            ('TARJETA',),
            ('DEPOSITO',)
        ])

    cursor.execute("SELECT COUNT(*) FROM tipos_movimiento_inventario")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO tipos_movimiento_inventario (nombre, naturaleza, descripcion) VALUES (?, ?, ?)", [
            ('COMPRA', 'E', 'Ingreso por compra a proveedor'),
            ('VENTA', 'S', 'Salida por venta a cliente'),
            ('AJUSTE ENTRADA', 'E', 'Ajuste positivo de inventario'),
            ('AJUSTE SALIDA', 'S', 'Ajuste negativo de inventario')
        ])

    # --------------------------------------------------------------------------
    # E. POBLADO DE DATOS DE EJEMPLO DE LA PASTELERÍA DULCE DELICIA
    # --------------------------------------------------------------------------
    cursor.execute("SELECT COUNT(*) FROM productos")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
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

    cursor.execute("SELECT COUNT(*) FROM clientes")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO clientes (id_tipo_cliente, nombre, cedula_ruc, correo, telefono, direccion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [
            (1, 'Consumidor Final', '9999999999999', 'final@dulcedelicia.ec', '0999999999', 'Quito - Ecuador'),
            (1, 'Ana Torres Mendoza', '1718293841', 'ana.torres@email.com', '0991112233', 'Av. República y Eloy Alfaro N34-12, Quito')
        ])

    cursor.execute("SELECT COUNT(*) FROM proveedores")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO proveedores (
                id_categoria_proveedor, id_estado_proveedor, razon_social, ruc,
                contacto, telefono, correo, direccion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (1, 1, 'Lácteos Andinos Cía. Ltda.', '1791234567001', 'Ing. María León', '0224588990', 'ventas@lacteosandinos.com', 'Parque Industrial Machachi, Pichincha'),
            (1, 1, 'Frutas del Valle Ecuador', '1792345678001', 'Lic. Carlos Ruiz', '0987654321', 'pedidos@frutasdelvalle.ec', 'Valle de los Chillos, Sangolquí')
        ])

    cursor.execute("SELECT COUNT(*) FROM facturas")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
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


# Invocación obligatoria para garantizar la existencia de tablas al arrancar la app
inicializar_base_datos()


# ==============================================================================
# 5. FUNCIONES AUXILIARES PARA FORMULARIOS FLASK-WTF (3FN)
# ==============================================================================
def sincronizar_opciones_producto(form):
    """Carga dinámicamente las categorías y unidades de medida desde SQLite en el formulario."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT id_categoria_producto, nombre FROM categorias_producto WHERE activo = 1 ORDER BY id_categoria_producto ASC")
    form.id_categoria_producto.choices = [(row['id_categoria_producto'], f"🎂 {row['nombre']}") for row in cursor.fetchall()]
    cursor.execute("SELECT id_unidad, nombre || ' (' || abreviatura || ')' AS etiqueta FROM unidades_medida ORDER BY id_unidad ASC")
    form.id_unidad.choices = [(row['id_unidad'], row['etiqueta']) for row in cursor.fetchall()]
    conn.close()


def sincronizar_opciones_cliente(form):
    """Carga los tipos de cliente desde SQLite en el formulario."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT id_tipo_cliente, nombre FROM tipos_cliente ORDER BY id_tipo_cliente ASC")
    form.id_tipo_cliente.choices = [(row['id_tipo_cliente'], f"👤 {row['nombre']}") for row in cursor.fetchall()]
    conn.close()


def sincronizar_opciones_proveedor(form):
    """Carga las categorías y estados de proveedores desde SQLite en el formulario."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT id_categoria_proveedor, nombre FROM categorias_proveedor ORDER BY id_categoria_proveedor ASC")
    form.id_categoria_proveedor.choices = [(row['id_categoria_proveedor'], f"🌾 {row['nombre']}") for row in cursor.fetchall()]
    cursor.execute("SELECT id_estado_proveedor, nombre FROM estados_proveedor ORDER BY id_estado_proveedor ASC")
    form.id_estado_proveedor.choices = [(row['id_estado_proveedor'], f"✅ {row['nombre']}") for row in cursor.fetchall()]
    conn.close()


def sincronizar_opciones_factura(form):
    """Carga clientes, métodos de pago y estados desde SQLite en el formulario de factura."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT id_cliente, nombre || ' (' || COALESCE(cedula_ruc, 'S/N') || ')' AS etiqueta FROM clientes ORDER BY nombre ASC")
    form.id_cliente.choices = [(row['id_cliente'], row['etiqueta']) for row in cursor.fetchall()]
    cursor.execute("SELECT id_metodo_pago, nombre FROM metodos_pago WHERE activo = 1 ORDER BY id_metodo_pago ASC")
    form.id_metodo_pago.choices = [(row['id_metodo_pago'], f"💵 {row['nombre']}") for row in cursor.fetchall()]
    cursor.execute("SELECT id_estado_factura, nombre FROM estados_factura ORDER BY id_estado_factura ASC")
    form.id_estado_factura.choices = [(row['id_estado_factura'], f"📌 {row['nombre']}") for row in cursor.fetchall()]
    conn.close()


# ==============================================================================
# 6. SEGURIDAD: DECORADOR DE SESIÓN ADMINISTRATIVA
# ==============================================================================
def login_requerido(f):
    """
    Decorador que valida la existencia de la sesión activa del usuario.
    Si el usuario no ha iniciado sesión, es redirigido a /login.
    """
    @wraps(f)
    def decorada(*args, **kwargs):
        if not session.get('usuario'):
            flash('Debe iniciar sesión para acceder al sistema administrativo.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorada


# ==============================================================================
# 7. MÓDULO DE AUTENTICACIÓN (LOGIN Y LOGOUT)
# ==============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Gestiona el inicio de sesión del personal administrativo mediante Flask-WTF.
    """
    if session.get('usuario'):
        return redirect(url_for('panel'))

    form = LoginForm()
    if form.validate_on_submit():
        usuario = form.usuario.data.strip()
        clave = form.password.data.strip()

        # Credenciales académicas demostrativas
        if usuario.lower() == 'admin' and clave == 'admin123':
            session['usuario'] = 'Administrador'
            session['rol'] = 'admin'
            flash('¡Bienvenido! Ha ingresado al sistema exitosamente.', 'success')
            return redirect(url_for('panel'))
        elif usuario and clave:
            session['usuario'] = usuario.capitalize()
            session['rol'] = 'usuario'
            flash(f'¡Bienvenido {session["usuario"]}! Ha ingresado al sistema.', 'success')
            return redirect(url_for('panel'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    """Cierra la sesión administrativa y redirige a la vista pública de la pastelería."""
    session.clear()
    flash('Ha cerrado su sesión correctamente.', 'info')
    return redirect(url_for('inicio'))


# ==============================================================================
# 8. PANEL ADMINISTRATIVO PRINCIPAL (PERSISTENCIA 3FN)
# ==============================================================================
@app.route('/panel')
@login_requerido
def panel():
    """
    Vista interna principal tras autenticarse en el sistema.
    Muestra 'Ha ingresado al sistema', métricas en tiempo real y últimos productos.
    """
    conn = obtener_conexion()
    cursor = conn.cursor()

    # Métricas totales de tablas relacionales
    cursor.execute("SELECT COUNT(*) FROM productos")
    total_productos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_clientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM proveedores")
    total_proveedores = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM facturas")
    total_facturas = cursor.fetchone()[0]

    # Consulta SELECT con JOIN hacia los catálogos 3FN para los últimos 3 postres
    cursor.execute('''
        SELECT
            p.id_producto AS id,
            p.id_producto,
            p.codigo,
            p.nombre,
            p.descripcion,
            p.precio_venta AS precio,
            p.precio_venta,
            p.stock_actual AS stock,
            p.stock_actual,
            p.stock_minimo,
            p.imagen,
            cp.nombre AS categoria,
            u.abreviatura AS unidad
        FROM productos p
        JOIN categorias_producto cp ON p.id_categoria_producto = cp.id_categoria_producto
        JOIN unidades_medida u ON p.id_unidad = u.id_unidad
        ORDER BY p.id_producto DESC
        LIMIT 3
    ''')
    ultimos_productos = cursor.fetchall()
    conn.close()

    metricas = {
        "total_productos": total_productos,
        "total_clientes": total_clientes,
        "total_proveedores": total_proveedores,
        "total_facturas": total_facturas
    }

    return render_template('panel.html', metricas=metricas, ultimos_productos=ultimos_productos)


# ==============================================================================
# 9. RUTA PÚBLICA PRINCIPAL (CATÁLOGO PARA CLIENTES)
# ==============================================================================
@app.route('/')
def inicio():
    """
    Página web pública de la pastelería artesanal Dulce Delicia.
    Solo contiene información de cara al cliente y el catálogo de productos.
    """
    conn = obtener_conexion()
    cursor = conn.cursor()

    # Consulta SELECT a la tabla productos normalizada
    cursor.execute('''
        SELECT
            p.id_producto AS id,
            p.codigo,
            p.nombre,
            p.descripcion,
            p.precio_venta AS precio,
            p.precio_venta,
            p.stock_actual AS stock,
            p.imagen,
            cp.nombre AS categoria,
            u.abreviatura AS unidad
        FROM productos p
        JOIN categorias_producto cp ON p.id_categoria_producto = cp.id_categoria_producto
        JOIN unidades_medida u ON p.id_unidad = u.id_unidad
        WHERE p.activo = 1
        ORDER BY p.id_producto ASC
    ''')
    productos_db = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM productos")
    total_p = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM clientes")
    total_c = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM proveedores")
    total_pr = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM facturas")
    total_f = cursor.fetchone()[0]
    conn.close()

    empresa = {
        "nombre": "Dulce Delicia",
        "ubicacion": "Quito - Ecuador",
        "eslogan": "Postres y Repostería Fina de Autor",
        "telefono": "+593 99 111 2233",
        "horario": "Lunes a Sábado: 08:30 - 19:30"
    }

    metricas = {
        "total_productos": total_p,
        "total_clientes": total_c,
        "total_proveedores": total_pr,
        "total_facturas": total_f
    }

    return render_template(
        "index.html",
        mensaje="Endulzamos tu día con arte y tradición",
        empresa=empresa,
        productos=productos_db,
        metricas=metricas
    )


# ==============================================================================
# 10. MÓDULO PRODUCTOS: PERSISTENCIA COMPLETA CRUD (SEMANA 12 - 3FN)
# ==============================================================================
@app.route('/productos')
@login_requerido
def productos():
    """
    Consulta y lista todos los productos registrados en SQLite mediante JOIN
    con los catálogos categorias_producto y unidades_medida.
    """
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            p.id_producto AS id,
            p.id_producto,
            p.codigo,
            p.nombre,
            p.descripcion,
            p.precio_venta AS precio,
            p.precio_venta,
            p.costo_referencial,
            p.stock_actual AS stock,
            p.stock_actual,
            p.stock_minimo,
            p.imagen,
            cp.nombre AS categoria,
            u.nombre AS unidad_nombre,
            u.abreviatura AS unidad
        FROM productos p
        JOIN categorias_producto cp ON p.id_categoria_producto = cp.id_categoria_producto
        JOIN unidades_medida u ON p.id_unidad = u.id_unidad
        ORDER BY p.id_producto ASC
    ''')
    lista_productos = cursor.fetchall()
    conn.close()

    return render_template("productos.html", productos=lista_productos)


@app.route('/productos/nuevo', methods=['GET', 'POST'])
@login_requerido
def nuevo_producto():
    """
    Inserta un nuevo producto en la base de datos local SQLite utilizando
    el formulario seguro ProductoForm (Flask-WTF).
    """
    form = ProductoForm()
    sincronizar_opciones_producto(form)

    # Autogenerar sugerencia de código en GET
    if request.method == 'GET':
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM productos")
        conteo = cursor.fetchone()[0]
        conn.close()
        form.codigo.data = f"POS-{conteo + 1:03d}"

    if form.validate_on_submit():
        codigo = form.codigo.data.strip().upper()
        nombre = form.nombre.data.strip()
        id_categoria = int(form.id_categoria_producto.data)
        id_unidad = int(form.id_unidad.data)
        descripcion = form.descripcion.data.strip()
        precio_venta = float(form.precio_venta.data)
        costo = float(form.costo_referencial.data) if form.costo_referencial.data else 0.0
        stock_actual = float(form.stock_actual.data)
        stock_minimo = float(form.stock_minimo.data)
        imagen = form.imagen.data

        conn = obtener_conexion()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO productos (
                    codigo, nombre, id_categoria_producto, id_unidad, descripcion,
                    precio_venta, costo_referencial, stock_actual, stock_minimo, imagen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                codigo, nombre, id_categoria, id_unidad, descripcion,
                precio_venta, costo, stock_actual, stock_minimo, imagen
            ))
            conn.commit()
            flash(f'¡Producto "{nombre}" ({codigo}) guardado con éxito en SQLite!', 'success')
            return redirect(url_for('productos'))
        except sqlite3.IntegrityError as e:
            flash(f'Error de integridad: El código "{codigo}" ya está registrado.', 'danger')
        finally:
            conn.close()

    return render_template("formulario_producto.html", form=form, modo="registro", producto=None)


@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_requerido
def editar_producto(id):
    """
    Recupera y actualiza los datos de un producto existente en SQLite (3FN).
    """
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos WHERE id_producto = ?", (id,))
    producto = cursor.fetchone()
    conn.close()

    if not producto:
        flash('El producto solicitado no existe en la base de datos.', 'warning')
        return redirect(url_for('productos'))

    form = ProductoForm()
    sincronizar_opciones_producto(form)

    # Cargar valores existentes en método GET
    if request.method == 'GET':
        form.codigo.data = producto['codigo']
        form.nombre.data = producto['nombre']
        form.id_categoria_producto.data = producto['id_categoria_producto']
        form.id_unidad.data = producto['id_unidad']
        form.descripcion.data = producto['descripcion']
        form.precio_venta.data = producto['precio_venta']
        form.costo_referencial.data = producto['costo_referencial']
        form.stock_actual.data = producto['stock_actual']
        form.stock_minimo.data = producto['stock_minimo']
        form.imagen.data = producto['imagen']

    # Procesar actualización al superar validaciones
    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE productos
            SET codigo = ?, nombre = ?, id_categoria_producto = ?, id_unidad = ?,
                descripcion = ?, precio_venta = ?, costo_referencial = ?,
                stock_actual = ?, stock_minimo = ?, imagen = ?
            WHERE id_producto = ?
        ''', (
            form.codigo.data.strip().upper(),
            form.nombre.data.strip(),
            int(form.id_categoria_producto.data),
            int(form.id_unidad.data),
            form.descripcion.data.strip(),
            float(form.precio_venta.data),
            float(form.costo_referencial.data) if form.costo_referencial.data else 0.0,
            float(form.stock_actual.data),
            float(form.stock_minimo.data),
            form.imagen.data,
            id
        ))
        conn.commit()
        conn.close()

        flash(f'¡Producto "{form.nombre.data.strip()}" actualizado con éxito!', 'info')
        return redirect(url_for('productos'))

    return render_template("formulario_producto.html", form=form, modo="edicion", producto=producto)


@app.route('/productos/eliminar/<int:id>', methods=['POST'])
@login_requerido
def eliminar_producto(id):
    """
    Elimina físicamente un producto de SQLite mediante petición POST protegida.
    """
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id_producto = ?", (id,))
    conn.commit()
    conn.close()

    flash('El producto ha sido eliminado del catálogo en SQLite.', 'warning')
    return redirect(url_for('productos'))


# ==============================================================================
# 11. MÓDULO CLIENTES: GESTIÓN CON MODELO NORMALIZADO (3FN)
# ==============================================================================
@app.route('/clientes')
@login_requerido
def clientes():
    """Consulta y presenta los clientes con su tipo obtenido mediante JOIN."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            c.id_cliente AS id,
            c.id_cliente,
            c.nombre,
            c.cedula_ruc AS cedula,
            c.cedula_ruc,
            c.correo,
            c.telefono,
            c.direccion,
            c.activo,
            tc.nombre AS tipo_cliente
        FROM clientes c
        JOIN tipos_cliente tc ON c.id_tipo_cliente = tc.id_tipo_cliente
        ORDER BY c.id_cliente ASC
    ''')
    lista_clientes = cursor.fetchall()
    conn.close()
    return render_template("clientes.html", clientes=lista_clientes)


@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_requerido
def nuevo_cliente():
    """Registra un nuevo cliente en SQLite mediante ClienteForm."""
    form = ClienteForm()
    sincronizar_opciones_cliente(form)

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clientes (id_tipo_cliente, nombre, cedula_ruc, correo, telefono, direccion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            int(form.id_tipo_cliente.data),
            form.nombre.data.strip(),
            form.cedula_ruc.data.strip(),
            form.correo.data.strip().lower(),
            form.telefono.data.strip(),
            form.direccion.data.strip()
        ))
        conn.commit()
        conn.close()
        flash(f'¡Cliente "{form.nombre.data.strip()}" registrado exitosamente!', 'success')
        return redirect(url_for('clientes'))

    return render_template("formulario_cliente.html", form=form, modo="registro", cliente=None)


@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_requerido
def editar_cliente(id):
    """Actualiza la información de un cliente en SQLite."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id_cliente = ?", (id,))
    cliente = cursor.fetchone()
    conn.close()

    if not cliente:
        flash('El cliente solicitado no existe.', 'warning')
        return redirect(url_for('clientes'))

    form = ClienteForm()
    sincronizar_opciones_cliente(form)

    if request.method == 'GET':
        form.id_tipo_cliente.data = cliente['id_tipo_cliente']
        form.nombre.data = cliente['nombre']
        form.cedula_ruc.data = cliente['cedula_ruc']
        form.correo.data = cliente['correo']
        form.telefono.data = cliente['telefono']
        form.direccion.data = cliente['direccion']

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE clientes
            SET id_tipo_cliente = ?, nombre = ?, cedula_ruc = ?, correo = ?,
                telefono = ?, direccion = ?
            WHERE id_cliente = ?
        ''', (
            int(form.id_tipo_cliente.data),
            form.nombre.data.strip(),
            form.cedula_ruc.data.strip(),
            form.correo.data.strip().lower(),
            form.telefono.data.strip(),
            form.direccion.data.strip(),
            id
        ))
        conn.commit()
        conn.close()
        flash(f'¡Cliente "{form.nombre.data.strip()}" actualizado correctamente!', 'info')
        return redirect(url_for('clientes'))

    return render_template("formulario_cliente.html", form=form, modo="edicion", cliente=cliente)


# ==============================================================================
# 12. MÓDULO PROVEEDORES: GESTIÓN CON MODELO NORMALIZADO (3FN)
# ==============================================================================
@app.route('/provedores')
@app.route('/proveedores')
@login_requerido
def proveedores():
    """Consulta y lista los proveedores con sus categorías y estados correspondientes."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            p.id_proveedor AS id,
            p.id_proveedor,
            p.razon_social AS empresa,
            p.razon_social,
            p.ruc,
            p.contacto,
            p.telefono,
            p.correo,
            p.direccion,
            cp.nombre AS categoria,
            ep.nombre AS estado
        FROM proveedores p
        LEFT JOIN categorias_proveedor cp ON p.id_categoria_proveedor = cp.id_categoria_proveedor
        LEFT JOIN estados_proveedor ep ON p.id_estado_proveedor = ep.id_estado_proveedor
        ORDER BY p.id_proveedor ASC
    ''')
    lista_proveedores = cursor.fetchall()
    conn.close()
    return render_template("proveedores.html", proveedores=lista_proveedores)


@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
@login_requerido
def nuevo_proveedor():
    """Inserta un nuevo proveedor comercial en SQLite."""
    form = ProveedorForm()
    sincronizar_opciones_proveedor(form)

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO proveedores (
                id_categoria_proveedor, id_estado_proveedor, razon_social,
                ruc, contacto, telefono, correo, direccion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            int(form.id_categoria_proveedor.data),
            int(form.id_estado_proveedor.data),
            form.razon_social.data.strip(),
            form.ruc.data.strip(),
            form.contacto.data.strip(),
            form.telefono.data.strip(),
            form.correo.data.strip().lower(),
            form.direccion.data.strip()
        ))
        conn.commit()
        conn.close()
        flash(f'¡Proveedor "{form.razon_social.data.strip()}" registrado exitosamente!', 'success')
        return redirect(url_for('proveedores'))

    return render_template("formulario_proveedor.html", form=form, modo="registro", proveedor=None)


@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
@login_requerido
def editar_proveedor(id):
    """Actualiza la información de un proveedor comercial en SQLite."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM proveedores WHERE id_proveedor = ?", (id,))
    proveedor = cursor.fetchone()
    conn.close()

    if not proveedor:
        flash('El proveedor solicitado no existe.', 'warning')
        return redirect(url_for('proveedores'))

    form = ProveedorForm()
    sincronizar_opciones_proveedor(form)

    if request.method == 'GET':
        form.razon_social.data = proveedor['razon_social']
        form.ruc.data = proveedor['ruc']
        form.contacto.data = proveedor['contacto']
        form.correo.data = proveedor['correo']
        form.telefono.data = proveedor['telefono']
        form.id_categoria_proveedor.data = proveedor['id_categoria_proveedor']
        form.id_estado_proveedor.data = proveedor['id_estado_proveedor']
        form.direccion.data = proveedor['direccion']

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE proveedores
            SET id_categoria_proveedor = ?, id_estado_proveedor = ?, razon_social = ?,
                ruc = ?, contacto = ?, telefono = ?, correo = ?, direccion = ?
            WHERE id_proveedor = ?
        ''', (
            int(form.id_categoria_proveedor.data),
            int(form.id_estado_proveedor.data),
            form.razon_social.data.strip(),
            form.ruc.data.strip(),
            form.contacto.data.strip(),
            form.telefono.data.strip(),
            form.correo.data.strip().lower(),
            form.direccion.data.strip(),
            id
        ))
        conn.commit()
        conn.close()
        flash(f'¡Proveedor "{form.razon_social.data.strip()}" actualizado correctamente!', 'info')
        return redirect(url_for('proveedores'))

    # Adaptador para compatibilidad visual con la plantilla
    prov_dict = dict(proveedor)
    prov_dict['empresa'] = proveedor['razon_social']
    return render_template("formulario_proveedor.html", form=form, modo="edicion", proveedor=prov_dict)


# ==============================================================================
# 13. MÓDULO FACTURACIÓN: GESTIÓN DE COMPROBANTES (3FN)
# ==============================================================================
@app.route('/facturacion')
@login_requerido
def facturacion():
    """Consulta y lista todas las facturas desde la vista normalizada."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            f.id_factura AS id,
            f.id_factura,
            f.numero,
            f.fecha_emision AS fecha,
            c.nombre AS cliente,
            c.cedula_ruc,
            mp.nombre AS metodo_pago,
            ef.nombre AS estado,
            f.subtotal,
            f.iva,
            f.total,
            f.observaciones
        FROM facturas f
        JOIN clientes c ON c.id_cliente = f.id_cliente
        JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
        JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
        ORDER BY f.id_factura ASC
    ''')
    lista_facturas = cursor.fetchall()
    conn.close()
    return render_template("facturacion.html", facturas=lista_facturas)


@app.route('/facturacion/nueva', methods=['GET', 'POST'])
@login_requerido
def nueva_factura():
    """Emite una nueva factura y la almacena en SQLite."""
    form = FacturacionForm()
    sincronizar_opciones_factura(form)

    # Sugerir correlativo y fecha actual en GET
    if request.method == 'GET':
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM facturas")
        conteo = cursor.fetchone()[0]
        conn.close()
        form.numero.data = f"FAC-{conteo + 1:03d}"
        form.fecha_emision.data = date.today()

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO facturas (
                numero, id_cliente, id_metodo_pago, id_estado_factura,
                fecha_emision, subtotal, iva, total, observaciones
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            form.numero.data.strip().upper(),
            int(form.id_cliente.data),
            int(form.id_metodo_pago.data),
            int(form.id_estado_factura.data),
            form.fecha_emision.data.strftime('%Y-%m-%d'),
            float(form.subtotal.data),
            float(form.iva.data),
            float(form.total.data),
            form.observaciones.data.strip() if form.observaciones.data else "Venta de postres artesanales."
        ))
        conn.commit()
        conn.close()
        flash(f'¡Factura {form.numero.data.strip()} emitida con éxito!', 'success')
        return redirect(url_for('facturacion'))

    return render_template("formulario_facturacion.html", form=form, modo="registro", factura=None)


@app.route('/facturacion/editar/<int:id>', methods=['GET', 'POST'])
@login_requerido
def editar_factura(id):
    """Permite modificar o corregir una factura registrada en SQLite."""
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM facturas WHERE id_factura = ?", (id,))
    factura = cursor.fetchone()
    conn.close()

    if not factura:
        flash('La factura solicitada no existe.', 'warning')
        return redirect(url_for('facturacion'))

    form = FacturacionForm()
    sincronizar_opciones_factura(form)

    if request.method == 'GET':
        form.numero.data = factura['numero']
        form.id_cliente.data = factura['id_cliente']
        try:
            form.fecha_emision.data = datetime.strptime(factura['fecha_emision'][:10], '%Y-%m-%d').date()
        except Exception:
            form.fecha_emision.data = date.today()

        form.id_metodo_pago.data = factura['id_metodo_pago']
        form.id_estado_factura.data = factura['id_estado_factura']
        form.subtotal.data = factura['subtotal']
        form.iva.data = factura['iva']
        form.total.data = factura['total']
        form.observaciones.data = factura['observaciones']

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE facturas
            SET numero = ?, id_cliente = ?, id_metodo_pago = ?, id_estado_factura = ?,
                fecha_emision = ?, subtotal = ?, iva = ?, total = ?, observaciones = ?
            WHERE id_factura = ?
        ''', (
            form.numero.data.strip().upper(),
            int(form.id_cliente.data),
            int(form.id_metodo_pago.data),
            int(form.id_estado_factura.data),
            form.fecha_emision.data.strftime('%Y-%m-%d'),
            float(form.subtotal.data),
            float(form.iva.data),
            float(form.total.data),
            form.observaciones.data.strip() if form.observaciones.data else "",
            id
        ))
        conn.commit()
        conn.close()
        flash(f'¡Factura {form.numero.data.strip()} actualizada correctamente!', 'info')
        return redirect(url_for('facturacion'))

    return render_template("formulario_facturacion.html", form=form, modo="edicion", factura=factura)


# ==============================================================================
# 14. EJECUCIÓN DEL SERVIDOR LOCAL DE DESARROLLO
# ==============================================================================
if __name__ == '__main__':
    # Arranca el servidor local de desarrollo en http://127.0.0.1:5000/
    app.run(debug=True)
