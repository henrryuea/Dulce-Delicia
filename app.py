# ==============================================================================
# APLICACIÓN PRINCIPAL: DULCE DELICIA
# Control Principal de la Aplicación Flask (Backend)
# ==============================================================================
# Este archivo contiene la configuración central del servidor y los controladores
# (rutas y vistas) que gestionan la lógica de negocio para:
# 1. Página de inicio y presentación de la empresa
# 2. Catálogo y gestión de Productos (CRUD) y sus Categorías (CRUD)
# 3. Directorio de proveedores e insumos (CRUD)
# 4. Directorio de Clientes y cartera comercial (CRUD)
# 5. Emisión de Facturas y Cotizaciones (CRUD) con detalle relacional real
#
# Persistencia de datos: PostgreSQL, mediante conexion/conexion.py (conexión centralizada).
# Todas las tablas están relacionadas mediante claves primarias y foráneas:
#   clientes  <--(cliente_cedula)--  facturacion  --(factura_numero)-->  detalle_factura
#   categorias_producto <--(categoria_producto_id)--  productos  <--(producto_id)--  detalle_factura
# ==============================================================================

import os
import json
import io
import math
import re
import secrets
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import psycopg2
from PIL import Image, ImageOps, UnidentifiedImageError
from html.parser import HTMLParser
from functools import wraps
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import click
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.exceptions import HTTPException
import bcrypt
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import InvalidToken

# Modelos de Usuario, Roles, Permisos y Logs de Auditoría (RBAC)
from models import Usuario, User, Role, ActivityLog, es_hash_contrasena

# Importación de clases de formularios creadas con Flask-WTF
from forms.cliente_form import ClienteForm
from forms.tipo_cliente_form import TipoClienteForm
from forms.producto_form import ProductoForm
from forms.categoria_producto_form import CategoriaProductoForm
from forms.proveedor_form import ProveedorForm
from forms.categoria_proveedor_form import CategoriaProveedorForm
from forms.facturacion_form import FacturacionForm
from forms.login_form import LoginForm
from forms.usuario_form import UsuarioForm
from forms.dos_factores_form import DosFactoresForm
from forms.mi_cuenta_form import MiCuentaForm

# Módulo propio de conexión centralizada a PostgreSQL (carpeta conexion/)
from conexion.conexion import close_db_connection, get_db_connection
from security.totp import (
    cifrar_secreto_totp,
    descifrar_secreto_totp,
    generar_secreto_totp,
    periodo_totp_valido,
    uri_configuracion_totp,
)


class _ImagenMetaParser(HTMLParser):
    """Obtiene la imagen principal declarada por una página web."""

    def __init__(self):
        super().__init__()
        self.imagen_url = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'meta' or self.imagen_url:
            return

        atributos = {clave.lower(): valor for clave, valor in attrs}
        referencia = (atributos.get('property') or atributos.get('name') or '').lower()
        if referencia in ('og:image', 'og:image:url', 'twitter:image', 'twitter:image:src'):
            self.imagen_url = atributos.get('content')


def resolver_url_imagen(valor):
    """Resuelve una imagen, conservando enlaces HTTPS válidos como respaldo."""
    url = (valor or '').strip()
    partes = urlparse(url)
    if partes.scheme not in ('http', 'https') or not partes.netloc:
        return None

    try:
        solicitud = Request(url, headers={'User-Agent': 'Dulce Delicia/1.0'})
        with urlopen(solicitud, timeout=8) as respuesta:
            tipo_contenido = respuesta.headers.get_content_type().lower()
            if tipo_contenido.startswith('image/'):
                return url

            if tipo_contenido in ('application/octet-stream', 'binary/octet-stream') and \
                    partes.path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif')):
                return url

            if not (tipo_contenido.startswith('text/html') or tipo_contenido == 'application/xhtml+xml'):
                return None

            contenido = respuesta.read(2_000_000).decode(
                respuesta.headers.get_content_charset() or 'utf-8',
                errors='replace'
            )
            parser = _ImagenMetaParser()
            parser.feed(contenido)
            if parser.imagen_url:
                imagen = urljoin(url, parser.imagen_url.strip())
                imagen_partes = urlparse(imagen)
                if imagen_partes.scheme in ('http', 'https') and imagen_partes.netloc:
                    return imagen
    except Exception:
        # El enlace puede ser válido aunque el servidor remoto bloquee la
        # verificación desde backend. El navegador aún puede cargarlo.
        return url

    return url

# ------------------------------------------------------------------------------
# INICIALIZACIÓN DE LA APLICACIÓN FLASK
# ------------------------------------------------------------------------------
app = Flask(__name__)
app.config['PROFILE_UPLOAD_FOLDER'] = os.path.join(
    app.static_folder or 'static', 'uploads', 'perfiles'
)

# Clave secreta para la protección de sesiones y seguridad contra ataques CSRF en formularios
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    if os.getenv('FLASK_ENV', 'development').lower() != 'production':
        app.config['SECRET_KEY'] = 'clave-local-dulce_delicia-2026'
    else:
        raise RuntimeError('SECRET_KEY es obligatoria fuera del modo de desarrollo.')

app.config['WTF_CSRF_ENABLED'] = True
# Límite global del cuerpo de las solicitudes (fotos de perfil: máx. 5 MB)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
csrf = CSRFProtect(app)

# Expiración automática de sesión tras 30 minutos de inactividad
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV', 'development').lower() == 'production'
app.teardown_appcontext(close_db_connection)


@app.after_request
def asegurar_codificacion_utf8(response):
    """Declara UTF-8 explícitamente para que los textos en español no se deformen."""
    if response.mimetype == 'text/html':
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE AUTENTICACIÓN (Flask-Login)
# ------------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    """
    Función de callback requerida por Flask-Login para recuperar la instancia del
    usuario autenticado desde la base de datos a partir de su ID de sesión.
    """
    return Usuario.get_by_id(user_id)


# ------------------------------------------------------------------------------
# FUNCIONES AUXILIARES: REGISTRO, AUDITORÍA Y CONTROL DE ACCESO (RBAC)
# ------------------------------------------------------------------------------

def validar_password_segura(password):
    """Exige una clave larga y diversa sin forzar símbolos en todos los casos."""
    if len(password) < 12:
        return False
    # bcrypt solo procesa los primeros 72 bytes: se acota la clave para que
    # el cifrado sea determinista y la contraseña siga validando al ingresar.
    if len(password.encode('utf-8')) > 72:
        return False
    clases = (
        bool(re.search(r'[a-z]', password)),
        bool(re.search(r'[A-Z]', password)),
        bool(re.search(r'\d', password)),
        bool(re.search(r'[^A-Za-z0-9]', password)),
    )
    return sum(clases) >= 3


def asegurar_inventario_base():
    """Crea columnas y tablas mínimas para stock y kardex si aún no existen."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'productos' AND column_name = 'stock_actual'
        """)
        if cur.fetchone() is None:
            cur.execute('ALTER TABLE productos ADD COLUMN stock_actual INTEGER NOT NULL DEFAULT 0')
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'productos' AND column_name = 'stock_minimo'
        """)
        if cur.fetchone() is None:
            cur.execute('ALTER TABLE productos ADD COLUMN stock_minimo INTEGER NOT NULL DEFAULT 0')
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kardex_movimientos (
                id SERIAL PRIMARY KEY,
                producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
                tipo VARCHAR(20) NOT NULL,
                cantidad INTEGER NOT NULL,
                referencia VARCHAR(120),
                descripcion TEXT,
                usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                automatico BOOLEAN NOT NULL DEFAULT FALSE,
                factura_numero VARCHAR(30) REFERENCES facturacion(numero) ON DELETE SET NULL,
                fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            ALTER TABLE kardex_movimientos
            ADD COLUMN IF NOT EXISTS automatico BOOLEAN NOT NULL DEFAULT FALSE
        """)
        cur.execute("""
            ALTER TABLE kardex_movimientos
            ADD COLUMN IF NOT EXISTS factura_numero VARCHAR(30)
            REFERENCES facturacion(numero) ON DELETE SET NULL
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_kardex_factura
            ON kardex_movimientos (factura_numero)
        """)
        cur.execute("""
            ALTER TABLE kardex_movimientos
            ADD COLUMN IF NOT EXISTS costo_unitario NUMERIC(12,2)
        """)
        cur.execute("""
            ALTER TABLE productos
            ADD COLUMN IF NOT EXISTS es_insumo BOOLEAN NOT NULL DEFAULT FALSE
        """)
        conn.commit()
    finally:
        cur.close()
        conn.close()


def ajustar_kardex_venta(cursor, factura_numero, productos_detalle, usuario_id,
                         tipo_documento, force_tracking=False):
    """Concilia las salidas de inventario de una venta con su detalle actual."""
    cursor.execute(
        '''SELECT producto_id, tipo, cantidad
           FROM kardex_movimientos
           WHERE factura_numero = %s AND automatico = TRUE
           ORDER BY id
           FOR UPDATE''',
        (factura_numero,)
    )
    movimientos_existentes = cursor.fetchall()
    if not movimientos_existentes and not force_tracking:
        return None

    cantidades_registradas = {}
    for movimiento in movimientos_existentes:
        producto_id = movimiento['producto_id']
        cantidad = int(movimiento['cantidad'])
        factor = 1 if movimiento['tipo'] == 'salida' else -1
        cantidades_registradas[producto_id] = cantidades_registradas.get(producto_id, 0) + factor * cantidad

    cantidades_objetivo = {}
    if tipo_documento == 'Factura':
        for item in productos_detalle:
            producto_id = item.get('id')
            if producto_id is not None:
                producto_id = int(producto_id)
                cantidades_objetivo[producto_id] = cantidades_objetivo.get(producto_id, 0) + int(item['cantidad'])

    ids_productos = sorted(set(cantidades_registradas) | set(cantidades_objetivo))
    if not ids_productos:
        return None

    cursor.execute(
        '''SELECT id, nombre, stock_actual
           FROM productos
           WHERE id = ANY(%s)
           ORDER BY id
           FOR UPDATE''',
        (ids_productos,)
    )
    productos = {row['id']: row for row in cursor.fetchall()}
    if len(productos) != len(ids_productos):
        return 'Uno de los productos de la venta ya no existe en el inventario.'

    cambios = []
    for producto_id in ids_productos:
        cantidad_actual = cantidades_registradas.get(producto_id, 0)
        cantidad_objetivo = cantidades_objetivo.get(producto_id, 0)
        diferencia = cantidad_objetivo - cantidad_actual
        producto = productos[producto_id]
        stock_actual = int(producto['stock_actual'])
        stock_disponible_documento = stock_actual + cantidad_actual
        if tipo_documento == 'Factura' and cantidad_objetivo > stock_disponible_documento:
            faltante = cantidad_objetivo - stock_disponible_documento
            return (
                f'Stock insuficiente para vender {producto["nombre"]}. '
                f'Disponibles para este pedido: {stock_disponible_documento}; '
                f'solicitadas: {cantidad_objetivo}; faltan: {faltante}.'
            )
        if diferencia == 0:
            continue
        nuevo_stock = stock_actual - diferencia
        cambios.append((producto_id, diferencia, nuevo_stock))

    if movimientos_existentes:
        descripcion = 'Ajuste automático por edición de venta'
    else:
        descripcion = 'Salida automática por venta'
    if tipo_documento != 'Factura':
        descripcion = 'Reverso automático por cambio o eliminación de venta'

    for producto_id, diferencia, nuevo_stock in cambios:
        tipo_movimiento = 'salida' if diferencia > 0 else 'entrada'
        cantidad_movimiento = abs(diferencia)
        cursor.execute(
            'UPDATE productos SET stock_actual = %s WHERE id = %s',
            (nuevo_stock, producto_id)
        )
        cursor.execute(
            '''INSERT INTO kardex_movimientos
               (producto_id, tipo, cantidad, referencia, descripcion, usuario_id, automatico, factura_numero)
               VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)''',
            (
                producto_id, tipo_movimiento, cantidad_movimiento, factura_numero,
                descripcion, usuario_id, factura_numero
            )
        )
    return None


def calcular_kardex_valorizado(movimientos):
    """
    Construye la hoja kardex real con costo promedio ponderado.

    Recibe movimientos ordenados cronológicamente y devuelve las filas con
    entrada (cantidad, costo unitario, total), salida (cantidad, costo
    unitario, total) y saldo acumulado (cantidad, costo unitario, valor).
    Las entradas sin costo explícito se valoran al promedio vigente.
    """
    def money(valor):
        return Decimal(valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    saldo_cantidad = Decimal(0)
    saldo_valor = Decimal(0)
    filas = []
    for movimiento in movimientos:
        cantidad = Decimal(int(movimiento['cantidad']))
        es_entrada = movimiento['tipo'] == 'entrada'
        if es_entrada:
            costo_guardado = movimiento.get('costo_unitario')
            if costo_guardado is not None and Decimal(costo_guardado) > 0:
                costo_unitario = Decimal(costo_guardado)
            elif saldo_cantidad > 0:
                costo_unitario = saldo_valor / saldo_cantidad
            else:
                costo_unitario = Decimal(0)
            total = costo_unitario * cantidad
            saldo_cantidad += cantidad
            saldo_valor += total
        else:
            costo_unitario = (saldo_valor / saldo_cantidad) if saldo_cantidad > 0 else Decimal(0)
            total = costo_unitario * cantidad
            saldo_cantidad -= cantidad
            saldo_valor = (saldo_valor - total) if saldo_cantidad > 0 else Decimal(0)
            if saldo_cantidad <= 0:
                saldo_cantidad = max(saldo_cantidad, Decimal(0))
        saldo_unitario = (saldo_valor / saldo_cantidad) if saldo_cantidad > 0 else Decimal(0)
        filas.append({
            'movimiento': movimiento,
            'entrada_cantidad': cantidad if es_entrada else None,
            'entrada_costo': money(costo_unitario) if es_entrada else None,
            'entrada_total': money(total) if es_entrada else None,
            'salida_cantidad': cantidad if not es_entrada else None,
            'salida_costo': money(costo_unitario) if not es_entrada else None,
            'salida_total': money(total) if not es_entrada else None,
            'saldo_cantidad': saldo_cantidad,
            'saldo_costo': money(saldo_unitario),
            'saldo_valor': money(saldo_valor),
        })
    totales = {
        'entrada_cantidad': sum((f['entrada_cantidad'] for f in filas if f['entrada_cantidad']), Decimal(0)),
        'entrada_valor': sum((f['entrada_total'] for f in filas if f['entrada_total']), Decimal(0)),
        'salida_cantidad': sum((f['salida_cantidad'] for f in filas if f['salida_cantidad']), Decimal(0)),
        'salida_valor': sum((f['salida_total'] for f in filas if f['salida_total']), Decimal(0)),
        'saldo_cantidad': saldo_cantidad,
        'saldo_valor': money(saldo_valor),
        'saldo_costo': money((saldo_valor / saldo_cantidad) if saldo_cantidad > 0 else Decimal(0)),
    }
    return filas, totales


def asegurar_datos_proveedor():
    """Añade información comercial opcional sin afectar los registros existentes."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS ruc VARCHAR(13)')
        cur.execute('ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS persona_contacto VARCHAR(150)')
        cur.execute('ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS telefono VARCHAR(30)')
        cur.execute('ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS correo VARCHAR(150)')
        cur.execute('ALTER TABLE proveedores ADD COLUMN IF NOT EXISTS sitio_web VARCHAR(300)')
        cur.execute(
            '''UPDATE proveedores
               SET correo = contacto
               WHERE correo IS NULL AND contacto ~* '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$' '''
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def asegurar_parametros_fiscales():
    """Crea los parámetros tributarios configurables y conserva el IVA existente."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS parametros (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(50) NOT NULL UNIQUE,
                nombre VARCHAR(100) NOT NULL,
                valor NUMERIC(7,4) NOT NULL CHECK (valor >= 0 AND valor <= 100),
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                descripcion VARCHAR(300),
                actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute(
            '''INSERT INTO parametros (codigo, nombre, valor, descripcion)
               VALUES ('iva', 'IVA', 15, 'Porcentaje tributario aplicado a las ventas')
               ON CONFLICT (codigo) DO NOTHING'''
        )
        cur.execute(
            "UPDATE parametros SET activo = FALSE WHERE codigo <> 'iva' AND activo = TRUE"
        )
        cur.execute(
            "ALTER TABLE facturacion ADD COLUMN IF NOT EXISTS impuestos_detalle JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def asegurar_detalles_factura():
    """Añade metadatos de línea sin invalidar facturas anteriores."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE detalle_factura ADD COLUMN IF NOT EXISTS descripcion_linea TEXT")
        cur.execute(
            "ALTER TABLE detalle_factura ADD COLUMN IF NOT EXISTS unidad_medida VARCHAR(30) NOT NULL DEFAULT 'unidad'"
        )
        cur.execute(
            "ALTER TABLE detalle_factura ADD COLUMN IF NOT EXISTS es_adicional BOOLEAN NOT NULL DEFAULT FALSE"
        )
        cur.execute(
            '''SELECT data_type FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'detalle_factura'
                 AND column_name = 'cantidad' '''
        )
        columna_cantidad = cur.fetchone()
        if columna_cantidad and columna_cantidad['data_type'] != 'numeric':
            cur.execute(
                'ALTER TABLE detalle_factura ALTER COLUMN cantidad TYPE NUMERIC(12,3) USING cantidad::NUMERIC(12,3)'
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def asegurar_campos_cliente():
    """Agrega campos opcionales de contacto sin afectar clientes existentes."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS apellido VARCHAR(100)")
        cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS direccion VARCHAR(300)")
        conn.commit()
    finally:
        cur.close()
        conn.close()


def asegurar_snapshots_documentos():
    """Prepara snapshots históricos en ventas y recibos sin alterar documentos previos."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for tabla in ('facturacion', 'comprobantes_pago'):
            for campo, tipo in (
                ('cliente_nombre_snapshot', 'VARCHAR(150)'),
                ('cliente_apellido_snapshot', 'VARCHAR(100)'),
                ('cliente_correo_snapshot', 'VARCHAR(150)'),
                ('cliente_telefono_snapshot', 'VARCHAR(20)'),
                ('cliente_direccion_snapshot', 'VARCHAR(300)'),
                ('cliente_ciudad_snapshot', 'VARCHAR(100)'),
            ):
                cur.execute(
                    f'ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS {campo} {tipo}'
                )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def obtener_impuestos_activos(cursor):
    """Devuelve tasas tributarias vigentes para el cálculo de un nuevo documento."""
    cursor.execute(
        '''SELECT id, codigo, nombre, valor, descripcion
           FROM parametros
           WHERE codigo = 'iva' AND activo = TRUE
           ORDER BY id'''
    )
    return [
        {
            'id': row['id'],
            'codigo': row['codigo'],
            'nombre': row['nombre'],
            'porcentaje': float(row['valor']),
            'descripcion': row['descripcion']
        }
        for row in cursor.fetchall()
    ]


def calcular_impuestos(subtotal, impuestos):
    """Calcula cada tributo configurado y conserva el desglose aplicado al documento."""
    desglose = [
        {
            **impuesto,
            'monto': round(float(subtotal) * impuesto['porcentaje'] / 100, 2)
        }
        for impuesto in impuestos
    ]
    return round(sum(impuesto['monto'] for impuesto in desglose), 2), desglose


def rol_requiere_aprobacion(rol_nombre):
    """Todos los perfiles excepto Cliente requieren autorización administrativa."""
    return rol_nombre.strip().casefold() != 'cliente'


def es_mayor_de_edad(fecha_nacimiento):
    """
    Determina en el servidor si la fecha de nacimiento corresponde a un mayor
    de edad. Una fecha nula o futura nunca cuenta como mayoría de edad.
    """
    if not isinstance(fecha_nacimiento, date):
        return False
    hoy = date.today()
    if fecha_nacimiento > hoy:
        return False
    cumple_18 = date(fecha_nacimiento.year + 18, fecha_nacimiento.month, fecha_nacimiento.day)
    return cumple_18 <= hoy


def vincular_cliente_con_usuario(cursor, cedula, correo):
    """
    Relaciona la ficha del cliente con la cuenta de usuario que usa el mismo
    correo. Si el usuario ya está ligado a otra ficha, la ficha nueva queda sin
    vincular para no romper la relación uno a uno.
    """
    if not correo:
        return None
    cursor.execute(
        'SELECT id FROM usuarios WHERE LOWER(TRIM(correo)) = LOWER(TRIM(%s)) LIMIT 1',
        (correo,)
    )
    usuario = cursor.fetchone()
    if not usuario:
        return None
    cursor.execute(
        'SELECT 1 FROM clientes WHERE usuario_id = %s AND cedula <> %s LIMIT 1',
        (usuario['id'], cedula)
    )
    return None if cursor.fetchone() else usuario['id']


def registrar_solicitud_acceso(cursor, usuario_id, rol_id, aprobado):
    """Deja constancia de la solicitud de acceso para que el Administrador la resuelva."""
    try:
        cursor.execute('SAVEPOINT solicitud_acceso')
        cursor.execute(
            '''INSERT INTO solicitudes_acceso (usuario_id, rol_id, estado, fecha_decision)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (usuario_id, rol_id) DO UPDATE
                   SET estado = EXCLUDED.estado, fecha_decision = EXCLUDED.fecha_decision''',
            (usuario_id, rol_id, 'Aprobada' if aprobado else 'Pendiente',
             datetime.now() if aprobado else None)
        )
        cursor.execute('RELEASE SAVEPOINT solicitud_acceso')
    except psycopg2.Error:
        # Si la tabla de solicitudes aún no existe, la cuenta ya quedó guardada:
        # la aprobación manual sigue disponible desde el panel de usuarios.
        try:
            cursor.execute('ROLLBACK TO SAVEPOINT solicitud_acceso')
        except psycopg2.Error:
            pass


def puede_ver_productos_futuros(usuario):
    """Solo clientes autenticados y autorizados pueden ver próximos productos."""
    return bool(
        usuario.is_authenticated
        and usuario.has_role('Cliente')
        and usuario.has_permission('productos.futuros')
    )


def registro_es_automatizado(sitio_web, inicio, ahora=None):
    """Detecta formularios rellenados por bots o enviados demasiado rápido."""
    if (sitio_web or '').strip():
        return True
    try:
        inicio = float(inicio)
        ahora = float(ahora if ahora is not None else time.time())
    except (TypeError, ValueError):
        return True
    transcurrido = ahora - inicio
    return transcurrido < 2 or transcurrido > 3600


@app.cli.command('crear-administrador')
def crear_administrador():
    """Crea la primera cuenta administrativa desde una consola confiable."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                '''SELECT 1
                   FROM usuarios u
                   JOIN roles r ON r.id = u.rol_id
                   WHERE r.nombre = 'Administrador'
                     AND u.aprobado = TRUE
                     AND u.activo = TRUE
                   LIMIT 1'''
            )
            if cursor.fetchone():
                raise click.ClickException('Ya existe una cuenta administradora.')

    usuario = click.prompt('Nombre de usuario').strip()
    correo = click.prompt('Correo electrónico').strip().lower()
    if len(usuario) < 3 or len(usuario) > 50:
        raise click.ClickException('El usuario debe tener entre 3 y 50 caracteres.')
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', correo):
        raise click.ClickException('El correo electrónico no es válido.')

    password = click.prompt('Contraseña', hide_input=True, confirmation_prompt=True)
    if not validar_password_segura(password):
        raise click.ClickException(
            'La clave debe tener al menos 12 caracteres y combinar al menos 3 tipos '
            '(minúsculas, mayúsculas, números o símbolos).'
        )

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM roles WHERE nombre = 'Administrador'")
            rol = cursor.fetchone()
            if rol is None:
                raise click.ClickException('No existe el rol Administrador en la base de datos.')
            cursor.execute(
                '''INSERT INTO usuarios
                   (usuario, correo, password, rol_id, activo, email_confirmado, aprobado, dos_factores_activo)
                   VALUES (%s, %s, %s, %s, TRUE, TRUE, TRUE, FALSE)''',
                (usuario, correo, User.hash_password(password), rol['id'])
            )
    click.echo(f'Cuenta administradora creada para {usuario}.')


@app.cli.command('permisos')
@click.argument('accion', required=False)
@click.argument('codigo', required=False)
@click.argument('rol', required=False)
@click.option('--estado/--inactivo', default=True, help='Activa o desactiva el permiso.')
def permisos_cli(accion, codigo, rol, estado):
    """
    Administra los permisos desde la terminal, igual que desde PostgreSQL.

      flask permisos                                   Lista la matriz rol x permiso
      flask permisos activar <codigo> [--inactivo]     Enciende o apaga un permiso
      flask permisos asignar <codigo> <rol>             Concede el permiso a un rol
      flask permisos revocar  <codigo> <rol>             Lo retira del rol

    En PostgreSQL los mismos cambios se hacen con las funciones
    activar_permiso(codigo, activo), asignar_permiso(rol, codigo) y
    revocar_permiso(rol, codigo).
    """
    matriz = Usuario.matriz_permisos()
    accion = (accion or '').lower()

    if accion in ('', 'listar', 'list'):
        roles_vistos = []
        for fila in matriz:
            if fila['rol_nombre'] not in roles_vistos:
                roles_vistos.append(fila['rol_nombre'])
                click.echo(f"\n{fila['rol_nombre']}")
            marca = 'X' if fila['asignado'] and fila['permiso_activo'] else (
                '-' if fila['asignado'] else ' '
            )
            estado_txt = '' if fila['permiso_activo'] else '  [inactivo]'
            click.echo(f"  [{marca}] {fila['permiso_codigo']}{estado_txt}")
        return

    if accion == 'activar':
        if not codigo:
            raise click.ClickException('Indica el permiso: flask permisos activar <codigo>')
        Usuario.definir_permiso(codigo, activo=estado)
        click.echo(f'Permiso {codigo}: {"activo" if estado else "desactivado"}')
        return

    if accion in ('asignar', 'revocar'):
        if not codigo or not rol:
            raise click.ClickException(
                f'Indica permiso y rol: flask permisos {accion} <codigo> <rol>'
            )
        Usuario.definir_permiso(codigo, rol_nombre=rol, asignado=(accion == 'asignar'))
        click.echo(
            f'Permiso {codigo} {"asignado a" if accion == "asignar" else "revocado de"} {rol}'
        )
        return

    raise click.ClickException(
        f'Acción desconocida: {accion}. Usa listar, activar, asignar o revocar.'
    )


@app.cli.command('auditar-esquema')
def auditar_esquema():
    """
    Comprueba que la base de datos conectada tenga el modelo relacional completo:
    tablas, claves foráneas, cifrado único de contraseñas y datos sin huérfanos.
    """
    # Relaciones que deben existir para que ninguna tabla quede suelta.
    esperadas = [
        ('clientes', 'tipo_cliente_id', 'tipos_cliente'), ('clientes', 'usuario_id', 'usuarios'),
        ('productos', 'categoria_producto_id', 'categorias_producto'),
        ('productos', 'proveedor_id', 'proveedores'),
        ('proveedores', 'categoria_id', 'categorias_proveedor'),
        ('proveedores', 'estado_id', 'estados_proveedor'),
        ('facturacion', 'cliente_cedula', 'clientes'), ('facturacion', 'estado_id', 'estados_documento'),
        ('facturacion', 'usuario_id', 'usuarios'), ('facturacion', 'iva_id', 'parametros'),
        ('detalle_factura', 'factura_numero', 'facturacion'),
        ('detalle_factura', 'producto_id', 'productos'),
        ('detalle_factura', 'iva_id', 'parametros'),
        ('pagos_factura', 'factura_numero', 'facturacion'), ('pagos_factura', 'usuario_id', 'usuarios'),
        ('cuotas_factura', 'factura_numero', 'facturacion'), ('cuotas_factura', 'pago_id', 'pagos_factura'),
        ('comprobantes_pago', 'pago_id', 'pagos_factura'),
        ('comprobantes_pago', 'factura_numero', 'facturacion'),
        ('comprobantes_pago', 'cliente_cedula', 'clientes'),
        ('kardex_movimientos', 'producto_id', 'productos'),
        ('kardex_movimientos', 'usuario_id', 'usuarios'),
        ('kardex_movimientos', 'factura_numero', 'facturacion'),
        ('logs_actividad', 'usuario_id', 'usuarios'),
        ('rol_permisos', 'rol_id', 'roles'), ('rol_permisos', 'permiso_id', 'permisos'),
        ('usuarios', 'rol_id', 'roles'),
        ('solicitudes', 'responsable_id', 'usuarios'), ('solicitudes', 'entregado_por_id', 'usuarios'),
        ('solicitudes', 'usuario_id', 'usuarios'),
        ('solicitudes', 'categoria_producto_id', 'categorias_producto'),
        ('solicitudes_acceso', 'usuario_id', 'usuarios'), ('solicitudes_acceso', 'rol_id', 'roles'),
    ]
    columnas_esperadas = [
        ('usuarios', 'fecha_nacimiento'), ('usuarios', 'es_mayor_edad'),
        ('detalle_factura', 'iva_valor'), ('facturacion', 'proxima_pago_fecha'),
        ('facturacion', 'proxima_pago_monto'), ('cuotas_factura', 'numero_pago'),
        ('cuotas_factura', 'valor_pago'), ('cuotas_factura', 'saldo_pago'),
        ('permisos', 'activo'),
    ]

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT tc.table_name AS tabla, kcu.column_name AS columna, ccu.table_name AS referencia
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
    """)
    existentes = {(f['tabla'], f['columna'], f['referencia']) for f in cur.fetchall()}
    faltantes = [v for v in esperadas if v not in existentes]

    cur.execute("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND column_name = ANY(%s)
    """, ([columna for _, columna in columnas_esperadas],))
    columnas_base = {(f['table_name'], f['column_name']) for f in cur.fetchall()}
    faltantes_columnas = [v for v in columnas_esperadas if v not in columnas_base]

    cur.execute("""
        SELECT tgname FROM pg_trigger
        WHERE tgrelid = 'usuarios'::regclass AND NOT tgisinternal
          AND tgname NOT IN ('trg_solicitud_acceso')
    """)
    triggers = [f['tgname'] for f in cur.fetchall()]
    cur.close()
    conn.close()

    click.echo(f'Relación foránea verificadas: {len(esperadas) - len(faltantes)}/{len(esperadas)}')
    for tabla, columna, referencia in faltantes:
        click.echo(f'  FALTA  {tabla}.{columna} -> {referencia}')
    click.echo(f'Columnas verificadas: {len(columnas_esperadas) - len(faltantes_columnas)}/{len(columnas_esperadas)}')
    for tabla, columna in faltantes_columnas:
        click.echo(f'  FALTA  {tabla}.{columna}')
    click.echo(f'Triggers de usuarios: {", ".join(triggers) or "ninguno"}')
    if triggers != ['trg_cifrar_password']:
        click.echo('  AVISO  debe existir un solo trigger de cifrado: trg_cifrar_password')

    if faltantes or faltantes_columnas:
        click.echo('\nAplica las migraciones de la carpeta sql/ en orden.')
        raise SystemExit(1)
    click.echo('\nLa base de datos está completa y relacionada.')


@app.cli.command('establecer-password')
@click.argument('usuario')
def establecer_password(usuario):
    """
    Guarda la contraseña de una cuenta cifrándola UNA sola vez.

    Repara cuentas cuyo hash quedó cifrado en capas (hash de hash) o generado
    por INSERT directo en SQL, para que la contraseña escrita sea exactamente
    la que valida al iniciar sesión.
    """
    objetivo = Usuario.get_by_usuario_o_correo(usuario.strip())
    if not objetivo:
        raise click.ClickException('No existe una cuenta con ese usuario o correo.')

    password = click.prompt('Nueva contraseña', hide_input=True, confirmation_prompt=True)
    if not validar_password_segura(password):
        raise click.ClickException(
            'La clave debe tener al menos 12 caracteres (máximo 72 bytes) y combinar '
            'al menos 3 tipos (minúsculas, mayúsculas, números o símbolos).'
        )

    # hash_password es idempotente: garantiza un único cifrado aunque el valor
    # ya pase después por los triggers de cifrado de PostgreSQL.
    password_cifrada = User.hash_password(password)
    if not User(
        id=objetivo.id,
        usuario=objetivo.usuario,
        correo=objetivo.correo,
        password=password_cifrada,
        rol_id=objetivo.rol_id,
    ).check_password(password):
        raise click.ClickException('No se pudo verificar el cifrado generado. Abortado.')

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                'UPDATE usuarios SET password = %s WHERE id = %s',
                (password_cifrada, objetivo.id)
            )
    click.echo(f'Contraseña de {objetivo.usuario} actualizada (un solo cifrado).')


@app.cli.command('auditar-passwords')
def auditar_passwords():
    """Lista las cuentas y el formato de su hash para detectar cifrado anidado."""
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            '''SELECT u.id, u.usuario, u.password
               FROM usuarios u ORDER BY u.id'''
        )
        filas = cursor.fetchall()
    conn.close()

    for fila in filas:
        hash_actual = fila['password'] or ''
        estado = 'OK' if es_hash_contrasena(hash_actual) else 'REVISAR'
        click.echo(
            f"id={fila['id']:>4}  {fila['usuario']:<24} "
            f"{hash_actual[:7]:<9} {estado}"
        )
    click.echo(f'Total de cuentas: {len(filas)}.')


def validar_nombre_persona(valor):
    """Valida que un nombre o apellido contenga solo letras y espacios."""
    if not valor:
        return False
    return bool(re.fullmatch(r'[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+', valor.strip()))


def validar_telefono_10_digitos(valor):
    """Valida que el teléfono tenga exactamente 10 dígitos numéricos."""
    if not valor:
        return False
    return bool(re.fullmatch(r'\d{10}', valor.strip()))


def registrar_log(accion, detalles=None):
    """Registra un evento en la tabla logs_actividad para auditoría de seguridad."""
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        user_name = current_user.usuario if current_user.is_authenticated else session.get('temp_user_nombre', 'Anónimo')
        ip = request.remote_addr or '127.0.0.1'
        ActivityLog.registrar(user_id, user_name, accion, ip, detalles)
    except Exception as e:
        app.logger.warning(f"Error registrando log de auditoría: {e}")


def role_required(*roles_permitidos):
    """
    Decorador para proteger rutas según los roles asignados al usuario actual.
    Si el usuario no está autenticado, redirige al login.
    Si no posee los roles permitidos, registra la denegación en la auditoría y redirige.
    """
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Por favor inicia sesión para acceder a esta página.', 'warning')
                return redirect(url_for('login', next=request.path))

            if current_user.rol_nombre not in roles_permitidos:
                registrar_log(
                    'ACCESO_DENEGADO_ROL',
                    f"Ruta: {request.path} | Rol actual: {current_user.rol_nombre} | Roles permitidos: {list(roles_permitidos)}"
                )
                flash(f'Acceso denegado: tu rol actual ({current_user.rol_nombre}) no tiene permisos para esta acción.', 'danger')
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)
        return wrapper
    return decorador


def permission_required(codigo_permiso):
    """
    Decorador para proteger rutas según la tabla relacional rol_permisos.
    Verifica que el rol asignado al usuario cuente con el permiso granular requerido.
    """
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Por favor inicia sesión para acceder a esta página.', 'warning')
                return redirect(url_for('login', next=request.path))

            if not current_user.has_permission(codigo_permiso):
                registrar_log(
                    'ACCESO_DENEGADO_PERMISO',
                    f"Ruta: {request.path} | Permiso requerido: {codigo_permiso} | Rol: {current_user.rol_nombre}"
                )
                flash('Acceso denegado: no dispones de los permisos granulares necesarios para esta operación.', 'danger')
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)
        return wrapper
    return decorador


# ==============================================================================
# RUTAS PÚBLICAS Y VISTAS GENERALES
# ==============================================================================

@app.route('/')
def inicio():
    """
    Portada pública de la pastelería.
    Renderiza la vista principal con información de la empresa y catálogo destacado.
    Accesible libremente para visitantes no autenticados y usuarios con sesión activa.
    Las cuentas con permiso pueden ver lanzamientos futuros; los visitantes solo
    ven productos disponibles.
    """
    mensaje = "Pasteles, tartas y postres artesanales preparados para compartir momentos especiales."
    empresa = {
        "nombre": "Dulce Delicia",
        "ubicacion": "Pedidos elaborados por encargo",
        "modalidad": "Atención personalizada"
    }
    categorias_producto = []
    productos_destacados = []
    base_datos_disponible = False
    puede_ver_futuros = False
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        base_datos_disponible = True
        puede_ver_futuros = puede_ver_productos_futuros(current_user)
        cursor.execute('''
            SELECT DISTINCT c.*
            FROM categorias_producto c
            JOIN productos p ON p.categoria_producto_id = c.id
            WHERE p.disponible = TRUE OR (%s = TRUE AND p.disponible = FALSE)
            ORDER BY c.nombre
        ''', (puede_ver_futuros,))
        categorias_producto = cursor.fetchall()

        # La portada muestra un máximo de seis productos visibles para la cuenta.
        cursor.execute('''
            SELECT p.*, c.nombre AS categoria_nombre,
                   COALESCE(v.unidades_vendidas, 0) AS unidades_solicitadas
            FROM productos p
            JOIN categorias_producto c ON p.categoria_producto_id = c.id
            LEFT JOIN (
                SELECT d.producto_id, SUM(d.cantidad) AS unidades_vendidas
                FROM detalle_factura d
                JOIN facturacion f ON f.numero = d.factura_numero
                WHERE f.tipo = 'Factura'
                GROUP BY d.producto_id
            ) v ON v.producto_id = p.id
            WHERE (p.disponible = TRUE OR (%s = TRUE AND p.disponible = FALSE))
              AND p.es_insumo = FALSE
            ORDER BY p.disponible DESC, unidades_solicitadas DESC, p.id ASC
            LIMIT 6
        ''', (puede_ver_futuros,))
        productos_destacados = cursor.fetchall()
        cursor.close()
        conn.close()
    except psycopg2.Error:
        app.logger.exception('No se pudo cargar el catálogo de la portada.')

    return render_template(
        'index.html',
        mensaje=mensaje,
        empresa=empresa,
        productos=productos_destacados,
        categorias_producto=categorias_producto,
        base_datos_disponible=base_datos_disponible
    )



# ==============================================================================
# MÓDULO DE AUTENTICACIÓN, REGISTRO Y SEGURIDAD
# ==============================================================================

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    """
    Ruta de registro de clientes con validaciones de seguridad y datos básicos.
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = UsuarioForm()
    try:
        roles_bd = Role.get_all()
    except Exception:
        app.logger.exception('No se pudieron cargar los roles durante el registro.')
        flash('No se pudo conectar con la base de datos. Revisa DATABASE_URL y los logs de Render.', 'danger')
        return render_template(
            '500.html',
            diagnostico='La base de datos no respondió al cargar los roles.'
        ), 503
    roles_registrables = roles_bd
    rol_cliente = next((r for r in roles_registrables if r['nombre'] == 'Cliente'), None)
    if rol_cliente is None:
        app.logger.error('No existe el rol Cliente en la base de datos.')
        return render_template('500.html', diagnostico='La base de datos no tiene configurado el rol de cliente.'), 503
    form.rol_id.choices = [(rol['id'], rol['nombre']) for rol in roles_registrables]
    if request.method == 'GET':
        form.rol_id.data = rol_cliente['id']

    def renderizar_registro(estado=200):
        session['registro_inicio'] = time.time()
        form.sitio_web.data = ''
        return render_template('registro.html', form=form), estado

    if request.method == 'GET':
        return renderizar_registro()

    if form.validate_on_submit():
        inicio_registro = session.pop('registro_inicio', None)
        if registro_es_automatizado(form.sitio_web.data, inicio_registro):
            app.logger.warning('Registro rechazado por la protección anti-automatización.')
            flash('No se pudo validar el envío. Recarga el formulario e inténtalo nuevamente.', 'danger')
            return renderizar_registro()

        usuario_limpio = form.usuario.data.strip()
        correo_limpio = form.correo.data.strip().lower()
        nombres_limpios = form.nombres.data.strip()
        apellidos_limpios = form.apellidos.data.strip()
        telefono_limpio = (form.telefono.data or '').strip()

        if not validar_nombre_persona(nombres_limpios):
            flash('Los nombres solo pueden contener letras y espacios.', 'danger')
            return renderizar_registro()

        if not validar_nombre_persona(apellidos_limpios):
            flash('Los apellidos solo pueden contener letras y espacios.', 'danger')
            return renderizar_registro()

        if not validar_telefono_10_digitos(telefono_limpio):
            flash('El teléfono debe contener exactamente 10 dígitos numéricos.', 'danger')
            return renderizar_registro()

        if not form.acepta_terminos.data:
            flash('Debes aceptar los Términos de uso para continuar.', 'danger')
            return renderizar_registro()

        if not form.acepta_tratamiento_datos.data:
            flash('Debes leer y aceptar el Aviso de Privacidad para continuar.', 'danger')
            return renderizar_registro()

        if not validar_password_segura(form.password.data):
            flash('La clave debe tener al menos 12 caracteres y combinar al menos 3 tipos de caracteres.', 'danger')
            return renderizar_registro()

        # La edad se calcula en el servidor: la casilla solo es la declaración.
        fecha_nacimiento = form.fecha_nacimiento.data
        es_mayor_edad = es_mayor_de_edad(fecha_nacimiento)
        if fecha_nacimiento is None:
            flash('Ingresa una fecha de nacimiento válida.', 'danger')
            return renderizar_registro()
        if not es_mayor_edad:
            flash('Solo pueden crear cuentas las personas mayores de edad.', 'danger')
            return renderizar_registro()

        if Usuario.get_by_usuario(usuario_limpio):
            flash('El nombre de usuario ya se encuentra registrado. Elige otro.', 'danger')
            return renderizar_registro()

        if Usuario.get_by_correo(correo_limpio):
            flash('Ya existe una cuenta con este correo electrónico. Inicia sesión o usa otro.', 'danger')
            return renderizar_registro()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT 1
               FROM information_schema.columns
               WHERE table_name = 'usuarios' AND column_name = 'telefono' '''
        )
        telefono_configurado = cursor.fetchone() is not None
        if not telefono_configurado:
            cursor.close()
            conn.close()
            flash('La base de datos aun no tiene configurado el campo de celular. Ejecuta la migracion indicada.', 'danger')
            return renderizar_registro(503)
        cursor.execute(
            'SELECT 1 FROM usuarios WHERE telefono = %s LIMIT 1',
            (telefono_limpio,)
        )
        telefono_repetido = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        if telefono_repetido:
            flash('Ya existe una cuenta con este número de celular. Usa otro.', 'danger')
            return renderizar_registro()

        rol_seleccionado = next(
            (rol for rol in roles_registrables if rol['id'] == form.rol_id.data),
            None
        )
        if rol_seleccionado is None:
            flash('Selecciona un perfil disponible para continuar.', 'danger')
            return renderizar_registro()
        rol_nombre = rol_seleccionado['nombre']
        aprobado = not rol_requiere_aprobacion(rol_nombre)
        password_hashed = User.hash_password(form.password.data)

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema = 'public' AND table_name = 'usuarios'
                     AND column_name = ANY(%s)""",
                ([
                    'nombres', 'apellidos', 'telefono', 'acepta_terminos',
                    'acepta_tratamiento_datos', 'fecha_consentimiento_datos',
                    'fecha_nacimiento', 'es_mayor_edad'
                ],)
            )
            columnas_extra = {row['column_name'] for row in cursor.fetchall()}
            columnas_consentimiento = {
                'acepta_tratamiento_datos', 'fecha_consentimiento_datos'
            }
            if not columnas_consentimiento.issubset(columnas_extra):
                raise RuntimeError(
                    'Falta aplicar sql/migracion_consentimiento_privacidad.sql antes de registrar usuarios.'
                )

            campos = ['usuario', 'correo', 'password', 'rol_id', 'activo', 'email_confirmado', 'aprobado', 'dos_factores_activo']
            valores = [usuario_limpio, correo_limpio, password_hashed, rol_seleccionado['id'], True, True, aprobado, False]

            if 'nombres' in columnas_extra:
                campos.append('nombres'); valores.append(nombres_limpios)
            if 'apellidos' in columnas_extra:
                campos.append('apellidos'); valores.append(apellidos_limpios)
            if 'telefono' in columnas_extra:
                campos.append('telefono'); valores.append(telefono_limpio)
            if 'fecha_nacimiento' in columnas_extra:
                campos.append('fecha_nacimiento'); valores.append(fecha_nacimiento)
            if 'es_mayor_edad' in columnas_extra:
                campos.append('es_mayor_edad'); valores.append(es_mayor_edad)
            if 'acepta_terminos' in columnas_extra:
                campos.append('acepta_terminos'); valores.append(True)
            campos.append('acepta_tratamiento_datos'); valores.append(True)
            campos.append('fecha_consentimiento_datos'); valores.append(datetime.now())

            placeholders = ', '.join(['%s'] * len(campos))
            columnas_sql = ', '.join(campos)
            sql = f'''INSERT INTO usuarios ({columnas_sql}) VALUES ({placeholders}) RETURNING id'''
            cursor.execute(sql, tuple(valores))
            nuevo_id = cursor.fetchone()['id']
            registrar_solicitud_acceso(cursor, nuevo_id, rol_seleccionado['id'], aprobado)
            conn.commit()
        except psycopg2.IntegrityError:
            if conn:
                conn.rollback()
            app.logger.exception('Registro rechazado por una restricción de PostgreSQL.')
            flash('No se pudo guardar: el usuario, correo o teléfono ya existe. Verifica los datos e inténtalo nuevamente.', 'danger')
            return renderizar_registro(409)
        except psycopg2.Error:
            if conn:
                conn.rollback()
            app.logger.exception('PostgreSQL falló al guardar un nuevo usuario.')
            flash('No se pudo guardar la información porque la base de datos no respondió. Inténtalo nuevamente en unos segundos.', 'danger')
            return renderizar_registro(503)
        except RuntimeError:
            if conn:
                conn.rollback()
            app.logger.exception('Falta la migración de consentimiento de privacidad.')
            flash('El registro no está disponible hasta actualizar el esquema de la base de datos.', 'danger')
            return renderizar_registro(503)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        ActivityLog.registrar(
            nuevo_id, usuario_limpio, 'REGISTRO_USUARIO',
            request.remote_addr, f"Rol solicitado: {rol_nombre} | Aprobado: {aprobado}"
        )

        if not aprobado:
            flash(
                f'La información se ha guardado correctamente. Es un gusto tenerte en Dulce Delicia, '
                f'{usuario_limpio}. Como solicitaste el rol de {rol_nombre}, un Administrador activo '
                'deberá aprobar tu acceso antes de poder iniciar sesión.',
                'warning'
            )
        else:
            flash(
                f'La información se ha guardado correctamente. Es un gusto tenerte en Dulce Delicia, '
                f'{usuario_limpio}. Tu cuenta con rol {rol_nombre} ya está lista; puedes iniciar sesión.',
                'success'
            )

        return redirect(url_for('login'))

    return renderizar_registro()


@app.route('/aviso-privacidad')
def aviso_privacidad():
    """Presenta la información de privacidad usada durante el registro."""
    return render_template('aviso_privacidad.html')


@app.route('/health')
def health():
    """Comprobación simple para Render: proceso web y PostgreSQL."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        cursor.execute(
            '''SELECT table_name
               FROM information_schema.tables
               WHERE table_schema = 'public'
                 AND table_name IN (
                     'roles', 'usuarios', 'clientes', 'productos',
                     'tipos_cliente', 'facturacion', 'detalle_factura', 'solicitudes',
                     'proveedores'
                 )'''
        )
        tablas = {fila['table_name'] for fila in cursor.fetchall()}
        tablas_requeridas = {
            'roles', 'usuarios', 'clientes', 'productos', 'tipos_cliente',
            'facturacion', 'detalle_factura', 'solicitudes', 'proveedores'
        }
        faltantes = sorted(tablas_requeridas - tablas)
        if faltantes:
            app.logger.error('Esquema incompleto. Faltan tablas: %s', ', '.join(faltantes))
            return {
                'status': 'error',
                'database': 'connected',
                'schema': 'incomplete',
                'missing_tables': faltantes
            }, 503

        cursor.execute(
            '''SELECT table_name, column_name
               FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND (
                     (table_name = 'solicitudes' AND column_name IN
                        ('estado', 'responsable_id', 'pedido_entregado', 'entregado_por_id', 'fecha_entrega'))
                     OR
                     (table_name = 'usuarios' AND column_name IN
                        ('activo', 'aprobado', 'rol_id', 'dos_factores_secreto',
                         'dos_factores_secreto_pendiente', 'dos_factores_intentos',
                         'dos_factores_bloqueo_hasta', 'dos_factores_ultimo_periodo'))
                     OR
                     (table_name = 'facturacion' AND column_name IN
                        ('fecha_entrega', 'modalidad_entrega', 'ubicacion_entrega'))
                 )'''
        )
        columnas = {(fila['table_name'], fila['column_name']) for fila in cursor.fetchall()}
        columnas_requeridas = {
            ('solicitudes', 'estado'),
            ('solicitudes', 'responsable_id'),
            ('solicitudes', 'pedido_entregado'),
            ('solicitudes', 'entregado_por_id'),
            ('solicitudes', 'fecha_entrega'),
            ('usuarios', 'activo'),
            ('usuarios', 'aprobado'),
            ('usuarios', 'rol_id'),
            ('usuarios', 'dos_factores_secreto'),
            ('usuarios', 'dos_factores_secreto_pendiente'),
            ('usuarios', 'dos_factores_intentos'),
            ('usuarios', 'dos_factores_bloqueo_hasta'),
            ('usuarios', 'dos_factores_ultimo_periodo'),
            ('facturacion', 'fecha_entrega'),
            ('facturacion', 'modalidad_entrega'),
            ('facturacion', 'ubicacion_entrega')
        }
        columnas_faltantes = sorted(
            f'{tabla}.{columna}'
            for tabla, columna in columnas_requeridas - columnas
        )
        if columnas_faltantes:
            app.logger.error(
                'Columnas requeridas ausentes: %s',
                ', '.join(columnas_faltantes)
            )
            return {
                'status': 'error',
                'database': 'connected',
                'schema': 'incomplete',
                'missing_columns': columnas_faltantes
            }, 503
        return {'status': 'ok', 'database': 'connected', 'schema': 'ready'}, 200
    except Exception:
        app.logger.exception('Healthcheck de PostgreSQL fallido.')
        return {
            'status': 'error',
            'database': 'unavailable',
            'configuration': (
                'Configura DATABASE_URL o DB_PASSWORD en el archivo .env '
                'de la raíz del proyecto.'
            )
        }, 503
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/registro/disponibilidad')
def disponibilidad_registro():
    """Comprueba en PostgreSQL si un usuario, correo o teléfono ya existe."""
    campo = (request.args.get('campo') or '').strip().lower()
    valor = (request.args.get('valor') or '').strip()
    columnas_permitidas = {
        'usuario': 'usuario',
        'correo': 'correo',
        'telefono': 'telefono',
    }
    columna = columnas_permitidas.get(campo)
    if not columna or not valor:
        return {'disponible': False, 'mensaje': 'Dato no válido.'}, 400

    if campo == 'correo':
        valor = valor.lower()
    elif campo == 'telefono':
        valor = re.sub(r'\D', '', valor)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT 1
               FROM information_schema.columns
               WHERE table_name = 'usuarios' AND column_name = %s''',
            (columna,)
        )
        if cursor.fetchone() is None:
            return {
                'disponible': False,
                'mensaje': 'Este campo aun no esta configurado en la base de datos.'
            }, 503
        cursor.execute(
            f'SELECT 1 FROM usuarios WHERE {columna} = %s LIMIT 1',
            (valor,)
        )
        existe = cursor.fetchone() is not None
        cursor.close()
        return {
            'disponible': not existe,
            'mensaje': (
                'Este dato ya está registrado.'
                if existe else 'Disponible.'
            ),
        }
    finally:
        conn.close()


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Ruta para el inicio de sesión de usuarios.
    Permite autenticarse por nombre de usuario o por correo electrónico.
    Verifica contraseñas seguras (Bcrypt con fallback a Werkzeug).
    Bloquea a usuarios con rol Administrador que aún no han sido aprobados por un Administrador activo.
    Gestiona flujo de 2FA si está habilitado y caducidad de sesión.
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        identificador = (form.usuario.data or '').strip()
        password = form.password.data or ''
        try:
            user = Usuario.get_by_identificador(identificador)
        except psycopg2.Error:
            app.logger.exception('No se pudo consultar el usuario durante el login.')
            flash('La base de datos de Render no está disponible en este momento. Espera unos segundos y vuelve a intentarlo.', 'warning')
            return render_template('login.html', form=form), 503

        # La identidad se busca por usuario/correo y la contraseña se verifica
        # contra su hash; nunca se compara la contraseña dentro de SQL.
        if user and user.check_password(password):
            # Validar si el usuario está activo
            if not user.activo:
                registrar_log('LOGIN_BLOQUEADO', f"Usuario inactivo: {user.usuario}")
                flash('Tu cuenta se encuentra temporalmente desactivada. Contacta al Administrador.', 'danger')
                return render_template('login.html', form=form)

            # Validar si el usuario requiere aprobación y aún no ha sido autorizado
            if not user.aprobado:
                registrar_log('LOGIN_PENDIENTE_APROBACION', f"Intento de acceso no aprobado ({user.rol_nombre}): {user.usuario}")
                flash(f'Tu solicitud de rol {user.rol_nombre} está pendiente de aprobación por un Administrador activo del sistema.', 'warning')
                return render_template('login.html', form=form)

            # Verificación en dos pasos (2FA) si está activada
            if user.dos_factores_activo:
                conn = None
                cur = None
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        'SELECT dos_factores_secreto FROM usuarios WHERE id = %s AND dos_factores_activo = TRUE',
                        (user.id,)
                    )
                    fila_2fa = cur.fetchone()
                    if not fila_2fa or not fila_2fa['dos_factores_secreto']:
                        raise RuntimeError('La cuenta tiene 2FA activo sin una semilla TOTP registrada.')
                    descifrar_secreto_totp(fila_2fa['dos_factores_secreto'])
                except (psycopg2.Error, RuntimeError, InvalidToken, ValueError):
                    app.logger.exception('No se pudo preparar TOTP para la cuenta %s.', user.id)
                    flash('No se pudo verificar la configuración de seguridad de tu cuenta. Contacta al administrador.', 'danger')
                    return render_template('login.html', form=form), 503
                finally:
                    if cur:
                        cur.close()
                    if conn:
                        conn.close()

                session['2fa_user_id'] = user.id
                session['2fa_remember'] = form.recordarme.data
                session['2fa_expira_en'] = (datetime.now() + timedelta(minutes=5)).timestamp()
                next_page = request.args.get('next', '')
                session['2fa_next'] = next_page if next_page.startswith('/') else ''
                registrar_log('SOLICITUD_2FA', f"Validación TOTP solicitada para {user.usuario}")
                flash('Ingresa el código actual de tu aplicación autenticadora.', 'info')
                return redirect(url_for('verificar_2fa'))

            # Inicio de sesión normal
            session.permanent = True
            login_user(user, remember=form.recordarme.data)
            registrar_log('LOGIN_EXITOSO', f"Inicio de sesión exitoso como {user.rol_nombre}")
            flash(f'¡Bienvenido/a al sistema, {user.usuario}!', 'success')
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard')
            return redirect(next_page)
        else:
            session['temp_user_nombre'] = identificador
            if user is None:
                # La cuenta no existe: la contraseña nunca se evaluó, así que se
                # informa del identificador para no hacer creer que la clave falla.
                app.logger.warning(
                    'Login rechazado: no existe una cuenta para el identificador=%s',
                    identificador.lower()
                )
                registrar_log('LOGIN_USUARIO_INEXISTENTE', f"Identificador no registrado: {identificador}")
                flash(
                    'No encontramos una cuenta con ese usuario o correo. '
                    'Revisa cómo lo escribiste o crea tu cuenta en el registro.',
                    'danger'
                )
            else:
                app.logger.warning(
                    'Login rechazado: contraseña incorrecta para la cuenta=%s',
                    user.usuario
                )
                registrar_log('LOGIN_FALLIDO', f"Contraseña incorrecta para: {identificador}")
                flash('La contraseña es incorrecta. Vuelve a escribirla con el mismo valor con el que te registraste.', 'danger')

    return render_template('login.html', form=form)


@app.route('/verificar-2fa', methods=['GET', 'POST'])
def verificar_2fa():
    """
    Valida un TOTP de aplicación autenticadora, con bloqueo y protección contra repetición.
    """
    user_id = session.get('2fa_user_id')
    expira_en = session.get('2fa_expira_en')
    if not user_id or not expira_en or datetime.now().timestamp() > float(expira_en):
        session.pop('2fa_user_id', None)
        session.pop('2fa_remember', None)
        session.pop('2fa_expira_en', None)
        session.pop('2fa_next', None)
        flash('No hay una sesión 2FA activa. Inicia sesión nuevamente.', 'warning')
        return redirect(url_for('login'))

    form = DosFactoresForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''SELECT dos_factores_activo, dos_factores_secreto,
                          dos_factores_intentos, dos_factores_bloqueo_hasta,
                          dos_factores_ultimo_periodo,
                          dos_factores_bloqueo_hasta > CURRENT_TIMESTAMP AS bloqueado,
                          CASE
                              WHEN dos_factores_bloqueo_hasta <= CURRENT_TIMESTAMP THEN 0
                              ELSE dos_factores_intentos
                          END AS intentos_actuales
                   FROM usuarios WHERE id = %s FOR UPDATE''',
                (user_id,)
            )
            fila = cursor.fetchone()
            if not fila or not fila['dos_factores_activo'] or not fila['dos_factores_secreto']:
                conn.rollback()
                flash('La configuración TOTP de esta cuenta ya no está activa. Inicia sesión nuevamente.', 'warning')
                return redirect(url_for('login'))

            if fila['bloqueado']:
                conn.rollback()
                flash('Se alcanzó el límite de intentos. Espera 10 minutos antes de probar de nuevo.', 'danger')
                return render_template('verificar_2fa.html', form=form), 429

            secreto = descifrar_secreto_totp(fila['dos_factores_secreto'])
            periodo = periodo_totp_valido(secreto, form.codigo.data.strip())
            ultimo_periodo = fila['dos_factores_ultimo_periodo']
            if periodo is None or (ultimo_periodo is not None and periodo <= ultimo_periodo):
                intentos = int(fila['intentos_actuales'] or 0) + 1
                cursor.execute(
                    '''UPDATE usuarios
                       SET dos_factores_intentos = %s,
                           dos_factores_bloqueo_hasta = CASE
                               WHEN %s >= 5 THEN CURRENT_TIMESTAMP + INTERVAL '10 minutes'
                               ELSE NULL
                           END
                       WHERE id = %s''',
                    (intentos, intentos, user_id)
                )
                conn.commit()
                mensaje = (
                    'Demasiados intentos. El acceso 2FA se bloqueó por 10 minutos.'
                    if intentos >= 5 else 'El código no es válido o ya fue utilizado. Revisa tu aplicación.'
                )
                flash(mensaje, 'danger')
                return render_template('verificar_2fa.html', form=form), 429 if intentos >= 5 else 200

            cursor.execute(
                '''UPDATE usuarios
                   SET dos_factores_intentos = 0,
                       dos_factores_bloqueo_hasta = NULL,
                       dos_factores_ultimo_periodo = %s
                   WHERE id = %s''',
                (periodo, user_id)
            )
            conn.commit()
        except (psycopg2.Error, RuntimeError, InvalidToken, ValueError):
            conn.rollback()
            app.logger.exception('No se pudo validar el código TOTP del usuario %s.', user_id)
            flash('No se pudo completar la validación de seguridad. Inténtalo nuevamente.', 'danger')
            return render_template('verificar_2fa.html', form=form), 503
        finally:
            cursor.close()
            conn.close()

        user = Usuario.get_by_id(user_id)
        if not user or not user.activo or not user.aprobado:
            session.clear()
            flash('La cuenta ya no está habilitada para iniciar sesión.', 'danger')
            return redirect(url_for('login'))

        recordar = session.get('2fa_remember', False)
        next_page = session.get('2fa_next') or url_for('dashboard')
        session.pop('2fa_user_id', None)
        session.pop('2fa_remember', None)
        session.pop('2fa_expira_en', None)
        session.pop('2fa_next', None)
        session.pop('temp_user_nombre', None)
        session.permanent = True
        login_user(user, remember=recordar)
        registrar_log('LOGIN_2FA_EXITOSO', f"TOTP validado para {user.usuario}")
        flash(f'Autenticación en dos pasos completada. Bienvenido/a, {user.usuario}.', 'success')
        return redirect(next_page if next_page.startswith('/') else url_for('dashboard'))

    return render_template('verificar_2fa.html', form=form)


@app.route('/mi-cuenta', methods=['GET', 'POST'])
@login_required
def mi_cuenta():
    """Perfil del usuario con datos personales, seguridad y resumen operativo."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS foto_perfil VARCHAR(255)')
    conn.commit()
    cur.close()
    conn.close()

    asegurada = False
    try:
        asegurar_inventario_base()
        asegurada = True
    except Exception:
        app.logger.exception('No se pudo asegurar la base de inventario del perfil.')

    form = MiCuentaForm()
    if request.method == 'POST':
        nombres = (form.nombres.data or '').strip()
        apellidos = (form.apellidos.data or '').strip()
        telefono = (form.telefono.data or '').strip()
        foto = form.foto_perfil.data
        error_formulario = None
        if not form.validate_on_submit():
            error_formulario = 'No pudimos validar el formulario. Recarga la página e inténtalo nuevamente.'
        elif not validar_nombre_persona(nombres):
            flash('Los nombres solo pueden incluir letras y espacios.', 'danger')
        elif not validar_nombre_persona(apellidos):
            flash('Los apellidos solo pueden incluir letras y espacios.', 'danger')
        elif telefono and not validar_telefono_10_digitos(telefono):
            flash('El teléfono debe tener 10 dígitos.', 'danger')
        else:
            foto_nueva = None
            archivo_nuevo = None
            if foto and foto.filename:
                try:
                    foto_nueva, archivo_nuevo = guardar_foto_perfil(foto, current_user.id)
                except ValueError as error:
                    flash(str(error), 'danger')
                else:
                    error_formulario = None

            if (not foto or not foto.filename or archivo_nuevo) and not error_formulario:
                conn = get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute('SELECT foto_perfil FROM usuarios WHERE id = %s', (current_user.id,))
                    foto_anterior = cur.fetchone()['foto_perfil']
                    cur.execute(
                        '''UPDATE usuarios
                           SET nombres = %s, apellidos = %s, telefono = %s, foto_perfil = %s
                           WHERE id = %s''',
                        (
                            nombres or None,
                            apellidos or None,
                            telefono or None,
                            foto_nueva or foto_anterior,
                            current_user.id,
                        )
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    if archivo_nuevo:
                        archivo_nuevo.unlink(missing_ok=True)
                    raise
                finally:
                    cur.close()
                    conn.close()
                if foto_nueva:
                    eliminar_foto_perfil(foto_anterior)
                flash('Tu perfil fue actualizado correctamente.', 'success')
                return redirect(url_for('mi_cuenta'))
        if error_formulario:
            flash(error_formulario, 'danger')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT u.*, r.nombre AS rol_nombre,
               COALESCE((SELECT COUNT(*) FROM facturacion f JOIN clientes c ON c.cedula = f.cliente_cedula WHERE LOWER(TRIM(c.correo)) = LOWER(TRIM(%s))), 0) AS documentos_totales,
               COALESCE((SELECT SUM(monto) FROM facturacion f JOIN clientes c ON c.cedula = f.cliente_cedula WHERE LOWER(TRIM(c.correo)) = LOWER(TRIM(%s))), 0) AS total_gastado
        FROM usuarios u
        LEFT JOIN roles r ON r.id = u.rol_id
        WHERE u.id = %s
    ''', (current_user.correo, current_user.correo, current_user.id))
    usuario_actual = cur.fetchone()
    cur.close(); conn.close()

    return render_template(
        'mi_cuenta.html',
        usuario=usuario_actual,
        stock_asegurado=asegurada,
        form=form
    )


def guardar_foto_perfil(archivo, usuario_id):
    """Valida y guarda una foto local normalizada para el perfil del usuario."""
    contenido = archivo.stream.read(5 * 1024 * 1024 + 1)
    if len(contenido) > 5 * 1024 * 1024:
        raise ValueError('La foto debe pesar como máximo 5 MB.')

    try:
        with Image.open(io.BytesIO(contenido)) as imagen:
            if imagen.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError('Elige una imagen JPG, PNG o WEBP.')
            if imagen.width * imagen.height > 20_000_000:
                raise ValueError('La imagen tiene demasiada resolución. Elige una foto más pequeña.')
            imagen.verify()
        with Image.open(io.BytesIO(contenido)) as imagen:
            imagen = ImageOps.exif_transpose(imagen).convert('RGB')
            imagen = ImageOps.fit(imagen, (512, 512))
            salida = io.BytesIO()
            imagen.save(salida, format='JPEG', quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError('No se pudo leer esa imagen. Elige un archivo JPG, PNG o WEBP válido.') from error

    nombre = f'usuario-{usuario_id}-{secrets.token_hex(16)}.jpg'
    carpeta = Path(app.config['PROFILE_UPLOAD_FOLDER'])
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_archivo = carpeta / nombre
    ruta_archivo.write_bytes(salida.getvalue())
    return f'uploads/perfiles/{nombre}', ruta_archivo


def eliminar_foto_perfil(ruta_relativa):
    """Elimina únicamente fotos generadas por esta función."""
    coincidencia = re.fullmatch(r'uploads/perfiles/usuario-\d+-[a-f0-9]{32}\.jpg', ruta_relativa or '')
    if coincidencia:
        (Path(app.config['PROFILE_UPLOAD_FOLDER']) / Path(ruta_relativa).name).unlink(missing_ok=True)


@app.route('/inventario')
@login_required
@role_required('Administrador', 'Encargado', 'Repostero')
def inventario():
    """Muestra un inventario mínimo de stock y movimientos de kardex."""
    asegurar_inventario_base()
    conn = get_db_connection(); cur = conn.cursor()
    por_pagina = 10
    cur.execute('SELECT COUNT(*) AS total FROM productos')
    total_productos = int(cur.fetchone()['total'])
    paginas_productos = max(1, (total_productos + por_pagina - 1) // por_pagina)
    pagina_productos = min(max(request.args.get('page', 1, type=int), 1), paginas_productos)
    cur.execute('SELECT COUNT(*) AS total FROM kardex_movimientos')
    total_movimientos = int(cur.fetchone()['total'])
    paginas_movimientos = max(1, (total_movimientos + por_pagina - 1) // por_pagina)
    pagina_movimientos = min(max(request.args.get('movement_page', 1, type=int), 1), paginas_movimientos)
    cur.execute('''
        SELECT p.id, p.nombre, c.nombre AS categoria, p.stock_actual, p.stock_minimo,
               p.precio_base, p.disponible, p.es_insumo,
               COALESCE((SELECT SUM(k.cantidad) FROM kardex_movimientos k WHERE k.producto_id = p.id AND k.tipo = 'salida'), 0) AS salidas,
               COALESCE((SELECT SUM(k.cantidad) FROM kardex_movimientos k WHERE k.producto_id = p.id AND k.tipo = 'entrada'), 0) AS entradas
        FROM productos p
        JOIN categorias_producto c ON c.id = p.categoria_producto_id
        ORDER BY c.nombre, p.nombre
        LIMIT %s OFFSET %s
    ''', (por_pagina, (pagina_productos - 1) * por_pagina))
    items = cur.fetchall()
    cur.execute('''
        SELECT k.*, p.nombre AS producto_nombre, u.usuario AS usuario_nombre
        FROM kardex_movimientos k
        JOIN productos p ON p.id = k.producto_id
        LEFT JOIN usuarios u ON u.id = k.usuario_id
        ORDER BY k.fecha DESC, k.id DESC
        LIMIT %s OFFSET %s
    ''', (por_pagina, (pagina_movimientos - 1) * por_pagina))
    movimientos = cur.fetchall()
    cur.execute('SELECT id, nombre, stock_actual, es_insumo FROM productos ORDER BY nombre')
    productos_movimiento = cur.fetchall()
    cur.close(); conn.close()
    return render_template(
        'inventario.html',
        items=items,
        productos_movimiento=productos_movimiento,
        movimientos=movimientos,
        pagina_productos=pagina_productos,
        paginas_productos=paginas_productos,
        pagina_movimientos=pagina_movimientos,
        paginas_movimientos=paginas_movimientos
    )


@app.route('/inventario/movimiento', methods=['POST'])
@login_required
@role_required('Administrador', 'Encargado', 'Repostero')
def registrar_movimiento_inventario():
    """Registra entradas y salidas de stock en el kardex."""
    asegurar_inventario_base()
    producto_id = request.form.get('producto_id', type=int)
    tipo = (request.form.get('tipo') or '').strip().lower()
    cantidad = request.form.get('cantidad', type=int)
    referencia = (request.form.get('referencia') or '').strip()
    descripcion = (request.form.get('descripcion') or '').strip()
    if not producto_id or tipo not in {'entrada', 'salida'} or not cantidad or cantidad <= 0:
        flash('Datos de inventario inválidos.', 'danger'); return redirect(url_for('inventario'))
    costo_unitario = None
    if tipo == 'entrada':
        costo_crudo = (request.form.get('costo_unitario') or '').strip().replace(',', '.')
        if costo_crudo:
            try:
                candidato = Decimal(costo_crudo)
            except InvalidOperation:
                candidato = None
            if candidato is not None and candidato >= 0:
                costo_unitario = candidato
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('SELECT stock_actual FROM productos WHERE id = %s FOR UPDATE', (producto_id,))
    producto = cur.fetchone()
    if not producto:
        cur.close(); conn.close(); flash('El producto no existe.', 'danger'); return redirect(url_for('inventario'))
    nuevo_stock = producto['stock_actual'] + cantidad if tipo == 'entrada' else producto['stock_actual'] - cantidad
    if nuevo_stock < 0:
        cur.close(); conn.close(); flash('No hay stock suficiente para registrar esa salida.', 'danger'); return redirect(url_for('inventario'))
    cur.execute('''
        INSERT INTO kardex_movimientos (producto_id, tipo, cantidad, referencia, descripcion, usuario_id, costo_unitario)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (producto_id, tipo, cantidad, referencia or None, descripcion or None, current_user.id, costo_unitario))
    cur.execute('UPDATE productos SET stock_actual = %s WHERE id = %s', (nuevo_stock, producto_id))
    conn.commit(); cur.close(); conn.close()
    registrar_log('MOVIMIENTO_INVENTARIO', f'{tipo.title()} de {cantidad} unidades para producto {producto_id}')
    flash('Movimiento de inventario registrado correctamente.', 'success')
    return redirect(url_for('inventario'))


@app.route('/inventario/movimiento/<int:movimiento_id>/editar', methods=['GET', 'POST'])
@login_required
@role_required('Administrador', 'Encargado')
def editar_movimiento_inventario(movimiento_id):
    """Permite corregir movimientos manuales sin habilitar la edición del kardex automático."""
    asegurar_inventario_base()
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute(
        '''SELECT k.*, p.nombre AS producto_nombre
           FROM kardex_movimientos k
           JOIN productos p ON p.id = k.producto_id
           WHERE k.id = %s
           FOR UPDATE OF k''',
        (movimiento_id,)
    )
    movimiento = cur.fetchone()
    if not movimiento:
        cur.close(); conn.close()
        flash('El movimiento seleccionado no existe.', 'danger')
        return redirect(url_for('inventario'))
    if movimiento['automatico']:
        cur.close(); conn.close()
        flash('Los movimientos automáticos de venta no se pueden editar.', 'warning')
        return redirect(url_for('inventario'))

    cur.execute('SELECT id, nombre FROM productos ORDER BY nombre')
    productos = cur.fetchall()
    if request.method == 'POST':
        producto_id = request.form.get('producto_id', type=int)
        tipo = (request.form.get('tipo') or '').strip().lower()
        cantidad = request.form.get('cantidad', type=int)
        referencia = (request.form.get('referencia') or '').strip()
        descripcion = (request.form.get('descripcion') or '').strip()
        costo_unitario = None
        if tipo == 'entrada':
            costo_crudo = (request.form.get('costo_unitario') or '').strip().replace(',', '.')
            if costo_crudo:
                try:
                    candidato = Decimal(costo_crudo)
                except InvalidOperation:
                    candidato = None
                if candidato is not None and candidato >= 0:
                    costo_unitario = candidato
        if not producto_id or tipo not in {'entrada', 'salida'} or not cantidad or cantidad <= 0:
            conn.rollback(); cur.close(); conn.close()
            flash('Datos de inventario inválidos.', 'danger')
            return redirect(url_for('editar_movimiento_inventario', movimiento_id=movimiento_id))

        ids_bloqueo = sorted({int(movimiento['producto_id']), producto_id})
        cur.execute(
            '''SELECT id, stock_actual FROM productos
               WHERE id = ANY(%s) ORDER BY id FOR UPDATE''',
            (ids_bloqueo,)
        )
        stocks = {row['id']: int(row['stock_actual']) for row in cur.fetchall()}
        if producto_id not in stocks or int(movimiento['producto_id']) not in stocks:
            conn.rollback(); cur.close(); conn.close()
            flash('El producto seleccionado ya no existe en el inventario.', 'danger')
            return redirect(url_for('inventario'))

        stock_por_producto = dict(stocks)
        cantidad_anterior = int(movimiento['cantidad'])
        efecto_anterior = cantidad_anterior if movimiento['tipo'] == 'entrada' else -cantidad_anterior
        stock_por_producto[movimiento['producto_id']] -= efecto_anterior
        efecto_nuevo = cantidad if tipo == 'entrada' else -cantidad
        stock_por_producto[producto_id] += efecto_nuevo
        if any(stock < 0 for stock in stock_por_producto.values()):
            conn.rollback(); cur.close(); conn.close()
            flash('El ajuste dejaría el stock por debajo de cero. Revisa la cantidad y el tipo de movimiento.', 'danger')
            return redirect(url_for('editar_movimiento_inventario', movimiento_id=movimiento_id))

        for id_producto, stock in stock_por_producto.items():
            cur.execute('UPDATE productos SET stock_actual = %s WHERE id = %s', (stock, id_producto))
        cur.execute(
            '''UPDATE kardex_movimientos
               SET producto_id = %s, tipo = %s, cantidad = %s, referencia = %s,
                   descripcion = %s, usuario_id = %s, costo_unitario = %s
               WHERE id = %s AND automatico = FALSE''',
            (producto_id, tipo, cantidad, referencia or None, descripcion or None,
             current_user.id, costo_unitario, movimiento_id)
        )
        if cur.rowcount != 1:
            conn.rollback(); cur.close(); conn.close()
            flash('El movimiento cambió mientras se editaba. Vuelve a intentarlo.', 'warning')
            return redirect(url_for('inventario'))

        conn.commit(); cur.close(); conn.close()
        registrar_log('EDITAR_MOVIMIENTO_INVENTARIO', f'Movimiento {movimiento_id} actualizado por {current_user.usuario}')
        flash('Movimiento de inventario actualizado correctamente.', 'success')
        return redirect(url_for('inventario'))

    cur.close(); conn.close()
    return render_template('formulario_movimiento_inventario.html', movimiento=movimiento, productos=productos)


@app.route('/kardex/<int:producto_id>')
@login_required
@role_required('Administrador', 'Encargado', 'Repostero')
def kardex_producto(producto_id):
    """Hoja kardex valorizada por producto o insumo con costo promedio ponderado."""
    asegurar_inventario_base()
    conn = get_db_connection(); cur = conn.cursor()
    cur.execute('''
        SELECT p.id, p.nombre, p.descripcion, p.stock_actual, p.stock_minimo, p.es_insumo,
               c.nombre AS categoria
        FROM productos p
        JOIN categorias_producto c ON c.id = p.categoria_producto_id
        WHERE p.id = %s
    ''', (producto_id,))
    producto = cur.fetchone()
    if not producto:
        cur.close(); conn.close()
        flash('El elemento solicitado no existe en el inventario.', 'danger')
        return redirect(url_for('inventario'))
    cur.execute('''
        SELECT k.*, u.usuario AS usuario_nombre
        FROM kardex_movimientos k
        LEFT JOIN usuarios u ON u.id = k.usuario_id
        WHERE k.producto_id = %s
        ORDER BY k.fecha ASC, k.id ASC
    ''', (producto_id,))
    movimientos = cur.fetchall()
    cur.close(); conn.close()
    filas, totales = calcular_kardex_valorizado(movimientos)
    return render_template('kardex_producto.html', producto=producto, filas=filas, totales=totales)


@app.route('/cuenta/seguridad/2fa', methods=['GET', 'POST'])
@app.route('/cuenta/seguridad', methods=['GET', 'POST'])
@login_required
def configurar_dos_factores():
    """Permite activar o desactivar TOTP con contraseña y, al desactivar, el TOTP actual."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion')
        try:
            if accion == 'cambiar_password':
                password_actual = request.form.get('password_actual') or ''
                password_nueva = request.form.get('password_nueva') or ''
                confirmar_password = request.form.get('confirmar_password') or ''
                cursor.execute(
                    'SELECT password FROM usuarios WHERE id = %s FOR UPDATE',
                    (current_user.id,)
                )
                fila_password = cursor.fetchone()
                if not fila_password:
                    conn.rollback()
                    flash('No se encontró la cuenta para actualizar la contraseña.', 'danger')
                    return redirect(url_for('configurar_dos_factores'))
                usuario_verificacion = User(
                    id=current_user.id,
                    usuario=current_user.usuario,
                    correo=current_user.correo,
                    password=fila_password['password'],
                    rol_id=current_user.rol_id,
                    rol_nombre=current_user.rol_nombre,
                )
                if not usuario_verificacion.check_password(password_actual):
                    conn.rollback()
                    flash('La contraseña actual no es correcta.', 'danger')
                elif not validar_password_segura(password_nueva):
                    conn.rollback()
                    flash(
                        'La nueva contraseña debe tener al menos 12 caracteres y combinar '
                        'al menos 3 tipos: minúsculas, mayúsculas, números o símbolos.',
                        'danger'
                    )
                elif password_nueva != confirmar_password:
                    conn.rollback()
                    flash('La confirmación no coincide con la nueva contraseña.', 'danger')
                elif usuario_verificacion.check_password(password_nueva):
                    conn.rollback()
                    flash('La nueva contraseña debe ser diferente de la actual.', 'warning')
                else:
                    password_cifrada = User.hash_password(password_nueva)
                    cursor.execute(
                        'UPDATE usuarios SET password = %s WHERE id = %s',
                        (password_cifrada, current_user.id)
                    )
                    conn.commit()
                    current_user.password = password_cifrada
                    registrar_log(
                        'CAMBIAR_PASSWORD',
                        f'La cuenta {current_user.usuario} actualizó su contraseña.'
                    )
                    flash('Tu contraseña se actualizó correctamente.', 'success')
                return redirect(url_for('configurar_dos_factores'))

            if accion == 'iniciar':
                cursor.execute(
                    'SELECT dos_factores_activo FROM usuarios WHERE id = %s FOR UPDATE',
                    (current_user.id,)
                )
                fila = cursor.fetchone()
                if not fila:
                    conn.rollback()
                    flash('No se encontró la cuenta para iniciar la configuración.', 'danger')
                    return redirect(url_for('configurar_dos_factores'))
                if fila['dos_factores_activo']:
                    conn.rollback()
                    flash('La autenticación en dos pasos ya está activada.', 'info')
                    return redirect(url_for('configurar_dos_factores'))

                secreto = generar_secreto_totp()
                secreto_cifrado = cifrar_secreto_totp(secreto)
                cursor.execute(
                    '''UPDATE usuarios SET dos_factores_secreto_pendiente = %s,
                           dos_factores_intentos = 0, dos_factores_bloqueo_hasta = NULL
                       WHERE id = %s''',
                    (secreto_cifrado, current_user.id)
                )
                conn.commit()
                registrar_log('INICIAR_CONFIGURACION_TOTP', f"Configuración TOTP iniciada por {current_user.usuario}")
                flash('Agrega la clave a tu aplicación autenticadora y confirma el código actual.', 'info')
                return redirect(url_for('configurar_dos_factores'))

            if accion == 'confirmar':
                cursor.execute(
                    '''SELECT dos_factores_secreto_pendiente, dos_factores_intentos,
                              dos_factores_bloqueo_hasta > CURRENT_TIMESTAMP AS bloqueado,
                              CASE
                                  WHEN dos_factores_bloqueo_hasta <= CURRENT_TIMESTAMP THEN 0
                                  ELSE dos_factores_intentos
                              END AS intentos_actuales
                       FROM usuarios WHERE id = %s FOR UPDATE''',
                    (current_user.id,)
                )
                fila = cursor.fetchone()
                if not fila or not fila['dos_factores_secreto_pendiente']:
                    conn.rollback()
                    flash('Primero inicia la configuración para generar una clave.', 'warning')
                    return redirect(url_for('configurar_dos_factores'))
                if fila['bloqueado']:
                    conn.rollback()
                    flash('Se alcanzó el límite de intentos. Espera 10 minutos antes de confirmar de nuevo.', 'danger')
                    return redirect(url_for('configurar_dos_factores'))
                secreto = descifrar_secreto_totp(fila['dos_factores_secreto_pendiente'])
                periodo = periodo_totp_valido(secreto, (request.form.get('codigo') or '').strip())
                if periodo is None:
                    intentos = int(fila['intentos_actuales'] or 0) + 1
                    cursor.execute(
                        '''UPDATE usuarios
                           SET dos_factores_intentos = %s,
                               dos_factores_bloqueo_hasta = CASE
                                   WHEN %s >= 5 THEN CURRENT_TIMESTAMP + INTERVAL '10 minutes'
                                   ELSE NULL
                               END
                           WHERE id = %s''',
                        (intentos, intentos, current_user.id)
                    )
                    conn.commit()
                    flash('El código no coincide. Revisa la hora del teléfono y vuelve a intentarlo.', 'danger')
                    return redirect(url_for('configurar_dos_factores'))
                cursor.execute(
                    '''UPDATE usuarios
                       SET dos_factores_activo = TRUE,
                           dos_factores_secreto = dos_factores_secreto_pendiente,
                           dos_factores_secreto_pendiente = NULL,
                           dos_factores_ultimo_periodo = %s,
                           dos_factores_intentos = 0,
                           dos_factores_bloqueo_hasta = NULL
                       WHERE id = %s''',
                    (periodo, current_user.id)
                )
                conn.commit()
                registrar_log('ACTIVAR_TOTP', f"Autenticación TOTP activada por {current_user.usuario}")
                flash('La autenticación en dos pasos quedó activada.', 'success')
                return redirect(url_for('configurar_dos_factores'))

            if accion == 'desactivar':
                password = request.form.get('password') or ''
                codigo = (request.form.get('codigo') or '').strip()
                cursor.execute(
                    '''SELECT password, dos_factores_activo, dos_factores_secreto,
                              dos_factores_ultimo_periodo
                       FROM usuarios WHERE id = %s FOR UPDATE''',
                    (current_user.id,)
                )
                fila = cursor.fetchone()
                if not fila or not fila['dos_factores_activo'] or not fila['dos_factores_secreto']:
                    conn.rollback()
                    flash('La autenticación en dos pasos no está activa.', 'info')
                    return redirect(url_for('configurar_dos_factores'))
                secreto = descifrar_secreto_totp(fila['dos_factores_secreto'])
                periodo = periodo_totp_valido(secreto, codigo)
                if not current_user.check_password(password) or periodo is None:
                    conn.rollback()
                    flash('La contraseña o el código de la aplicación no son correctos.', 'danger')
                    return redirect(url_for('configurar_dos_factores'))
                if fila['dos_factores_ultimo_periodo'] is not None and periodo <= fila['dos_factores_ultimo_periodo']:
                    conn.rollback()
                    flash('Ese código ya se utilizó. Espera al siguiente código de tu aplicación.', 'danger')
                    return redirect(url_for('configurar_dos_factores'))
                cursor.execute(
                    '''UPDATE usuarios
                       SET dos_factores_activo = FALSE,
                           dos_factores_secreto = NULL,
                           dos_factores_secreto_pendiente = NULL,
                           dos_factores_intentos = 0,
                           dos_factores_bloqueo_hasta = NULL,
                           dos_factores_ultimo_periodo = NULL
                       WHERE id = %s''',
                    (current_user.id,)
                )
                conn.commit()
                registrar_log('DESACTIVAR_TOTP', f"Autenticación TOTP desactivada por {current_user.usuario}")
                flash('La autenticación en dos pasos se desactivó.', 'success')
                return redirect(url_for('configurar_dos_factores'))

            conn.rollback()
            flash('La acción de seguridad solicitada no es válida.', 'danger')
        except (psycopg2.Error, RuntimeError, InvalidToken, ValueError):
            conn.rollback()
            app.logger.exception('Falló la gestión TOTP de la cuenta %s.', current_user.id)
            flash('No se pudo actualizar la autenticación en dos pasos. Verifica la clave de cifrado y vuelve a intentarlo.', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('configurar_dos_factores'))

    try:
        cursor.execute(
            '''SELECT dos_factores_activo, dos_factores_secreto_pendiente
               FROM usuarios WHERE id = %s''',
            (current_user.id,)
        )
        fila = cursor.fetchone()
        if not fila:
            flash('No se encontró la cuenta de usuario.', 'danger')
            return redirect(url_for('dashboard'))
        secreto_pendiente = (
            descifrar_secreto_totp(fila['dos_factores_secreto_pendiente'])
            if fila['dos_factores_secreto_pendiente'] else None
        )
        return render_template(
            'configurar_2fa.html',
            activo=fila['dos_factores_activo'],
            secreto=secreto_pendiente,
            uri=uri_configuracion_totp(secreto_pendiente, current_user.usuario) if secreto_pendiente else None
        )
    except (psycopg2.Error, RuntimeError, InvalidToken, ValueError):
        app.logger.exception('No se pudo cargar la configuración TOTP del usuario %s.', current_user.id)
        flash('No se pudo cargar la configuración de seguridad. Revisa TOTP_ENCRYPTION_KEY y la conexión.', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()


@app.route('/confirmar-correo/<token>')
def confirmar_correo(token):
    """
    Simulación de confirmación de correo electrónico.
    """
    user = Usuario.get_by_usuario_o_correo(token)
    if user:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE usuarios SET email_confirmado = TRUE WHERE id = %s', (user.id,))
        conn.commit()
        cur.close()
        conn.close()
        registrar_log('EMAIL_CONFIRMADO', f"Correo confirmado para {user.usuario}")
        flash('¡Tu dirección de correo ha sido confirmada con éxito!', 'success')
    else:
        flash('Token o enlace de confirmación inválido.', 'danger')
    return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    """
    Ruta para el cierre de sesión seguro.
    Registra el evento en auditoría, destruye la sesión con logout_user y redirige al login.
    """
    registrar_log('LOGOUT', f'Sesión cerrada por {current_user.usuario}')
    logout_user()
    flash('Has cerrado sesión correctamente. ¡Hasta pronto!', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Panel administrativo principal protegido por autenticación.
    Muestra métricas globales y accesos rápidos adaptados al rol del usuario.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    es_cliente = current_user.rol_nombre == 'Cliente'
    puede_ver_cartera = current_user.has_role('Administrador', 'Encargado', 'Vendedor')
    puede_ver_facturacion_global = current_user.has_role(
        'Administrador', 'Encargado', 'Vendedor'
    )
    puede_ver_proveedores = current_user.has_role('Administrador', 'Repostero')

    if not puede_ver_cartera:
        total_clientes = 0
    else:
        cursor.execute('SELECT COUNT(*) AS total FROM clientes')
        total_clientes = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) AS total FROM productos WHERE es_insumo = FALSE')
    total_productos = cursor.fetchone()['total']

    if es_cliente:
        cursor.execute('''
            SELECT COUNT(*) AS total
            FROM facturacion f
            JOIN clientes c ON f.cliente_cedula = c.cedula
            WHERE LOWER(TRIM(c.correo)) = LOWER(TRIM(%s))
               OR c.cedula = %s
        ''', (current_user.correo, current_user.usuario))
        total_facturas = cursor.fetchone()['total']
    elif puede_ver_facturacion_global:
        cursor.execute('SELECT COUNT(*) AS total FROM facturacion')
        total_facturas = cursor.fetchone()['total']
    else:
        total_facturas = 0

    if puede_ver_proveedores:
        cursor.execute('SELECT COUNT(*) AS total FROM proveedores')
        total_proveedores = cursor.fetchone()['total']
    else:
        total_proveedores = 0

    # Si es Cliente, muestra únicamente sus propios documentos comerciales
    if es_cliente:
        cursor.execute('''
            SELECT f.*, c.nombre AS cliente_nombre, e.nombre AS estado_nombre
            FROM facturacion f
            JOIN clientes c ON f.cliente_cedula = c.cedula
            JOIN estados_documento e ON f.estado_id = e.id
            WHERE LOWER(TRIM(c.correo)) = LOWER(TRIM(%s))
               OR c.cedula = %s
            ORDER BY f.fecha DESC, f.numero DESC
            LIMIT 5
        ''', (current_user.correo, current_user.usuario))
        ultimas_facturas = cursor.fetchall()
    elif puede_ver_facturacion_global:
        # Consulta general para administración y personal autorizado.
        cursor.execute('''
            SELECT f.*, c.nombre AS cliente_nombre, e.nombre AS estado_nombre
            FROM facturacion f
            JOIN clientes c ON f.cliente_cedula = c.cedula
            JOIN estados_documento e ON f.estado_id = e.id
            ORDER BY f.fecha DESC, f.numero DESC
            LIMIT 5
        ''')
        ultimas_facturas = cursor.fetchall()
    else:
        ultimas_facturas = []

    cursor.close()
    conn.close()

    return render_template(
        'dashboard.html',
        total_clientes=total_clientes,
        total_productos=total_productos,
        total_facturas=total_facturas,
        total_proveedores=total_proveedores,
        ultimas_facturas=ultimas_facturas
    )


# ==============================================================================
# MÓDULO EXCLUSIVO DE ADMINISTRACIÓN (RBAC & AUDITORÍA)
# ==============================================================================

@app.route('/admin/usuarios')
@login_required
@role_required('Administrador')
def admin_usuarios():
    """
    Panel de gestión de cuentas y roles de usuario.
    Permite autorizar nuevas solicitudes de rol Administrador y reasignar roles.
    Muestra la matriz de permisos granulares asociada en la tabla rol_permisos.
    """
    usuarios = Usuario.get_all()
    roles = Role.get_all()
    solicitudes = Usuario.get_solicitudes_acceso()
    matriz_permisos = Usuario.matriz_permisos()

    # Se agrupa la matriz rol x permiso para pintar la consola de activación.
    permisos_por_rol = {}
    catalogo_permisos = {}
    for fila in matriz_permisos:
        permisos_por_rol.setdefault(fila['rol_nombre'], []).append({
            'codigo': fila['permiso_codigo'],
            'descripcion': fila['descripcion'],
            'activo': fila['permiso_activo'],
            'asignado': fila['asignado'],
        })
        catalogo_permisos[fila['permiso_codigo']] = {
            'codigo': fila['permiso_codigo'],
            'descripcion': fila['descripcion'],
            'activo': fila['permiso_activo'],
        }

    return render_template(
        'admin_usuarios.html',
        usuarios=usuarios,
        roles=roles,
        solicitudes=solicitudes,
        permisos_por_rol=permisos_por_rol,
        catalogo_permisos=list(catalogo_permisos.values())
    )


@app.route('/admin/permisos', methods=['POST'])
@login_required
@role_required('Administrador')
def admin_definir_permiso():
    """
    Activa o desactiva un permiso y lo concede o revoca a un rol.

    Escribe en las mismas tablas que usa el panel de PostgreSQL
    (`permisos` y `rol_permisos`), por lo que el cambio es visible desde ambos
    lados sin pasos adicionales.
    """
    codigo = (request.form.get('permiso') or '').strip()
    rol_nombre = (request.form.get('rol') or '').strip() or None

    if request.form.get('accion') == 'activar':
        activo = request.form.get('activo') == '1'
        if not codigo:
            flash('Indica el permiso que quieres activar.', 'danger')
            return redirect(url_for('admin_usuarios'))
        try:
            Usuario.definir_permiso(codigo, activo=activo)
        except ValueError as error:
            flash(str(error), 'danger')
            return redirect(url_for('admin_usuarios'))
        registrar_log(
            'ACTIVAR_PERMISO',
            f"El administrador {current_user.usuario} {'activó' if activo else 'desactivó'} el permiso {codigo}"
        )
        flash(
            f'El permiso {codigo} quedó {"activo" if activo else "desactivado"} para toda la aplicación.',
            'success' if activo else 'warning'
        )
        return redirect(url_for('admin_usuarios'))

    asignado = request.form.get('asignado') == '1'
    if not codigo or not rol_nombre:
        flash('Indica el permiso y el rol que quieres modificar.', 'danger')
        return redirect(url_for('admin_usuarios'))
    try:
        Usuario.definir_permiso(codigo, rol_nombre=rol_nombre, asignado=asignado)
    except ValueError as error:
        flash(str(error), 'danger')
        return redirect(url_for('admin_usuarios'))

    registrar_log(
        'ASIGNAR_PERMISO' if asignado else 'REVOCAR_PERMISO',
        f"El administrador {current_user.usuario} "
        f"{'asignó' if asignado else 'revocó'} el permiso {codigo} al rol {rol_nombre}"
    )
    flash(
        f'El permiso {codigo} fue {"asignado a" if asignado else "revocado de"} {rol_nombre}.',
        'success'
    )
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/aprobar-usuario/<int:id>', methods=['POST'])
@login_required
@role_required('Administrador')
def admin_aprobar_usuario(id):
    """
    Aprueba la solicitud de acceso pendiente de un perfil del equipo.
    Solo puede autorizarla un administrador activo del sistema.
    """
    user = Usuario.get_by_id(id)
    if not user:
        flash('El usuario indicado no existe.', 'danger')
        return redirect(url_for('admin_usuarios'))
    if user.aprobado:
        flash(f'La cuenta de {user.usuario} ya está aprobada.', 'info')
        return redirect(url_for('admin_usuarios'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'UPDATE usuarios SET aprobado = TRUE, activo = TRUE WHERE id = %s AND aprobado = FALSE',
        (id,)
    )
    aprobada = cur.rowcount == 1
    if aprobada:
        cur.execute(
            '''UPDATE solicitudes_acceso
               SET estado = 'Aprobada', fecha_decision = %s, decidido_por = %s, motivo = NULL
               WHERE usuario_id = %s''',
            (datetime.now(), current_user.usuario, id)
        )
    conn.commit()
    cur.close()
    conn.close()

    if not aprobada:
        flash(f'La solicitud de {user.usuario} ya no está pendiente.', 'info')
        return redirect(url_for('admin_usuarios'))

    registrar_log(
        'APROBAR_SOLICITUD_ROL',
        f"El administrador {current_user.usuario} aprobó el rol {user.rol_nombre} para {user.usuario}"
    )
    flash(
        f'La cuenta de {user.usuario} fue aprobada para el rol {user.rol_nombre}. Ya puede iniciar sesión.',
        'success'
    )
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/rechazar-usuario/<int:id>', methods=['POST'])
@login_required
@role_required('Administrador')
def admin_rechazar_usuario(id):
    """
    Rechaza la solicitud de acceso y deja constancia del motivo.
    La cuenta queda desactivada para que no pueda iniciar sesión.
    """
    user = Usuario.get_by_id(id)
    if not user:
        flash('El usuario indicado no existe.', 'danger')
        return redirect(url_for('admin_usuarios'))
    if user.id == current_user.id:
        flash('No puedes rechazar tu propia cuenta.', 'danger')
        return redirect(url_for('admin_usuarios'))
    if user.aprobado:
        flash(f'La cuenta de {user.usuario} ya está aprobada. Desactívala si quieres revocarla.', 'info')
        return redirect(url_for('admin_usuarios'))

    motivo = (request.form.get('motivo') or '').strip() or 'No cumple con los requisitos de acceso.'

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'UPDATE usuarios SET aprobado = FALSE, activo = FALSE WHERE id = %s',
        (id,)
    )
    cur.execute(
        '''UPDATE solicitudes_acceso
           SET estado = 'Rechazada', fecha_decision = %s, decidido_por = %s, motivo = %s
           WHERE usuario_id = %s''',
        (datetime.now(), current_user.usuario, motivo, id)
    )
    conn.commit()
    cur.close()
    conn.close()

    registrar_log(
        'RECHAZAR_SOLICITUD_ROL',
        f"El administrador {current_user.usuario} rechazó el rol {user.rol_nombre} de {user.usuario}. Motivo: {motivo}"
    )
    flash(f'La solicitud de {user.usuario} fue rechazada y quedó registrada.', 'warning')
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/cambiar-rol/<int:id>', methods=['POST'])
@login_required
@role_required('Administrador')
def admin_cambiar_rol(id):
    """
    Modifica el rol asignado a un usuario existente en PostgreSQL.
    """
    nuevo_rol_id = request.form.get('nuevo_rol_id', type=int)
    if not nuevo_rol_id:
        flash('Rol inválido.', 'danger')
        return redirect(url_for('admin_usuarios'))

    rol_obj = Role.get_by_id(nuevo_rol_id)
    if not rol_obj:
        flash('El rol seleccionado no es válido.', 'danger')
        return redirect(url_for('admin_usuarios'))

    user = Usuario.get_by_id(id)
    if not user:
        flash('El usuario no existe.', 'danger')
        return redirect(url_for('admin_usuarios'))

    conn = get_db_connection()
    cur = conn.cursor()
    # Si un Administrador activo le asigna el rol Administrador, queda aprobado automáticamente
    cur.execute('UPDATE usuarios SET rol_id = %s, aprobado = TRUE WHERE id = %s', (nuevo_rol_id, id))
    conn.commit()
    cur.close()
    conn.close()

    registrar_log('CAMBIO_ROL', f"El administrador {current_user.usuario} cambió el rol de {user.usuario} a {rol_obj['nombre']}")
    flash(f'Rol de {user.usuario} actualizado exitosamente a {rol_obj["nombre"]}.', 'success')
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/restablecer-password/<int:id>', methods=['POST'])
@login_required
@role_required('Administrador')
def admin_restablecer_password(id):
    """Genera una contraseña temporal para una cuenta sin usar correo electrónico."""
    user = Usuario.get_by_id(id)
    if not user:
        flash('El usuario no existe.', 'danger')
        return redirect(url_for('admin_usuarios'))

    password_temporal = f"Dulce-{secrets.token_urlsafe(6)}!"
    password_hashed = User.hash_password(password_temporal)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        '''UPDATE usuarios
           SET password = %s
           WHERE id = %s''',
        (password_hashed, id)
    )
    conn.commit()
    cur.close()
    conn.close()

    registrar_log(
        'RESTABLECER_PASSWORD',
        f'El administrador {current_user.usuario} generó una contraseña temporal para {user.usuario}'
    )
    flash(
        f'Contraseña temporal para {user.usuario}: {password_temporal}. '
        'Entrégala de forma privada y solicita cambiarla después de iniciar sesión.',
        'warning'
    )
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/logs')
@login_required
@role_required('Administrador')
def admin_logs():
    """
    Visualiza el registro histórico de auditoría de actividad del sistema.
    """
    filtros = {
        'fecha_desde': request.args.get('fecha_desde', '').strip(),
        'fecha_hasta': request.args.get('fecha_hasta', '').strip(),
        'hora_desde': request.args.get('hora_desde', '').strip(),
        'hora_hasta': request.args.get('hora_hasta', '').strip(),
        'persona': request.args.get('persona', '').strip(),
        'accion': request.args.get('accion', '').strip(),
        'ip': request.args.get('ip', '').strip(),
        'detalles': request.args.get('detalles', '').strip(),
    }
    for nombre_filtro, formato in (
        ('fecha_desde', '%Y-%m-%d'),
        ('fecha_hasta', '%Y-%m-%d'),
        ('hora_desde', '%H:%M'),
        ('hora_hasta', '%H:%M'),
    ):
        valor = filtros[nombre_filtro]
        if valor:
            try:
                datetime.strptime(valor, formato)
            except ValueError:
                filtros[nombre_filtro] = ''
                flash(f'El filtro {nombre_filtro.replace("_", " ")} no es válido.', 'warning')
    logs = ActivityLog.buscar(**filtros)
    acciones_disponibles = ActivityLog.acciones_disponibles()
    return render_template(
        'admin_logs.html',
        logs=logs,
        filtros=filtros,
        acciones_disponibles=acciones_disponibles
    )


@app.route('/solicitudes', methods=['GET'])
@login_required
@role_required('Administrador', 'Encargado', 'Repostero')
def solicitudes():
    """Muestra pedidos de clientes y permite organizar preparación y entrega."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if current_user.rol_nombre == 'Repostero':
        cursor.execute('''
            SELECT s.*, u.usuario AS responsable_nombre,
                   r.usuario AS entregado_por_nombre
            FROM solicitudes s
            LEFT JOIN usuarios u ON u.id = s.responsable_id
            LEFT JOIN usuarios r ON r.id = s.entregado_por_id
            WHERE s.responsable_id = %s
            ORDER BY s.fecha DESC, s.id DESC
        ''', (current_user.id,))
    else:
        cursor.execute('''
            SELECT s.*, u.usuario AS responsable_nombre,
                   r.usuario AS entregado_por_nombre
            FROM solicitudes s
            LEFT JOIN usuarios u ON u.id = s.responsable_id
            LEFT JOIN usuarios r ON r.id = s.entregado_por_id
            ORDER BY s.fecha DESC, s.id DESC
        ''')
    solicitudes_registradas = cursor.fetchall()
    cursor.execute('''
        SELECT u.id, u.usuario
        FROM usuarios u
        JOIN roles r ON r.id = u.rol_id
        WHERE u.activo = TRUE
          AND r.nombre IN ('Administrador', 'Encargado', 'Repostero', 'Vendedor')
        ORDER BY u.usuario
    ''')
    responsables = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        'solicitudes.html',
        solicitudes=solicitudes_registradas,
        responsables=responsables
    )


@app.route('/api/solicitudes', methods=['POST'])
def crear_solicitud():
    """Registra una petición pública directamente en PostgreSQL."""
    datos = request.get_json(silent=True) or request.form
    nombre = (datos.get('nombre') or '').strip()
    correo = (datos.get('correo') or '').strip().lower()
    telefono = (datos.get('telefono') or '').strip()
    tipo_producto = (datos.get('tipo_producto') or '').strip()
    mensaje = (datos.get('mensaje') or '').strip()

    correo_valido = re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]{2,}', correo)
    nombre_valido = re.fullmatch(
        r"[^\W\d_]+(?:[ .'-][^\W\d_]+)*",
        nombre,
        flags=re.UNICODE
    )
    telefono_valido = re.fullmatch(r'\d{10}', telefono)
    if (
        not nombre_valido or len(nombre) < 4 or len(nombre) > 150
        or not correo_valido or len(correo) > 150
        or not telefono_valido or len(tipo_producto) < 2
        or len(mensaje) < 10 or len(mensaje) > 5000
    ):
        return {
            'ok': False,
            'mensaje': 'Revisa nombre, correo, teléfono obligatorio de 10 números, producto y descripción.'
        }, 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # La solicitud queda relacionada con la categoría del producto, con la
        # cuenta del solicitante si está registrado y con el usuario que la envía.
        cursor.execute('SELECT id FROM categorias_producto WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))',
                       (tipo_producto,))
        categoria = cursor.fetchone()
        cursor.execute('SELECT id FROM usuarios WHERE LOWER(TRIM(correo)) = LOWER(TRIM(%s))',
                       (correo,))
        solicitante = cursor.fetchone()
        solicitante_id = solicitante['id'] if solicitante else None
        remitente_id = current_user.id if current_user.is_authenticated else None
        cursor.execute('''
            INSERT INTO solicitudes (nombre, correo, telefono, tipo_producto, mensaje,
                                     usuario_id, categoria_producto_id, responsable_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (nombre, correo, telefono, tipo_producto, mensaje,
              solicitante_id, categoria['id'] if categoria else None, remitente_id))
        solicitud_id = cursor.fetchone()['id']
        conn.commit()
        return {'ok': True, 'id': solicitud_id}, 201
    except psycopg2.Error as error:
        if conn:
            conn.rollback()
        app.logger.exception('No se pudo guardar la solicitud en PostgreSQL.')
        if getattr(error, 'pgcode', None) == '42P01':
            mensaje_error = 'La tabla solicitudes no existe en la base de datos conectada.'
        elif getattr(error, 'pgcode', None) == '42703':
            mensaje_error = 'La tabla solicitudes no tiene una columna requerida por la aplicación.'
        else:
            mensaje_error = 'La base de datos rechazó la solicitud. Revisa la conexión y el esquema.'
        return {
            'ok': False,
            'mensaje': mensaje_error
        }, 503
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/solicitudes/<int:id>/actualizar', methods=['POST'])
@login_required
@role_required('Administrador', 'Encargado', 'Repostero')
def actualizar_solicitud(id):
    """Actualiza el estado, la asignación y la entrega de un pedido."""
    estado = (request.form.get('estado') or '').strip()
    responsable_id = request.form.get('responsable_id', type=int)
    respuesta_cliente = (request.form.get('respuesta_cliente') or '').strip()
    estados_validos = {
        'Pendiente', 'Confirmado', 'En preparación', 'Listo para retiro',
        'En reparto', 'Entregada', 'Cancelada'
    }
    if estado not in estados_validos:
        flash('El estado seleccionado no es válido.', 'danger')
        return redirect(url_for('solicitudes'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT responsable_id FROM solicitudes WHERE id = %s', (id,))
    solicitud_actual = cursor.fetchone()
    if not solicitud_actual:
        cursor.close()
        conn.close()
        flash('La solicitud no existe.', 'danger')
        return redirect(url_for('solicitudes'))
    if current_user.rol_nombre == 'Repostero' and solicitud_actual['responsable_id'] != current_user.id:
        cursor.close()
        conn.close()
        flash('Solo puedes actualizar pedidos asignados a tu usuario.', 'danger')
        return redirect(url_for('solicitudes'))
    if current_user.rol_nombre == 'Repostero':
        responsable_id = current_user.id
    cursor.execute('''
        UPDATE solicitudes
        SET estado = %s, responsable_id = %s,
            respuesta_cliente = %s, pedido_entregado = %s,
            entregado_por_id = CASE
                WHEN %s = 'Entregada' THEN %s
                ELSE NULL
            END,
            fecha_entrega = CASE
                WHEN %s = 'Entregada' THEN COALESCE(fecha_entrega, CURRENT_TIMESTAMP)
                ELSE NULL
            END
        WHERE id = %s
    ''', (
        estado, responsable_id or None, respuesta_cliente or None,
        estado == 'Entregada', estado, current_user.id, estado, id
    ))
    if cursor.rowcount == 0:
        conn.rollback()
        cursor.close()
        conn.close()
        flash('La solicitud no existe.', 'danger')
        return redirect(url_for('solicitudes'))
    conn.commit()
    cursor.close()
    conn.close()
    registrar_log('ACTUALIZAR_SOLICITUD', f'Solicitud {id}: {estado}, responsable {responsable_id or "sin asignar"}')
    flash('La solicitud fue actualizada correctamente.', 'success')
    return redirect(url_for('solicitudes'))


# ==============================================================================
# MÓDULOS DE ADMINISTRACIÓN Y GESTIÓN CRUD (Protegidos por Roles y Permisos RBAC)
# ==============================================================================

@app.route('/productos')
def productos():
    """
    Ruta del catálogo completo de productos (Pública para consulta y lectura).
    Visitantes ven solo productos disponibles; cuentas con el permiso correspondiente
    también pueden consultar los próximos lanzamientos.
    Usa JOIN para mostrar el nombre de la categoría de cada producto.
    Soporta motor de búsqueda multicriterio (por nombre, descripción y categoría)
    tanto por parámetros URL (?q=...&tipo=...) como en tiempo real vía JavaScript.
    """
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '').strip()

    categorias_producto = []
    lista_productos = []
    base_datos_disponible = False
    puede_ver_futuros = False
    try:
        puede_ver_futuros = puede_ver_productos_futuros(current_user)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT c.*
            FROM categorias_producto c
            JOIN productos p ON p.categoria_producto_id = c.id
            WHERE p.disponible = TRUE OR (%s = TRUE AND p.disponible = FALSE)
            ORDER BY c.nombre
        ''', (puede_ver_futuros,))
        categorias_producto = cursor.fetchall()

        params = []
        where_clauses = ['(p.disponible = TRUE OR (%s = TRUE AND p.disponible = FALSE))']
        params.append(puede_ver_futuros)
        if q:
            where_clauses.append("(p.nombre ILIKE %s OR p.descripcion ILIKE %s OR c.nombre ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if tipo:
            where_clauses.append("c.nombre = %s")
            params.append(tipo)

        sql_where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        query = f'''
            SELECT p.*, c.nombre AS categoria_nombre,
                   COUNT(d.id) AS detalles_relacionados
            FROM productos p
            JOIN categorias_producto c ON p.categoria_producto_id = c.id
            LEFT JOIN detalle_factura d ON d.producto_id = p.id
            {sql_where}
            GROUP BY p.id, c.nombre
            ORDER BY p.disponible DESC, p.id ASC
        '''
        cursor.execute(query, tuple(params))
        lista_productos = cursor.fetchall()
        base_datos_disponible = True
        cursor.close()
        conn.close()
    except psycopg2.Error:
        app.logger.exception('No se pudo cargar el catálogo de productos.')
        flash(
            'No se puede consultar el catálogo porque la conexión con la base de datos no está disponible.',
            'warning'
        )
    return render_template(
        'productos.html',
        productos=lista_productos,
        categorias_producto=categorias_producto,
        query_busqueda=q,
        tipo_seleccionado=tipo,
        puede_ver_futuros=puede_ver_futuros,
        base_datos_disponible=base_datos_disponible
    ), (200 if base_datos_disponible else 503)



@app.route('/proveedores')
@role_required('Administrador', 'Repostero')
def proveedores():
    """
    Ruta del directorio de proveedores e insumos.
    Acceso para Administrador y Repostero.
    Usa JOIN con estados_proveedor y categorias_proveedor para mostrar los nombres relacionados.
    """
    asegurar_datos_proveedor()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, e.nombre AS estado_nombre, c.nombre AS categoria_nombre
        FROM proveedores p
        JOIN estados_proveedor e ON p.estado_id = e.id
        JOIN categorias_proveedor c ON p.categoria_id = c.id
        ORDER BY p.nombre ASC, p.id ASC
    ''')
    lista_proveedores = cursor.fetchall()
    cursor.execute('SELECT * FROM estados_proveedor ORDER BY nombre')
    estados = cursor.fetchall()
    cursor.execute('SELECT * FROM categorias_proveedor ORDER BY nombre')
    categorias = cursor.fetchall()
    cursor.close()
    conn.close()
    form = ProveedorForm()
    form.estado_id.choices = [(e['id'], e['nombre']) for e in estados]
    form.categoria_id.choices = [(c['id'], c['nombre']) for c in categorias]
    return render_template(
        'proveedores.html',
        proveedores=lista_proveedores,
        form=form,
        estados=estados,
        categorias=categorias
    )


@app.route('/clientes')
@role_required('Administrador', 'Encargado', 'Vendedor')
def clientes():
    """
    Ruta del directorio de clientes comerciales.
    Acceso restringido a Administrador, Encargado y Vendedor.
    Repostero y Clientes NO tienen acceso para proteger datos sensibles.
    Usa JOIN con tipos_cliente para mostrar la categoría de persona o empresa.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.*, t.nombre AS tipo_cliente_nombre
        FROM clientes c
        JOIN tipos_cliente t ON c.tipo_cliente_id = t.id
    ''')
    lista_clientes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('clientes.html', clientes=lista_clientes)


def sumar_meses(fecha_base, meses):
    """Suma N meses a una fecha respetando los días del mes y años bisiestos."""
    if not fecha_base or not meses:
        return fecha_base
    if isinstance(fecha_base, str):
        try:
            fecha_base = datetime.strptime(fecha_base, '%Y-%m-%d').date()
        except ValueError:
            return fecha_base
    mes = fecha_base.month - 1 + int(meses)
    anio = fecha_base.year + mes // 12
    mes = mes % 12 + 1
    dias_en_mes = [31, 29 if (anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    dia = min(fecha_base.day, dias_en_mes[mes - 1])
    return date(anio, mes, dia)


def validar_datos_entrega(form, tipo_documento, fecha_emision):
    if tipo_documento == 'Cotizacion':
        return None, None, None

    fecha_texto = (form.fecha_entrega.data or '').strip()
    modalidad = (form.modalidad_entrega.data or '').strip()
    ubicacion = (form.ubicacion_entrega.data or '').strip()
    if not fecha_texto:
        return 'Indica la fecha acordada para entregar el pedido.'
    try:
        fecha = datetime.strptime(fecha_texto, '%Y-%m-%d').date()
    except ValueError:
        return 'La fecha de entrega no tiene un formato válido.'
    if fecha < fecha_emision:
        return 'La fecha de entrega no puede ser anterior a la emisión del documento.'
    if modalidad not in {'domicilio', 'retiro_local'}:
        return 'Selecciona si el pedido se retira en el local o se entrega a domicilio.'
    if modalidad == 'domicilio' and not ubicacion:
        return 'Indica la dirección y una referencia para la entrega a domicilio.'
    return fecha, modalidad, ubicacion or None


@app.route('/parametros-fiscales', methods=['GET', 'POST'])
@login_required
@role_required('Administrador')
def parametros_fiscales():
    """Administra el IVA aplicado a facturas nuevas, sin activar tasas no verificadas."""
    asegurar_parametros_fiscales()
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion', '')
        try:
            if accion == 'actualizar_iva':
                porcentaje = float(request.form.get('valor', ''))
                if not math.isfinite(porcentaje) or not 0 <= porcentaje <= 100:
                    flash('El IVA debe ser un número entre 0 y 100.', 'danger')
                else:
                    cursor.execute(
                        '''UPDATE parametros
                           SET valor = %s, activo = TRUE, actualizado_en = CURRENT_TIMESTAMP
                           WHERE codigo = 'iva' ''',
                        (porcentaje,)
                    )
                    if cursor.rowcount:
                        conn.commit()
                        flash('El porcentaje de IVA se actualizó para las facturas nuevas.', 'success')
                    else:
                        conn.rollback()
                        flash('No se encontró el parámetro IVA. Vuelve a cargar la pantalla.', 'danger')
            else:
                conn.rollback()
                flash('La acción solicitada no es válida. Solo se puede actualizar el IVA.', 'danger')
        except (ValueError, TypeError):
            conn.rollback()
            flash('El IVA debe ser un número válido entre 0 y 100.', 'danger')
        except psycopg2.Error:
            conn.rollback()
            app.logger.exception('No se pudo actualizar el parámetro IVA.')
            flash('No se pudo actualizar el IVA. Inténtalo nuevamente.', 'danger')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('parametros_fiscales'))

    cursor.execute("SELECT * FROM parametros WHERE codigo = 'iva'")
    iva_configurado = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template(
        'parametros_fiscales.html',
        iva=iva_configurado
    )


@app.route('/facturacion')
@role_required('Administrador', 'Encargado', 'Vendedor', 'Cliente')
def facturacion():
    """
    Ruta principal del panel comercial de Facturación y Cotizaciones.
    - Administrador, Encargado y Vendedor: ven los documentos del negocio.
    - Cliente: ve únicamente sus propios pedidos y cotizaciones.
    Carga documentos con historial de pagos, comprobantes y estado de amortización.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if current_user.rol_nombre == 'Cliente':
        cursor.execute('''
            SELECT f.*, c.nombre AS cliente_nombre, c.telefono AS cliente_telefono,
                   c.correo AS cliente_correo, c.ciudad AS cliente_ciudad, e.nombre AS estado_nombre
            FROM facturacion f
            JOIN clientes c ON f.cliente_cedula = c.cedula
            JOIN estados_documento e ON f.estado_id = e.id
            WHERE LOWER(TRIM(c.correo)) = LOWER(TRIM(%s))
               OR c.cedula = %s
            ORDER BY f.numero DESC
        ''', (current_user.correo, current_user.usuario))
    else:
        cursor.execute('''
            SELECT f.*, c.nombre AS cliente_nombre, c.telefono AS cliente_telefono,
                   c.correo AS cliente_correo, c.ciudad AS cliente_ciudad, e.nombre AS estado_nombre
            FROM facturacion f
            JOIN clientes c ON f.cliente_cedula = c.cedula
            JOIN estados_documento e ON f.estado_id = e.id
            ORDER BY f.numero DESC
        ''')
    filas = cursor.fetchall()

    lista_facturas = []
    if filas:
        numeros = [f['numero'] for f in filas]

        # Conteo de productos por documento
        cursor.execute(
            'SELECT factura_numero, COUNT(*) AS total FROM detalle_factura WHERE factura_numero = ANY(%s) GROUP BY factura_numero',
            (numeros,)
        )
        conteos = {r['factura_numero']: r['total'] for r in cursor.fetchall()}

        # Historial de pagos recibidos
        cursor.execute(
            'SELECT * FROM pagos_factura WHERE factura_numero = ANY(%s) ORDER BY factura_numero, numero_pago ASC',
            (numeros,)
        )
        abonos_por_factura = {}
        for p in cursor.fetchall():
            abonos_por_factura.setdefault(p['factura_numero'], []).append(dict(p))

        # Comprobantes de pago
        cursor.execute(
            'SELECT * FROM comprobantes_pago WHERE factura_numero = ANY(%s) ORDER BY factura_numero, id DESC',
            (numeros,)
        )
        comprobantes_por_factura = {}
        for cp in cursor.fetchall():
            comprobantes_por_factura.setdefault(cp['factura_numero'], []).append(dict(cp))

        # Calendario de cuotas y amortización
        cursor.execute(
            'SELECT * FROM cuotas_factura WHERE factura_numero = ANY(%s) ORDER BY factura_numero, numero_pago ASC',
            (numeros,)
        )
        pagos_por_factura = {}
        for c in cursor.fetchall():
            pagos_por_factura.setdefault(c['factura_numero'], []).append(dict(c))

        for f in filas:
            doc = dict(f)
            num = doc['numero']
            doc['productos_conteo'] = conteos.get(num, 0)
            doc['productos_detalle'] = [None] * doc['productos_conteo']

            doc['pagos'] = pagos_por_factura.get(num, [])
            doc['abonos'] = abonos_por_factura.get(num, [])
            doc['comprobantes'] = comprobantes_por_factura.get(num, [])
            doc['pagos'] = pagos_por_factura.get(num, [])

            # Totales y saldos calculados desde base de datos
            total_deuda = float(doc.get('monto') or 0.0)
            doc['total_deuda'] = total_deuda
            if doc['abonos']:
                total_abonado = sum(float(p['monto']) for p in doc['abonos'])
            else:
                total_abonado = float(doc.get('total_abonado') or doc.get('anticipo') or 0.0)
            doc['total_abonado'] = round(total_abonado, 2)
            doc['saldo_pendiente'] = max(0.0, round(total_deuda - total_abonado, 2))

            # Próxima pago pendiente
            pagos_pendientes = [c for c in doc['pagos'] if c['estado'] != 'Pagada']
            if pagos_pendientes:
                prox = pagos_pendientes[0]
                doc['proxima_pago'] = prox
                doc['proxima_pago_texto'] = f"pago #{prox['numero_pago']}: ${float(prox['saldo_pago']):.2f}"
                doc['proxima_pago_fecha'] = prox['fecha_vencimiento']
            else:
                doc['proxima_pago'] = None
                doc['proxima_pago_texto'] = "Liquidado" if doc['saldo_pendiente'] <= 0 else "Al contado"
                doc['proxima_pago_fecha'] = None

            # Normalizar nombre del estado según saldo real
            if doc['tipo'] != 'Cotizacion':
                if doc['saldo_pendiente'] <= 0:
                    doc['estado_nombre'] = 'Pagada'
                elif doc['total_abonado'] > 0:
                    doc['estado_nombre'] = 'Parcial'
                else:
                    doc['estado_nombre'] = 'Pendiente'

            doc['ultimo_comprobante'] = doc['comprobantes'][0]['numero_comprobante'] if doc['comprobantes'] else None
            lista_facturas.append(doc)

    cursor.close()
    conn.close()
    return render_template('facturacion.html', facturas=lista_facturas)


# ==============================================================================
# MÓDULO CRUD: CLIENTES
# ==============================================================================

@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@role_required('Administrador', 'Encargado', 'Vendedor')
def nuevo_cliente():
    """
    Crea y registra un nuevo cliente en el sistema. La cédula es la clave primaria.
    """
    asegurar_campos_cliente()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tipos_cliente ORDER BY nombre')
    tipos_cliente = cursor.fetchall()

    form = ClienteForm()
    form.tipo_cliente_id.choices = [(t['id'], t['nombre']) for t in tipos_cliente]

    if form.validate_on_submit():
        cursor.execute('SELECT * FROM clientes WHERE cedula = %s', (form.cedula.data.strip(),))
        existente = cursor.fetchone()
        if existente is not None:
            cursor.close()
            conn.close()
            flash('Ya existe un cliente registrado con esa cédula.', 'danger')
            return render_template('formulario_cliente.html', form=form, editando=False)

        cedula_cliente = form.cedula.data.strip()
        correo_cliente = form.correo.data.strip()
        cursor.execute(
            '''INSERT INTO clientes
               (cedula, nombre, apellido, telefono, correo, tipo_cliente_id, ciudad, direccion, usuario_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (cedula_cliente, form.nombre.data.strip(), (form.apellido.data or '').strip() or None,
             form.telefono.data.strip(), correo_cliente, form.tipo_cliente_id.data,
             form.ciudad.data.strip(), (form.direccion.data or '').strip() or None,
             vincular_cliente_con_usuario(cursor, cedula_cliente, correo_cliente))
        )
        conn.commit()
        cursor.close()
        conn.close()

        registrar_log('CREAR_CLIENTE', f"Cliente {form.nombre.data.strip()} ({form.cedula.data.strip()}) creado por {current_user.usuario}")
        flash('Cliente registrado correctamente.', 'success')
        return redirect(url_for('clientes'))

    cursor.close()
    conn.close()
    return render_template('formulario_cliente.html', form=form, editando=False)


@app.route('/api/clientes', methods=['POST'])
@login_required
@role_required('Administrador', 'Encargado', 'Vendedor')
def crear_cliente_desde_facturacion():
    """Registra un cliente desde el flujo de facturación con la validación habitual."""
    asegurar_campos_cliente()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre FROM tipos_cliente ORDER BY nombre')
    tipos_cliente = cursor.fetchall()
    form = ClienteForm()
    form.tipo_cliente_id.choices = [(tipo['id'], tipo['nombre']) for tipo in tipos_cliente]

    if not form.validate_on_submit():
        errores = {
            campo: mensajes
            for campo, mensajes in form.errors.items()
        }
        cursor.close()
        conn.close()
        return jsonify({'ok': False, 'errores': errores}), 400

    cedula = form.cedula.data.strip()
    tipo_identificacion = request.form.get('tipo_identificacion')
    if not identificacion_valida_para_tipo(tipo_identificacion, cedula):
        cursor.close()
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'La identificación no corresponde al tipo seleccionado.'}), 400
    cursor.execute('SELECT 1 FROM clientes WHERE cedula = %s', (cedula,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'Ya existe un cliente registrado con esa cédula.'}), 409

    try:
        correo_cliente = form.correo.data.strip()
        cursor.execute(
            '''INSERT INTO clientes
               (cedula, nombre, apellido, telefono, correo, tipo_cliente_id, ciudad, direccion, usuario_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
            (cedula, form.nombre.data.strip(), (form.apellido.data or '').strip() or None,
             form.telefono.data.strip(), correo_cliente, form.tipo_cliente_id.data,
             form.ciudad.data.strip(), (form.direccion.data or '').strip() or None,
             vincular_cliente_con_usuario(cursor, cedula, correo_cliente))
        )
        conn.commit()
    except psycopg2.Error:
        conn.rollback()
        app.logger.exception('No se pudo crear el cliente desde facturación.')
        cursor.close()
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'No se pudo guardar el cliente. Verifica los datos e intenta otra vez.'}), 503

    cursor.close()
    conn.close()
    registrar_log('CREAR_CLIENTE', f"Cliente {form.nombre.data.strip()} ({cedula}) creado desde facturación por {current_user.usuario}")
    return jsonify({
        'ok': True,
        'cliente': {
            'cedula': cedula,
            'nombre': form.nombre.data.strip(),
            'apellido': (form.apellido.data or '').strip(),
            'telefono': form.telefono.data.strip(),
            'correo': form.correo.data.strip(),
            'ciudad': form.ciudad.data.strip(),
            'direccion': (form.direccion.data or '').strip()
        }
    }), 201


@app.route('/api/clientes/<identificacion>')
@login_required
@role_required('Administrador', 'Encargado', 'Vendedor')
def buscar_cliente_facturacion(identificacion):
    """Busca por cédula o RUC para completar los datos de facturación."""
    identificacion = identificacion.strip()
    if not identificacion.isdigit() or len(identificacion) not in (10, 13):
        return jsonify({'ok': False, 'mensaje': 'Ingresa una cédula de 10 o un RUC de 13 dígitos.'}), 400

    asegurar_campos_cliente()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT cedula, nombre, apellido, correo, telefono, direccion, ciudad
               FROM clientes WHERE cedula = %s''',
            (identificacion,)
        )
        cliente = cursor.fetchone()
        if cliente is None:
            return jsonify({'ok': True, 'encontrado': False}), 404
        return jsonify({'ok': True, 'encontrado': True, 'cliente': dict(cliente)})
    finally:
        cursor.close()
        conn.close()


@app.route('/clientes/editar/<cedula>', methods=['GET', 'POST'])
@role_required('Administrador', 'Encargado')
def editar_cliente(cedula):
    """
    Edita la información de un cliente existente identificado por su cédula (PK).
    La cédula no se modifica desde este formulario, ya que otras tablas dependen de ella.
    """
    asegurar_campos_cliente()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes WHERE cedula = %s', (cedula,))
    cliente = cursor.fetchone()

    if cliente is None:
        cursor.close()
        conn.close()
        flash('El cliente seleccionado no existe.', 'danger')
        return redirect(url_for('clientes'))

    cursor.execute('SELECT * FROM tipos_cliente ORDER BY nombre')
    tipos_cliente = cursor.fetchall()

    form = ClienteForm(data=dict(cliente)) if request.method == 'GET' else ClienteForm()
    form.tipo_cliente_id.choices = [(t['id'], t['nombre']) for t in tipos_cliente]
    if request.method == 'GET':
        form.tipo_cliente_id.data = cliente['tipo_cliente_id']

    if form.validate_on_submit():
        cursor.execute(
            '''UPDATE clientes
               SET nombre=%s, apellido=%s, telefono=%s, correo=%s, tipo_cliente_id=%s, ciudad=%s, direccion=%s
               WHERE cedula=%s''',
            (form.nombre.data.strip(), (form.apellido.data or '').strip() or None, form.telefono.data.strip(),
             form.correo.data.strip(), form.tipo_cliente_id.data, form.ciudad.data.strip(),
             (form.direccion.data or '').strip() or None, cedula)
        )
        conn.commit()
        cursor.close()
        conn.close()

        registrar_log('EDITAR_CLIENTE', f"Cliente {form.nombre.data.strip()} ({cedula}) actualizado por {current_user.usuario}")
        flash(f'Cliente "{form.nombre.data.strip()}" actualizado correctamente.', 'success')
        return redirect(url_for('clientes'))

    cursor.close()
    conn.close()
    return render_template('formulario_cliente.html', form=form, editando=True, cedula=cedula)


@app.route('/clientes/eliminar/<cedula>', methods=['POST'])
@role_required('Administrador')
def eliminar_cliente(cedula):
    """
    Elimina un cliente de PostgreSQL según su cédula, siempre que no tenga facturas asociadas.
    Acceso exclusivo para el rol Administrador.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes WHERE cedula = %s', (cedula,))
    cliente = cursor.fetchone()

    if cliente is None:
        cursor.close()
        conn.close()
        flash('El cliente seleccionado no existe.', 'danger')
        return redirect(url_for('clientes'))

    cursor.execute(
        'SELECT COUNT(*) AS total FROM facturacion WHERE cliente_cedula = %s', (cedula,)
    )
    facturas_asociadas = cursor.fetchone()['total']

    if facturas_asociadas > 0:
        cursor.close()
        conn.close()
        flash(f'No se puede eliminar a "{cliente["nombre"]}" porque tiene {facturas_asociadas} factura(s) o cotización(es) registradas.', 'danger')
        return redirect(url_for('clientes'))

    cursor.execute('DELETE FROM clientes WHERE cedula = %s', (cedula,))
    conn.commit()
    cursor.close()
    conn.close()

    registrar_log('ELIMINAR_CLIENTE', f"Cliente {cliente['nombre']} ({cedula}) eliminado por {current_user.usuario}")
    flash(f'Cliente "{cliente["nombre"]}" eliminado correctamente.', 'success')
    return redirect(url_for('clientes'))


# ==============================================================================
# MÓDULO CRUD: TIPOS DE CLIENTE
# ==============================================================================

@app.route('/tipos-cliente')
@role_required('Administrador')
def tipos_cliente():
    """
    Lista las categorías de cliente disponibles para personas naturales y empresas.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tipos_cliente ORDER BY nombre')
    lista_tipos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('tipos_cliente.html', tipos=lista_tipos)


@app.route('/tipos-cliente/nuevo', methods=['GET', 'POST'])
@role_required('Administrador')
def nuevo_tipo_cliente():
    """
    Registra una nueva categoría de cliente.
    """
    form = TipoClienteForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO tipos_cliente (nombre) VALUES (%s)', (form.nombre.data.strip(),))
        conn.commit()
        cursor.close()
        conn.close()
        registrar_log('CREAR_TIPO_CLIENTE', f"Tipo de cliente {form.nombre.data.strip()} creado por {current_user.usuario}")
        flash('Tipo de cliente registrado correctamente.', 'success')
        return redirect(url_for('tipos_cliente'))
    return render_template('formulario_tipo_cliente.html', form=form, editando=False)


@app.route('/tipos-cliente/editar/<int:id>', methods=['GET', 'POST'])
@role_required('Administrador')
def editar_tipo_cliente(id):
    """
    Edita el nombre de una categoría de cliente existente.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tipos_cliente WHERE id = %s', (id,))
    tipo = cursor.fetchone()

    if tipo is None:
        cursor.close()
        conn.close()
        flash('El tipo de cliente seleccionado no existe.', 'danger')
        return redirect(url_for('tipos_cliente'))

    form = TipoClienteForm(data=dict(tipo)) if request.method == 'GET' else TipoClienteForm()

    if form.validate_on_submit():
        cursor.execute('UPDATE tipos_cliente SET nombre=%s WHERE id=%s', (form.nombre.data.strip(), id))
        conn.commit()
        cursor.close()
        conn.close()
        registrar_log('EDITAR_TIPO_CLIENTE', f"Tipo de cliente ID {id} actualizado a {form.nombre.data.strip()} por {current_user.usuario}")
        flash(f'Tipo de cliente "{form.nombre.data.strip()}" actualizado correctamente.', 'success')
        return redirect(url_for('tipos_cliente'))

    cursor.close()
    conn.close()
    return render_template('formulario_tipo_cliente.html', form=form, editando=True, id=id)


@app.route('/tipos-cliente/eliminar/<int:id>', methods=['POST'])
@role_required('Administrador')
def eliminar_tipo_cliente(id):
    """
    Elimina un tipo de cliente, siempre que ningún registro lo esté usando.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tipos_cliente WHERE id = %s', (id,))
    tipo = cursor.fetchone()

    if tipo is None:
        cursor.close()
        conn.close()
        flash('El tipo de cliente seleccionado no existe.', 'danger')
        return redirect(url_for('tipos_cliente'))

    cursor.execute('SELECT COUNT(*) AS total FROM clientes WHERE tipo_cliente_id = %s', (id,))
    en_uso = cursor.fetchone()['total']
    if en_uso > 0:
        cursor.close()
        conn.close()
        flash(f'No se puede eliminar "{tipo["nombre"]}" porque hay clientes asignados a esta categoría.', 'danger')
        return redirect(url_for('tipos_cliente'))

    cursor.execute('DELETE FROM tipos_cliente WHERE id = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()
    registrar_log('ELIMINAR_TIPO_CLIENTE', f"Tipo de cliente {tipo['nombre']} (ID {id}) eliminado por {current_user.usuario}")
    flash(f'Tipo de cliente "{tipo["nombre"]}" eliminado correctamente.', 'success')
    return redirect(url_for('tipos_cliente'))


# ==============================================================================
# MÓDULO CRUD: CATEGORÍAS DE PRODUCTOS
# ==============================================================================

@app.route('/categorias-producto')
@role_required('Administrador')
def categorias_producto():
    """
    Lista las categorías de producto disponibles en el catálogo.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias_producto ORDER BY nombre')
    lista_tipos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('categorias_producto.html', tipos=lista_tipos)


@app.route('/categorias-producto/nuevo', methods=['GET', 'POST'])
@role_required('Administrador')
def nueva_categoria_producto():
    """
    Registra una nueva categoría de producto.
    """
    form = CategoriaProductoForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO categorias_producto (nombre) VALUES (%s)', (form.nombre.data.strip(),))
        conn.commit()
        cursor.close()
        conn.close()
        registrar_log('CREAR_CATEGORIA_PRODUCTO', f"Categoría {form.nombre.data.strip()} creada por {current_user.usuario}")
        flash('Categoría registrada correctamente.', 'success')
        return redirect(url_for('categorias_producto'))
    return render_template('formulario_categoria_producto.html', form=form, editando=False)


@app.route('/categorias-producto/editar/<int:id>', methods=['GET', 'POST'])
@role_required('Administrador')
def editar_categoria_producto(id):
    """
    Edita el nombre de una categoría de producto existente.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias_producto WHERE id = %s', (id,))
    tipo = cursor.fetchone()

    if tipo is None:
        cursor.close()
        conn.close()
        flash('La categoría seleccionada no existe.', 'danger')
        return redirect(url_for('categorias_producto'))

    form = CategoriaProductoForm(data=dict(tipo)) if request.method == 'GET' else CategoriaProductoForm()

    if form.validate_on_submit():
        cursor.execute('UPDATE categorias_producto SET nombre=%s WHERE id=%s', (form.nombre.data.strip(), id))
        conn.commit()
        cursor.close()
        conn.close()
        registrar_log('EDITAR_CATEGORIA_PRODUCTO', f"Categoría ID {id} actualizada a {form.nombre.data.strip()} por {current_user.usuario}")
        flash(f'Categoría "{form.nombre.data.strip()}" actualizada correctamente.', 'success')
        return redirect(url_for('categorias_producto'))

    cursor.close()
    conn.close()
    return render_template('formulario_categoria_producto.html', form=form, editando=True, id=id)


@app.route('/categorias-producto/eliminar/<int:id>', methods=['POST'])
@role_required('Administrador')
def eliminar_categoria_producto(id):
    """
    Elimina una categoría de producto, siempre que ningún producto la esté usando.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias_producto WHERE id = %s', (id,))
    tipo = cursor.fetchone()

    if tipo is None:
        cursor.close()
        conn.close()
        flash('La categoría seleccionada no existe.', 'danger')
        return redirect(url_for('categorias_producto'))

    cursor.execute('SELECT COUNT(*) AS total FROM productos WHERE categoria_producto_id = %s', (id,))
    en_uso = cursor.fetchone()['total']
    if en_uso > 0:
        cursor.close()
        conn.close()
        flash(f'No se puede eliminar "{tipo["nombre"]}" porque hay productos asignados a esta categoría.', 'danger')
        return redirect(url_for('categorias_producto'))

    cursor.execute('DELETE FROM categorias_producto WHERE id = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()
    registrar_log('ELIMINAR_CATEGORIA_PRODUCTO', f"Categoría {tipo['nombre']} (ID {id}) eliminada por {current_user.usuario}")
    flash(f'Categoría "{tipo["nombre"]}" eliminada correctamente.', 'success')
    return redirect(url_for('categorias_producto'))


# ==============================================================================
# MÓDULO CRUD: PRODUCTOS
# ==============================================================================

@app.route('/productos/nuevo', methods=['GET', 'POST'])
@role_required('Administrador', 'Encargado')
def nuevo_producto():
    """
    Registra un nuevo producto en el catálogo, asociado a una categoría (categoria_producto_id).
    Acceso para Administrador y Encargado.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias_producto ORDER BY nombre')
    tipos = cursor.fetchall()

    form = ProductoForm()
    form.categoria_producto_id.choices = [(t['id'], t['nombre']) for t in tipos]

    if form.validate_on_submit():
        imagen_ingresada = form.imagen.data.strip() if form.imagen.data else ''
        imagen_url = resolver_url_imagen(imagen_ingresada) if imagen_ingresada else None
        cursor.execute(
            '''INSERT INTO productos (categoria_producto_id, nombre, precio_base, imagen, descripcion, disponible, es_insumo)
               VALUES (%s, %s, %s, %s, %s, %s, %s)''',
            (form.categoria_producto_id.data, form.nombre.data.strip(), float(form.precio.data),
             imagen_url, form.descripcion.data.strip(), form.disponible.data, bool(form.es_insumo.data))
        )
        conn.commit()
        cursor.close()
        conn.close()

        registrar_log('CREAR_PRODUCTO', f"Producto {form.nombre.data.strip()} creado por {current_user.usuario}")
        flash('Producto registrado correctamente.', 'success')
        return redirect(url_for('productos'))

    cursor.close()
    conn.close()
    return render_template('formulario_producto.html', form=form, editando=False)


@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@role_required('Administrador', 'Encargado', 'Repostero')
@permission_required('productos.editar')
def editar_producto(id):
    """
    Edita un producto existente identificado por su id real de PostgreSQL.
    Acceso para Administrador y Encargado.
    """
    asegurar_inventario_base()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM productos WHERE id = %s', (id,))
    producto = cursor.fetchone()

    if producto is None:
        cursor.close()
        conn.close()
        flash('El producto seleccionado no existe.', 'danger')
        return redirect(url_for('productos'))

    cursor.execute('SELECT * FROM categorias_producto ORDER BY nombre')
    tipos = cursor.fetchall()

    datos_form = dict(producto)
    datos_form['precio'] = producto['precio_base']  # el form usa 'precio', la BD usa 'precio_base'

    form = ProductoForm(data=datos_form) if request.method == 'GET' else ProductoForm()
    form.categoria_producto_id.choices = [(t['id'], t['nombre']) for t in tipos]
    if request.method == 'GET':
        form.categoria_producto_id.data = producto['categoria_producto_id']
        form.stock_entrada.data = 0

    if form.validate_on_submit():
        imagen_ingresada = form.imagen.data.strip() if form.imagen.data else ''
        imagen_url = resolver_url_imagen(imagen_ingresada) if imagen_ingresada else producto['imagen']
        entrada_stock = int(form.stock_entrada.data or 0)
        cursor.execute('SELECT stock_actual FROM productos WHERE id = %s FOR UPDATE', (id,))
        producto_bloqueado = cursor.fetchone()
        if producto_bloqueado is None:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('El producto seleccionado ya no existe.', 'danger')
            return redirect(url_for('productos'))
        stock_actual = int(producto_bloqueado['stock_actual'] or 0)
        cursor.execute(
            '''UPDATE productos SET categoria_producto_id=%s, nombre=%s, precio_base=%s, imagen=%s, descripcion=%s, disponible=%s, es_insumo=%s
               WHERE id=%s''',
            (form.categoria_producto_id.data, form.nombre.data.strip(), float(form.precio.data),
             imagen_url, form.descripcion.data.strip(), form.disponible.data, bool(form.es_insumo.data), id)
        )
        if entrada_stock:
            cursor.execute(
                '''INSERT INTO kardex_movimientos
                   (producto_id, tipo, cantidad, referencia, descripcion, usuario_id)
                   VALUES (%s, 'entrada', %s, %s, %s, %s)''',
                (id, entrada_stock, 'Entrada desde edición de producto',
                 'Ingreso de existencias al editar el producto', current_user.id)
            )
            cursor.execute(
                'UPDATE productos SET stock_actual = %s WHERE id = %s',
                (stock_actual + entrada_stock, id)
            )
        conn.commit()
        cursor.close()
        conn.close()

        registrar_log('EDITAR_PRODUCTO', f"Producto {form.nombre.data.strip()} (ID {id}) editado por {current_user.usuario}")
        flash(f'Producto "{form.nombre.data.strip()}" actualizado correctamente.', 'success')
        return redirect(url_for('productos'))

    cursor.close()
    conn.close()
    return render_template(
        'formulario_producto.html', form=form, editando=True, id=id,
        stock_actual=producto['stock_actual'] or 0
    )


@app.route('/productos/eliminar/<int:id>', methods=['POST'])
@role_required('Administrador')
def eliminar_producto(id):
    """
    Elimina un producto del catálogo en PostgreSQL.
    Acceso exclusivo para el rol Administrador.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM productos WHERE id = %s', (id,))
    producto = cursor.fetchone()

    if producto is None:
        cursor.close()
        conn.close()
        flash('El producto seleccionado no existe.', 'danger')
        return redirect(url_for('productos'))

    cursor.execute(
        'SELECT COUNT(*) AS total FROM detalle_factura WHERE producto_id = %s',
        (id,)
    )
    relaciones = cursor.fetchone()['total']
    if relaciones > 0:
        cursor.close()
        conn.close()
        flash(
            f'No se puede eliminar "{producto["nombre"]}" porque está relacionado '
            f'con {relaciones} detalle(s) de factura o cotización. Puedes editarlo '
            'o marcarlo como no disponible.',
            'danger'
        )
        return redirect(url_for('productos'))

    cursor.execute('DELETE FROM productos WHERE id = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()

    registrar_log('ELIMINAR_PRODUCTO', f"Producto {producto['nombre']} (ID {id}) eliminado por {current_user.usuario}")
    flash(f'Producto "{producto["nombre"]}" eliminado correctamente.', 'success')
    return redirect(url_for('productos'))


# ==============================================================================
# MÓDULO CRUD: PROVEEDORES
# ==============================================================================

@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
@role_required('Administrador', 'Repostero')
def nuevo_proveedor():
    """
    Registra un proveedor de insumos o productos.
    Acceso para Administrador y Repostero.
    """
    asegurar_datos_proveedor()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM estados_proveedor ORDER BY id')
    estados = cursor.fetchall()
    cursor.execute('SELECT * FROM categorias_proveedor ORDER BY nombre')
    categorias = cursor.fetchall()

    form = ProveedorForm()
    form.estado_id.choices = [(e['id'], e['nombre']) for e in estados]
    form.categoria_id.choices = [(c['id'], c['nombre']) for c in categorias]

    if form.validate_on_submit():
        ruc = form.ruc.data.strip() if form.ruc.data else None
        if not ruc:
            form.ruc.errors.append('El RUC fiscal es obligatorio para registrar un proveedor.')
        else:
            cursor.execute('SELECT 1 FROM proveedores WHERE ruc = %s', (ruc,))
            if cursor.fetchone():
                form.ruc.errors.append('Ya existe un proveedor registrado con este RUC.')
            else:
                cursor.execute(
                    '''INSERT INTO proveedores
                       (nombre, ruc, categoria_id, persona_contacto, telefono, correo, sitio_web, contacto, estado_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (
                        form.nombre.data.strip(), ruc, form.categoria_id.data,
                        form.persona_contacto.data.strip() if form.persona_contacto.data else None,
                        form.telefono.data.strip(), form.correo.data.strip(),
                        form.sitio_web.data.strip() if form.sitio_web.data else None,
                        form.correo.data.strip(), form.estado_id.data
                    )
                )
                conn.commit()
                cursor.close()
                conn.close()

                registrar_log('CREAR_PROVEEDOR', f"Proveedor {form.nombre.data.strip()} creado por {current_user.usuario}")
                flash('Proveedor registrado correctamente.', 'success')
                return redirect(url_for('proveedores'))

    cursor.close()
    conn.close()
    return render_template('formulario_proveedor.html', form=form, editando=False)


@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
@role_required('Administrador', 'Repostero')
def editar_proveedor(id):
    """
    Modifica los datos de un proveedor existente en PostgreSQL.
    Acceso para Administrador y Repostero.
    """
    asegurar_datos_proveedor()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM proveedores WHERE id = %s', (id,))
    proveedor = cursor.fetchone()

    if proveedor is None:
        cursor.close()
        conn.close()
        flash('El proveedor seleccionado no existe.', 'danger')
        return redirect(url_for('proveedores'))

    cursor.execute('SELECT * FROM estados_proveedor ORDER BY id')
    estados = cursor.fetchall()
    cursor.execute('SELECT * FROM categorias_proveedor ORDER BY nombre')
    categorias = cursor.fetchall()

    form = ProveedorForm(data=dict(proveedor)) if request.method == 'GET' else ProveedorForm()
    form.estado_id.choices = [(e['id'], e['nombre']) for e in estados]
    form.categoria_id.choices = [(c['id'], c['nombre']) for c in categorias]
    if request.method == 'GET':
        form.estado_id.data = proveedor['estado_id']
        form.categoria_id.data = proveedor['categoria_id']

    if form.validate_on_submit():
        ruc = form.ruc.data.strip() if form.ruc.data else None
        if ruc:
            cursor.execute('SELECT 1 FROM proveedores WHERE ruc = %s AND id <> %s', (ruc, id))
            if cursor.fetchone():
                form.ruc.errors.append('Ya existe un proveedor registrado con este RUC.')
            else:
                cursor.execute(
                    '''UPDATE proveedores
                       SET nombre=%s, ruc=%s, categoria_id=%s, persona_contacto=%s,
                           telefono=%s, correo=%s, sitio_web=%s, contacto=%s, estado_id=%s
                       WHERE id=%s''',
                    (
                        form.nombre.data.strip(), ruc, form.categoria_id.data,
                        form.persona_contacto.data.strip() if form.persona_contacto.data else None,
                        form.telefono.data.strip(), form.correo.data.strip(),
                        form.sitio_web.data.strip() if form.sitio_web.data else None,
                        form.correo.data.strip(), form.estado_id.data, id
                    )
                )
        else:
            cursor.execute(
                '''UPDATE proveedores
                   SET nombre=%s, ruc=NULL, categoria_id=%s, persona_contacto=%s,
                       telefono=%s, correo=%s, sitio_web=%s, contacto=%s, estado_id=%s
                   WHERE id=%s''',
                (
                    form.nombre.data.strip(), form.categoria_id.data,
                    form.persona_contacto.data.strip() if form.persona_contacto.data else None,
                    form.telefono.data.strip(), form.correo.data.strip(),
                    form.sitio_web.data.strip() if form.sitio_web.data else None,
                    form.correo.data.strip(), form.estado_id.data, id
                )
            )
        if not form.ruc.errors:
            conn.commit()
            cursor.close()
            conn.close()

            registrar_log('EDITAR_PROVEEDOR', f"Proveedor {form.nombre.data.strip()} (ID {id}) actualizado por {current_user.usuario}")
            flash(f'Proveedor "{form.nombre.data.strip()}" actualizado correctamente.', 'success')
            return redirect(url_for('proveedores'))

    cursor.close()
    conn.close()
    return render_template('formulario_proveedor.html', form=form, editando=True, id=id)


@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
@role_required('Administrador')
def eliminar_proveedor(id):
    """
    Elimina un proveedor de PostgreSQL.
    Acceso exclusivo para el rol Administrador.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM proveedores WHERE id = %s', (id,))
    proveedor = cursor.fetchone()

    if proveedor is None:
        cursor.close()
        conn.close()
        flash('El proveedor seleccionado no existe.', 'danger')
        return redirect(url_for('proveedores'))

    cursor.execute('DELETE FROM proveedores WHERE id = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()

    registrar_log('ELIMINAR_PROVEEDOR', f"Proveedor {proveedor['nombre']} (ID {id}) eliminado por {current_user.usuario}")
    flash(f'Proveedor "{proveedor["nombre"]}" eliminado correctamente.', 'success')
    return redirect(url_for('proveedores'))


# ==============================================================================
# MÓDULO CRUD: CATEGORÍAS DE PROVEEDOR
# ==============================================================================

@app.route('/categorias-proveedor')
@role_required('Administrador', 'Repostero')
def categorias_proveedor():
    """
    Lista las categorías disponibles para clasificar proveedores.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias_proveedor ORDER BY nombre')
    lista_categorias = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('categorias_proveedor.html', categorias=lista_categorias)


@app.route('/categorias-proveedor/nueva', methods=['GET', 'POST'])
@role_required('Administrador', 'Repostero')
def nueva_categoria_proveedor():
    """
    Registra una nueva categoría de proveedor.
    """
    form = CategoriaProveedorForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO categorias_proveedor (nombre) VALUES (%s)', (form.nombre.data.strip(),))
        conn.commit()
        cursor.close()
        conn.close()

        registrar_log('CREAR_CATEGORIA_PROVEEDOR', f"Categoría {form.nombre.data.strip()} creada por {current_user.usuario}")
        flash('Categoría registrada correctamente.', 'success')
        return redirect(url_for('categorias_proveedor'))
    return render_template('formulario_categoria_proveedor.html', form=form, editando=False)


@app.route('/api/categorias-proveedor', methods=['POST'])
@login_required
@role_required('Administrador', 'Repostero')
def crear_categoria_proveedor_inline():
    """Permite añadir una categoría desde el formulario de proveedor."""
    form = CategoriaProveedorForm()
    if not form.validate_on_submit():
        return jsonify({'ok': False, 'errores': form.errors}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    nombre = form.nombre.data.strip()
    try:
        cursor.execute(
            'INSERT INTO categorias_proveedor (nombre) VALUES (%s) RETURNING id',
            (nombre,)
        )
        categoria_id = cursor.fetchone()['id']
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'Ya existe una categoría con ese nombre.'}), 409
    except psycopg2.Error:
        conn.rollback()
        app.logger.exception('No se pudo crear la categoría de proveedor desde el formulario.')
        cursor.close()
        conn.close()
        return jsonify({'ok': False, 'mensaje': 'No se pudo guardar la categoría.'}), 503

    cursor.close()
    conn.close()
    registrar_log('CREAR_CATEGORIA_PROVEEDOR', f"Categoría {nombre} creada por {current_user.usuario}")
    return jsonify({'ok': True, 'categoria': {'id': categoria_id, 'nombre': nombre}}), 201


@app.route('/categorias-proveedor/editar/<int:id>', methods=['GET', 'POST'])
@role_required('Administrador', 'Repostero')
def editar_categoria_proveedor(id):
    """
    Edita el nombre de una categoría de proveedor existente.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias_proveedor WHERE id = %s', (id,))
    categoria = cursor.fetchone()

    if categoria is None:
        cursor.close()
        conn.close()
        flash('La categoría seleccionada no existe.', 'danger')
        return redirect(url_for('categorias_proveedor'))

    form = CategoriaProveedorForm(data=dict(categoria)) if request.method == 'GET' else CategoriaProveedorForm()

    if form.validate_on_submit():
        cursor.execute('UPDATE categorias_proveedor SET nombre=%s WHERE id=%s', (form.nombre.data.strip(), id))
        conn.commit()
        cursor.close()
        conn.close()

        registrar_log('EDITAR_CATEGORIA_PROVEEDOR', f"Categoría ID {id} actualizada a {form.nombre.data.strip()} por {current_user.usuario}")
        flash(f'Categoría "{form.nombre.data.strip()}" actualizada correctamente.', 'success')
        return redirect(url_for('categorias_proveedor'))

    cursor.close()
    conn.close()
    return render_template('formulario_categoria_proveedor.html', form=form, editando=True, id=id)


@app.route('/categorias-proveedor/eliminar/<int:id>', methods=['POST'])
@role_required('Administrador', 'Repostero')
def eliminar_categoria_proveedor(id):
    """
    Elimina una categoría de proveedor, siempre que ningún proveedor la esté usando.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categorias_proveedor WHERE id = %s', (id,))
    categoria = cursor.fetchone()

    if categoria is None:
        cursor.close()
        conn.close()
        flash('La categoría seleccionada no existe.', 'danger')
        return redirect(url_for('categorias_proveedor'))

    cursor.execute('SELECT COUNT(*) AS total FROM proveedores WHERE categoria_id = %s', (id,))
    en_uso = cursor.fetchone()['total']
    if en_uso > 0:
        cursor.close()
        conn.close()
        flash(f'No se puede eliminar "{categoria["nombre"]}" porque hay proveedores asignados a esta categoría.', 'danger')
        return redirect(url_for('categorias_proveedor'))

    cursor.execute('DELETE FROM categorias_proveedor WHERE id = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()

    registrar_log('ELIMINAR_CATEGORIA_PROVEEDOR', f"Categoría {categoria['nombre']} (ID {id}) eliminada por {current_user.usuario}")
    flash(f'Categoría "{categoria["nombre"]}" eliminada correctamente.', 'success')
    return redirect(url_for('categorias_proveedor'))


# ==============================================================================
# MÓDULO CRUD: FACTURACIÓN
# ==============================================================================

def obtener_siguiente_numero_documento(cursor, tipo_doc):
    """
    Calcula el siguiente número secuencial único que NO exista en facturacion.
    Garantiza que no haya saltos innecesarios en lecturas (GET) y evita colisiones.
    """
    es_cotizacion = (tipo_doc == 'Cotizacion')
    prefijo = f"COT-{date.today().year}-" if es_cotizacion else "001-001-"

    # 1. Obtener todos los números existentes en facturación con este prefijo
    cursor.execute("SELECT numero FROM facturacion WHERE numero LIKE %s", (f"{prefijo}%",))
    existentes = {r['numero'] for r in cursor.fetchall()}

    max_num = 0
    for num_str in existentes:
        try:
            seg = int(num_str.split('-')[-1])
            if seg > max_num:
                max_num = seg
        except (ValueError, IndexError):
            continue

    proximo = max_num + 1

    # 2. Garantizar que el número no colisione con ninguno existente
    while True:
        candidato = f"{prefijo}{proximo:04d}" if es_cotizacion else f"{prefijo}{proximo:09d}"
        if candidato not in existentes:
            break
        proximo += 1

    return f"{prefijo}{proximo:09d}" if not es_cotizacion else f"{prefijo}{proximo:04d}"


def identificacion_valida_para_tipo(tipo, identificacion):
    """Comprueba que la longitud de la identificación corresponda al tipo elegido."""
    longitud = len(str(identificacion or '').strip())
    if tipo == 'cedula':
        return longitud == 10
    if tipo == 'ruc':
        return longitud == 13
    return tipo in (None, '') and longitud in (10, 13)


def datos_actualizacion_cliente_factura(form):
    """Devuelve solo los campos de cliente marcados explícitamente para actualizar."""
    campos = {
        'actualizar_correo': ('correo', form.cliente_correo.data, 150),
        'actualizar_direccion': ('direccion', form.cliente_direccion.data, 300),
        'actualizar_ciudad': ('ciudad', form.cliente_ciudad.data, 100),
        'actualizar_telefono': ('telefono', form.cliente_telefono.data, 20),
    }
    actualizaciones = {}
    for bandera, (columna, valor, limite) in campos.items():
        if request.form.get(bandera) != 'on':
            continue
        valor = (valor or '').strip()
        if not valor or len(valor) > limite:
            raise ValueError(f'Completa un valor válido para actualizar {columna}.')
        if columna == 'correo' and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', valor):
            raise ValueError('El correo que deseas actualizar no tiene un formato válido.')
        if columna == 'telefono' and not re.fullmatch(r'[\d+() -]{7,20}', valor):
            raise ValueError('El teléfono que deseas actualizar no tiene un formato válido.')
        actualizaciones[columna] = valor
    return actualizaciones


def guardar_datos_cliente_facturacion(cursor, cedula, actualizaciones):
    """Obtiene los datos vigentes, aplica solo cambios consentidos y devuelve el snapshot."""
    cursor.execute(
        '''SELECT nombre, apellido, correo, telefono, direccion, ciudad
           FROM clientes WHERE cedula = %s FOR UPDATE''',
        (cedula,)
    )
    fila = cursor.fetchone()
    if fila is None:
        raise ValueError('El cliente ya no está registrado. Verifica la identificación e intenta otra vez.')
    datos = dict(fila)
    datos.update(actualizaciones)
    if actualizaciones:
        columnas = ', '.join(f'{columna} = %s' for columna in actualizaciones)
        cursor.execute(
            f'UPDATE clientes SET {columnas} WHERE cedula = %s',
            (*actualizaciones.values(), cedula)
        )
    return datos


def normalizar_detalles_factura(cursor, items, usar_precio_catalogo=False):
    """Valida líneas de catálogo y adicionales antes de persistirlas o descontar stock."""
    if not isinstance(items, list) or not items:
        raise ValueError('Agrega al menos un producto o adicional antes de guardar.')
    ids_catalogo = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Hay una línea de detalle con formato inválido.')
        if not item.get('es_adicional') and str(item.get('id', '')).isdigit():
            ids_catalogo.add(int(item['id']))

    catalogo = {}
    if ids_catalogo:
        cursor.execute(
            'SELECT id, nombre, descripcion, precio_base FROM productos WHERE id = ANY(%s) AND es_insumo = FALSE',
            (list(ids_catalogo),)
        )
        catalogo = {int(row['id']): row for row in cursor.fetchall()}
        if len(catalogo) != len(ids_catalogo):
            raise ValueError('Uno de los productos seleccionados ya no existe en el catálogo.')

    normalizados = []
    for item in items:
        es_adicional = bool(item.get('es_adicional'))
        nombre = str(item.get('producto') or '').strip()
        descripcion = str(item.get('descripcion') or '').strip()
        unidad = str(item.get('unidad_medida') or 'unidad').strip()
        if not nombre or len(nombre) > 150 or len(descripcion) > 3000 or not unidad or len(unidad) > 30:
            raise ValueError('Completa el nombre, la descripción y la unidad de cada línea.')
        try:
            cantidad = float(item.get('cantidad', 1))
            precio = float(item.get('precio', 0))
            ajuste = float(item.get('ajuste', 0))
        except (TypeError, ValueError):
            raise ValueError('La cantidad y los precios deben ser números válidos.')
        if (
            not math.isfinite(cantidad) or cantidad <= 0
            or not math.isfinite(precio) or precio < 0
            or not math.isfinite(ajuste) or precio + ajuste < 0
        ):
            raise ValueError('La cantidad y el total unitario deben ser válidos y no negativos.')

        producto_id = None
        if es_adicional:
            ajuste = 0.0
        else:
            try:
                producto_id = int(item.get('id'))
            except (TypeError, ValueError):
                raise ValueError('Selecciona un producto del catálogo para cada línea de producto.')
            producto = catalogo.get(producto_id)
            if producto is None:
                raise ValueError('Selecciona un producto válido del catálogo.')
            if not cantidad.is_integer():
                raise ValueError('La cantidad de productos de inventario debe ser un número entero.')
            nombre = producto['nombre']
            if not descripcion:
                descripcion = producto['descripcion'] or ''
            if usar_precio_catalogo:
                precio = float(producto['precio_base'])
            unidad = 'unidad'
            cantidad = int(cantidad)

        linea = {
            'id': producto_id,
            'producto': nombre,
            'descripcion': descripcion,
            'unidad_medida': unidad,
            'es_adicional': es_adicional,
            'cantidad': cantidad,
            'precio': precio,
            'ajuste': ajuste,
            'total': round((precio + ajuste) * cantidad, 2)
        }
        normalizados.append(linea)

    consolidado = {}
    for item in normalizados:
        llave = (
            item['id'], item['producto'].casefold(), item['descripcion'],
            item['unidad_medida'], item['es_adicional'], item['precio'], item['ajuste']
        )
        if llave in consolidado:
            consolidado[llave]['cantidad'] += item['cantidad']
            consolidado[llave]['total'] = round(
                (item['precio'] + item['ajuste']) * consolidado[llave]['cantidad'], 2
            )
        else:
            consolidado[llave] = item
    return list(consolidado.values())


@app.route('/api/siguiente-numero/<tipo>')
@login_required
def api_siguiente_numero(tipo):
    """Retorna el siguiente número secuencial disponible para Factura o Cotización."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        num = obtener_siguiente_numero_documento(cursor, tipo)
        return jsonify({'numero': num})
    finally:
        cursor.close()
        conn.close()


@app.route('/facturacion/nueva', methods=['GET', 'POST'])
@role_required('Administrador', 'Encargado', 'Vendedor')
@permission_required('facturas.crear')
def nueva_factura():
    """
    Emite un nuevo documento comercial (Factura o Cotización).
    El cliente se selecciona de una lista real (cliente_cedula), y cada producto
    incluido se guarda como una fila propia en detalle_factura.
    Soporta un pago al confirmar el pedido o dos pagos hasta el retiro.
    """
    form = FacturacionForm()
    tipo_solicitado = request.args.get('tipo', 'Cotizacion' if request.args.get('producto_id') is not None else 'Factura')

    asegurar_inventario_base()
    asegurar_parametros_fiscales()
    asegurar_detalles_factura()
    asegurar_campos_cliente()
    asegurar_snapshots_documentos()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''SELECT c.*, t.nombre AS tipo_cliente_nombre
           FROM clientes c LEFT JOIN tipos_cliente t ON t.id = c.tipo_cliente_id
           ORDER BY c.nombre'''
    )
    clientes_registrados = cursor.fetchall()
    impuestos_activos = obtener_impuestos_activos(cursor)
    cursor.execute('SELECT id, nombre FROM tipos_cliente ORDER BY nombre')
    tipos_cliente = cursor.fetchall()

    cursor.execute('SELECT * FROM estados_documento ORDER BY id')
    estados = cursor.fetchall()
    form.estado_id.choices = [(e['id'], e['nombre']) for e in estados]
    id_por_nombre = {e['nombre']: e['id'] for e in estados}

    if request.method == 'GET':
        form.tipo.data = tipo_solicitado
        form.tipo_identificacion.data = 'cedula'
        proximo_numero = obtener_siguiente_numero_documento(cursor, tipo_solicitado)
        form.numero.data = proximo_numero
        if tipo_solicitado == 'Cotizacion':
            form.validez.data = "15 días"
            form.estado_id.data = id_por_nombre.get('En revision') or id_por_nombre.get('Pendiente', 2)
        else:
            form.validez.data = "30 días"
            form.estado_id.data = id_por_nombre.get('Pendiente', 2)
        form.fecha.data = str(date.today())
        form.anticipo.data = 0.00
        form.saldo_pendiente.data = 0.00
        form.tipo_pago.data = 'contado'
        form.plazo_meses.data = 2

    formulario_valido = form.validate_on_submit()
    if formulario_valido and not identificacion_valida_para_tipo(
        form.tipo_identificacion.data, form.cliente_cedula.data
    ):
        form.cliente_cedula.errors.append('El número de dígitos no coincide con el tipo de identificación seleccionado.')
        formulario_valido = False
    cliente_encontrado = any(
        cliente['cedula'] == form.cliente_cedula.data
        for cliente in clientes_registrados
    ) if formulario_valido else False
    if formulario_valido and cliente_encontrado:
        try:
            actualizaciones_cliente = datos_actualizacion_cliente_factura(form)
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(error), 'danger')
            return redirect(url_for('nueva_factura', tipo=form.tipo.data))

        tipo_doc = form.tipo.data
        cursor.execute('LOCK TABLE facturacion IN SHARE ROW EXCLUSIVE MODE')
        numero_param = obtener_siguiente_numero_documento(cursor, tipo_doc)

        productos_detalle = []
        if form.productos_json.data:
            try:
                productos_detalle = json.loads(form.productos_json.data)
            except (TypeError, ValueError, json.JSONDecodeError):
                productos_detalle = []

        try:
            productos_detalle = normalizar_detalles_factura(
                cursor, productos_detalle, usar_precio_catalogo=True
            )
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(error), 'danger')
            return redirect(url_for('nueva_factura', tipo=tipo_doc))

        subtotal_calculado = round(sum(item['total'] for item in productos_detalle), 2)
        aplica_iva = bool(form.aplica_impuestos.data)
        subtotal_val = subtotal_calculado
        iva_val, impuestos_detalle = calcular_impuestos(
            subtotal_val, impuestos_activos if aplica_iva else []
        )
        # El documento y sus líneas quedan relacionados con el parámetro de IVA.
        iva_aplicado = impuestos_activos[0] if (aplica_iva and impuestos_activos) else None
        iva_param_id = iva_aplicado['id'] if iva_aplicado else None
        iva_porcentaje = iva_aplicado['porcentaje'] if iva_aplicado else None
        total_original = round(subtotal_val + iva_val, 2)
        anticipo_val = float(form.anticipo.data) if form.anticipo.data is not None else 0.00

        # Los pagos diferidos se registran en pagos sin cargos financieros.
        forma_pago = form.forma_pago.data or 'Transferencia bancaria'
        tipo_pago = form.tipo_pago.data or 'contado'
        plazo_meses = 2 if tipo_pago == 'plazos' else 1

        if not math.isfinite(anticipo_val) or anticipo_val < 0:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('El abono inicial debe ser un monto válido y no negativo.', 'danger')
            return redirect(url_for('nueva_factura', tipo=tipo_doc))

        if anticipo_val > total_original and total_original > 0:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(f'El abono recibido (${anticipo_val:.2f}) no puede superar el total del pedido (${total_original:.2f}).', 'danger')
            return redirect(url_for('nueva_factura', tipo=tipo_doc))

        if tipo_doc == 'Factura':
            if tipo_pago == 'contado' and round(anticipo_val, 2) != round(total_original, 2):
                conn.rollback()
                cursor.close()
                conn.close()
                flash('Para registrar un solo pago, debe recibirse el total del pedido al confirmarlo.', 'danger')
                return redirect(url_for('nueva_factura', tipo=tipo_doc))
            if tipo_pago == 'plazos' and not (0 < anticipo_val < total_original):
                conn.rollback()
                cursor.close()
                conn.close()
                flash('Para usar dos pagos, registra un Pago 1 mayor a $0.00 y menor al total; el Pago 2 será el saldo al retirar.', 'danger')
                return redirect(url_for('nueva_factura', tipo=tipo_doc))

        saldo_val = max(0.0, round(total_original - anticipo_val, 2))

        try:
            fecha_emision = datetime.strptime(str(form.fecha.data), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            fecha_emision = date.today()

        entrega = validar_datos_entrega(form, tipo_doc, fecha_emision)
        if isinstance(entrega, str):
            conn.rollback()
            cursor.close()
            conn.close()
            flash(entrega, 'danger')
            return redirect(url_for('nueva_factura', tipo=tipo_doc))
        fecha_entrega, modalidad_entrega, ubicacion_entrega = entrega

        # El comprobante final solo se asigna cuando el saldo queda liquidado.
        numero_factura_final = None
        if tipo_doc == 'Cotizacion':
            estado_id_final = id_por_nombre.get('En revision') or id_por_nombre.get('Pendiente', 2)
            numero_factura_final = None
        else:
            if saldo_val <= 0:
                estado_id_final = id_por_nombre.get('Pagada', 1)
                numero_factura_final = numero_param
            else:
                numero_factura_final = None  # Bloqueado hasta liquidación total
                estado_id_final = id_por_nombre.get('Parcial') if anticipo_val > 0 else id_por_nombre.get('Pendiente', 2)

        notas_final = form.notas.data.strip() if form.notas.data else (
            "Propuesta emitida por Dulce Delicia." if tipo_doc == 'Cotizacion' else "Comprobante emitido por Dulce Delicia."
        )
        try:
            cliente_snapshot = guardar_datos_cliente_facturacion(
                cursor, form.cliente_cedula.data.strip(), actualizaciones_cliente
            )
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(error), 'danger')
            return redirect(url_for('nueva_factura', tipo=tipo_doc))

        # Inserción con autogeneración secuencial atómica
        cursor.execute(
            '''INSERT INTO facturacion
               (numero, tipo, cliente_cedula, fecha, validez, subtotal, iva, impuestos_detalle, monto, anticipo, saldo_pendiente, estado_id, notas,
                numero_factura, forma_pago, tipo_pago, plazo_meses, total_abonado,
                fecha_entrega, modalidad_entrega, ubicacion_entrega,
                cliente_nombre_snapshot, cliente_apellido_snapshot, cliente_correo_snapshot,
                cliente_telefono_snapshot, cliente_direccion_snapshot, cliente_ciudad_snapshot,
                usuario_id, iva_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING numero''',
            (numero_param, tipo_doc, form.cliente_cedula.data, str(fecha_emision),
             form.validez.data.strip() if form.validez.data else "15 días",
             subtotal_val, iva_val, json.dumps(impuestos_detalle), total_original, anticipo_val, saldo_val, estado_id_final, notas_final,
             numero_factura_final, forma_pago, tipo_pago, plazo_meses, anticipo_val,
             fecha_entrega, modalidad_entrega, ubicacion_entrega,
             cliente_snapshot['nombre'], cliente_snapshot.get('apellido'), cliente_snapshot['correo'],
             cliente_snapshot['telefono'], cliente_snapshot.get('direccion'), cliente_snapshot['ciudad'],
             current_user.id if current_user.is_authenticated else None,
             iva_param_id)
        )
        row_insertado = cursor.fetchone()
        numero_limpio = row_insertado['numero']

        # Insertar líneas de detalle
        for item in productos_detalle:
            cursor.execute(
                '''INSERT INTO detalle_factura
                   (factura_numero, producto_id, nombre_producto, cantidad, precio_base, ajuste, total,
                    descripcion_linea, unidad_medida, es_adicional, iva_id, iva_valor)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (numero_limpio, item.get('id'), item.get('producto', 'Producto'),
                 float(item.get('cantidad', 1)), float(item.get('precio', 0)),
                 float(item.get('ajuste', 0)), float(item.get('total', item.get('precio', 0))),
                 item.get('descripcion') or None, item.get('unidad_medida') or 'unidad',
                 bool(item.get('es_adicional')), iva_param_id, iva_porcentaje)
            )

        if tipo_doc == 'Factura':
            error_stock = ajustar_kardex_venta(
                cursor, numero_limpio, productos_detalle, current_user.id, tipo_doc,
                force_tracking=True
            )
            if error_stock:
                conn.rollback()
                cursor.close()
                conn.close()
                flash(error_stock, 'danger')
                return redirect(url_for('nueva_factura', tipo=tipo_doc))

        # El esquema legado de pagos se usa aquí para guardar solo los dos hitos acordados.
        if tipo_doc != 'Cotizacion' and tipo_pago == 'plazos' and plazo_meses >= 2:
            pagos_programados = (
                (1, anticipo_val, fecha_emision, anticipo_val, 0.0, 'Pagada'),
                (2, saldo_val, fecha_entrega, 0.0, saldo_val, 'Pendiente'),
            )
            for numero_pago_plan, monto_plan, fecha_plan, monto_pagado_plan, saldo_plan, estado_plan in pagos_programados:
                cursor.execute(
                    '''INSERT INTO cuotas_factura (factura_numero, numero_pago, valor_pago, fecha_vencimiento, monto_pagado, saldo_pago, estado)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                    (
                        numero_limpio, numero_pago_plan, monto_plan, fecha_plan,
                        monto_pagado_plan, saldo_plan, estado_plan
                    )
                )

        numero_comprobante = None
        # Todo pago inicial produce su propio recibo antes de poder consultar la factura final.
        if tipo_doc != 'Cotizacion' and anticipo_val > 0:
            cursor.execute('''
                INSERT INTO pagos_factura (
                    factura_numero, numero_pago, monto, fecha, metodo_pago, referencia,
                    saldo_anterior, saldo_posterior, total_acumulado, registrado_por, notas, usuario_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                numero_limpio, 1, anticipo_val, str(fecha_emision), forma_pago,
                'Anticipo inicial', total_original, saldo_val, anticipo_val, current_user.usuario, 'Abono inicial registrado',
                current_user.id if current_user.is_authenticated else None
            ))
            pago_id = cursor.fetchone()['id']

            cursor.execute("SELECT nextval('secuencia_comprobantes') AS seq")
            numero_comprobante = f"REC-{date.today().year}-{cursor.fetchone()['seq']:04d}"

            cursor.execute('''
                INSERT INTO comprobantes_pago (
                    numero_comprobante, pago_id, factura_numero, cliente_cedula, fecha,
                    monto_abonado, total_deuda, total_acumulado_pagado, saldo_pendiente, observaciones,
                    cliente_nombre_snapshot, cliente_apellido_snapshot, cliente_correo_snapshot,
                    cliente_telefono_snapshot, cliente_direccion_snapshot, cliente_ciudad_snapshot
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                numero_comprobante, pago_id, numero_limpio, form.cliente_cedula.data, str(fecha_emision),
                anticipo_val, total_original, anticipo_val, saldo_val, 'Comprobante de abono inicial',
                cliente_snapshot['nombre'], cliente_snapshot.get('apellido'), cliente_snapshot['correo'],
                cliente_snapshot['telefono'], cliente_snapshot.get('direccion'), cliente_snapshot['ciudad']
            ))

            # La cuota cubierta por el anticipo queda ligada a su pago, para que
            # la trazabilidad cuota -> pago -> comprobante sea completa.
            cursor.execute(
                '''UPDATE cuotas_factura SET pago_id = %s
                   WHERE factura_numero = %s AND numero_pago = 1 AND estado = 'Pagada'
                     AND pago_id IS NULL''',
                (pago_id, numero_limpio)
            )

        # El documento y su comprobante muestran siempre el próximo pago
        # pendiente; si la deuda está liquidada, quedan en NULL ("Liquidado").
        cursor.execute('''
            SELECT numero_pago, fecha_vencimiento, saldo_pago
            FROM cuotas_factura
            WHERE factura_numero = %s AND estado <> 'Pagada' AND saldo_pago > 0
            ORDER BY numero_pago ASC
            LIMIT 1
        ''', (numero_limpio,))
        proxima = cursor.fetchone()
        proxima_pago_num = proxima['numero_pago'] if proxima else None
        proxima_pago_fecha = proxima['fecha_vencimiento'] if proxima else None
        proxima_pago_monto = float(proxima['saldo_pago']) if proxima else None

        cursor.execute(
            '''UPDATE facturacion
               SET proxima_pago_fecha = %s, proxima_pago_monto = %s
               WHERE numero = %s''',
            (proxima_pago_fecha, proxima_pago_monto, numero_limpio)
        )
        if numero_comprobante:
            cursor.execute(
                '''UPDATE comprobantes_pago
                   SET proxima_pago_num = %s, proxima_pago_fecha = %s, proxima_pago_monto = %s
                   WHERE numero_comprobante = %s''',
                (proxima_pago_num, proxima_pago_fecha, proxima_pago_monto, numero_comprobante)
            )

        conn.commit()
        cursor.close()
        conn.close()

        nombre_doc = "Cotización" if tipo_doc == 'Cotizacion' else "Documento de Venta"
        registrar_log('EMITIR_FACTURA', f"{nombre_doc} {numero_limpio} emitida por {current_user.usuario} por un monto de ${total_original:.2f}")
        flash(f'{nombre_doc} "{numero_limpio}" guardada correctamente.', 'success')
        if tipo_doc == 'Factura' and numero_comprobante:
            return redirect(url_for('ver_comprobante_pago', numero_comprobante=numero_comprobante))
        if tipo_doc == 'Factura' and saldo_val <= 0:
            return redirect(url_for('ver_comprobante_venta', numero=numero_limpio))
        return redirect(url_for('facturacion'))

    if formulario_valido and not cliente_encontrado:
        form.cliente_cedula.errors.append(
            'No existe un cliente con esa cédula. Regístralo aquí antes de emitir el documento.'
        )
    cursor.execute(
        'SELECT p.*, p.stock_actual AS stock_disponible FROM productos p WHERE NOT p.es_insumo ORDER BY p.nombre'
    )
    productos_catalogo = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'formulario_facturacion.html',
        form=form,
        editando=False,
        productos_catalogo=productos_catalogo,
        clientes_registrados=clientes_registrados,
        tipos_cliente=tipos_cliente,
        impuestos_activos=impuestos_activos,
        producto_seleccionado_id=request.args.get('producto_id', type=int)
    )


@app.route('/facturacion/editar/<numero>', methods=['GET', 'POST'])
@role_required('Administrador', 'Encargado')
@permission_required('facturas.editar')
def editar_factura(numero):
    """
    Edita un documento comercial existente, identificado por su número (clave primaria).
    El número no se modifica desde este formulario, ya que detalle_factura y pagos dependen de él.
    """
    asegurar_inventario_base()
    asegurar_parametros_fiscales()
    asegurar_detalles_factura()
    asegurar_campos_cliente()
    asegurar_snapshots_documentos()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM facturacion WHERE numero = %s FOR UPDATE', (numero,))
    fila = cursor.fetchone()

    if fila is None:
        cursor.close()
        conn.close()
        flash('El documento seleccionado no existe.', 'danger')
        return redirect(url_for('facturacion'))

    factura = dict(fila)
    cursor.execute('SELECT * FROM detalle_factura WHERE factura_numero = %s', (numero,))
    detalle_actual = cursor.fetchall()
    factura['productos_detalle'] = [
        {'id': d['producto_id'], 'producto': d['nombre_producto'], 'cantidad': float(d['cantidad']),
         'precio': float(d['precio_base']), 'ajuste': float(d['ajuste']), 'total': float(d['total']),
         'descripcion': d['descripcion_linea'] or '', 'unidad_medida': d['unidad_medida'],
         'es_adicional': bool(d['es_adicional'])}
        for d in detalle_actual
    ]

    cursor.execute(
        '''SELECT c.*, t.nombre AS tipo_cliente_nombre
           FROM clientes c LEFT JOIN tipos_cliente t ON t.id = c.tipo_cliente_id
           ORDER BY c.nombre'''
    )
    clientes_registrados = cursor.fetchall()
    impuestos_activos = obtener_impuestos_activos(cursor)
    cursor.execute('SELECT id, nombre FROM tipos_cliente ORDER BY nombre')
    tipos_cliente = cursor.fetchall()
    cursor.execute('SELECT * FROM estados_documento ORDER BY id')
    estados = cursor.fetchall()
    id_por_nombre = {e['nombre']: e['id'] for e in estados}

    form = FacturacionForm(data=factura) if request.method == 'GET' else FacturacionForm()
    form.estado_id.choices = [(e['id'], e['nombre']) for e in estados]

    if request.method == 'GET':
        form.cliente_cedula.data = factura['cliente_cedula']
        form.tipo_identificacion.data = 'ruc' if len(str(factura['cliente_cedula'])) == 13 else 'cedula'
        form.estado_id.data = factura['estado_id']
        form.aplica_impuestos.data = float(factura.get('iva') or 0) > 0
        form.forma_pago.data = factura.get('forma_pago') or 'Transferencia bancaria'
        form.tipo_pago.data = factura.get('tipo_pago') or 'contado'
        plazo_guardado = int(factura.get('plazo_meses') or 2)
        plazos_validos = {valor for valor, _ in form.plazo_meses.choices}
        form.plazo_meses.data = plazo_guardado if plazo_guardado in plazos_validos else 2
        form.productos_json.data = json.dumps(factura['productos_detalle'])

    formulario_valido = form.validate_on_submit()
    if formulario_valido and not identificacion_valida_para_tipo(
        form.tipo_identificacion.data, form.cliente_cedula.data
    ):
        form.cliente_cedula.errors.append('El número de dígitos no coincide con el tipo de identificación seleccionado.')
        formulario_valido = False
    cliente_encontrado = any(
        cliente['cedula'] == form.cliente_cedula.data
        for cliente in clientes_registrados
    ) if formulario_valido else False
    if formulario_valido and cliente_encontrado:
        try:
            actualizaciones_cliente = datos_actualizacion_cliente_factura(form)
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(error), 'danger')
            return redirect(url_for('editar_factura', numero=numero))

        productos_detalle = []
        if form.productos_json.data:
            try:
                productos_detalle = json.loads(form.productos_json.data)
            except (TypeError, ValueError, json.JSONDecodeError):
                productos_detalle = []
        try:
            productos_detalle = normalizar_detalles_factura(cursor, productos_detalle)
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(error), 'danger')
            return redirect(url_for('editar_factura', numero=numero))

        # Consultar pagos registrados en base de datos (Regla 10 G)
        cursor.execute('SELECT COALESCE(SUM(monto), 0) AS total_pagos FROM pagos_factura WHERE factura_numero = %s', (numero,))
        total_pagos_bd = float(cursor.fetchone()['total_pagos'])

        anticipo_form = float(form.anticipo.data) if form.anticipo.data is not None else 0.00
        if not math.isfinite(anticipo_form) or anticipo_form < 0:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('El total abonado debe ser un monto válido y no negativo.', 'danger')
            return redirect(url_for('editar_factura', numero=numero))
        total_abonado = max(total_pagos_bd, anticipo_form)

        forma_pago = form.forma_pago.data or factura.get('forma_pago') or 'Transferencia bancaria'
        tipo_pago = form.tipo_pago.data or factura.get('tipo_pago') or 'contado'
        plazo_meses = int(form.plazo_meses.data or factura.get('plazo_meses') or 2) if tipo_pago == 'plazos' else 1
        subtotal_val = round(sum(item['total'] for item in productos_detalle), 2)
        aplica_iva = bool(form.aplica_impuestos.data)
        iva_val, impuestos_detalle = calcular_impuestos(
            subtotal_val, impuestos_activos if aplica_iva else []
        )
        total_original = round(subtotal_val + iva_val, 2)

        saldo_val = max(0.0, round(total_original - total_abonado, 2))
        if total_abonado > total_original:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('El total actualizado no puede ser menor que los pagos ya registrados.', 'danger')
            return redirect(url_for('editar_factura', numero=numero))
        tipo_doc = form.tipo.data
        notas_final = form.notas.data.strip() if form.notas.data else "Documento generado por Dulce Delicia."

        try:
            fecha_emision = datetime.strptime(str(form.fecha.data), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            fecha_emision = date.today()

        entrega = validar_datos_entrega(form, tipo_doc, fecha_emision)
        if isinstance(entrega, str):
            conn.rollback()
            cursor.close()
            conn.close()
            flash(entrega, 'danger')
            return redirect(url_for('editar_factura', numero=numero))
        fecha_entrega, modalidad_entrega, ubicacion_entrega = entrega

        error_stock = ajustar_kardex_venta(
            cursor,
            numero,
            productos_detalle,
            current_user.id,
            tipo_doc,
            force_tracking=(tipo_doc == 'Factura')
        )
        if error_stock:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(error_stock, 'danger')
            return redirect(url_for('editar_factura', numero=numero))

        try:
            cliente_snapshot = guardar_datos_cliente_facturacion(
                cursor, form.cliente_cedula.data.strip(), actualizaciones_cliente
            )
        except ValueError as error:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(error), 'danger')
            return redirect(url_for('editar_factura', numero=numero))

        # REGLA CRÍTICA B: Factura final generada ÚNICAMENTE cuando saldo <= 0
        numero_factura_asignado = factura.get('numero_factura')
        if tipo_doc == 'Factura':
            if saldo_val <= 0:
                estado_id_final = id_por_nombre.get('Pagada', 1)
                if not numero_factura_asignado:
                    numero_factura_asignado = numero
            else:
                numero_factura_asignado = None  # Se revoca número oficial si tiene saldo pendiente
                estado_id_final = id_por_nombre.get('Parcial') if total_abonado > 0 else id_por_nombre.get('Pendiente', 2)
        else:
            estado_id_final = form.estado_id.data

        cursor.execute(
            '''UPDATE facturacion SET
               tipo=%s, cliente_cedula=%s, fecha=%s, validez=%s,
               subtotal=%s, iva=%s, impuestos_detalle=%s::jsonb, monto=%s, anticipo=%s, saldo_pendiente=%s, estado_id=%s, notas=%s,
               numero_factura=%s, forma_pago=%s, tipo_pago=%s, plazo_meses=%s,
               total_abonado=%s, fecha_entrega=%s, modalidad_entrega=%s, ubicacion_entrega=%s,
               cliente_nombre_snapshot=%s, cliente_apellido_snapshot=%s, cliente_correo_snapshot=%s,
               cliente_telefono_snapshot=%s, cliente_direccion_snapshot=%s, cliente_ciudad_snapshot=%s
               WHERE numero=%s''',
            (tipo_doc, form.cliente_cedula.data, str(fecha_emision),
             form.validez.data.strip() if form.validez.data else "15 días",
             subtotal_val, iva_val, json.dumps(impuestos_detalle), total_original, total_abonado, saldo_val, estado_id_final, notas_final,
             numero_factura_asignado, forma_pago, tipo_pago, plazo_meses,
             total_abonado, fecha_entrega, modalidad_entrega, ubicacion_entrega,
             cliente_snapshot['nombre'], cliente_snapshot.get('apellido'), cliente_snapshot['correo'],
             cliente_snapshot['telefono'], cliente_snapshot.get('direccion'), cliente_snapshot['ciudad'], numero)
        )

        cursor.execute('DELETE FROM detalle_factura WHERE factura_numero = %s', (numero,))
        for item in productos_detalle:
            cursor.execute(
                '''INSERT INTO detalle_factura
                   (factura_numero, producto_id, nombre_producto, cantidad, precio_base, ajuste, total,
                    descripcion_linea, unidad_medida, es_adicional)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (numero, item.get('id'), item.get('producto', 'Producto'),
                 float(item.get('cantidad', 1)), float(item.get('precio', 0)),
                 float(item.get('ajuste', 0)), float(item.get('total', item.get('precio', 0))),
                 item.get('descripcion') or None, item.get('unidad_medida') or 'unidad',
                 bool(item.get('es_adicional')))
            )

        conn.commit()
        cursor.close()
        conn.close()

        nombre_doc = "Cotización" if tipo_doc == 'Cotizacion' else "Factura"
        registrar_log('EDITAR_FACTURA', f"{nombre_doc} {numero} actualizada por {current_user.usuario}")
        flash(f'{nombre_doc} "{numero}" actualizada correctamente.', 'success')
        return redirect(url_for('facturacion'))

    if formulario_valido and not cliente_encontrado:
        form.cliente_cedula.errors.append(
            'No existe un cliente con esa cédula. Regístralo aquí antes de guardar el documento.'
        )
    cursor.execute(
        '''SELECT p.*,
                  p.stock_actual + COALESCE((
                      SELECT SUM(CASE WHEN k.tipo = 'salida' THEN k.cantidad ELSE -k.cantidad END)
                      FROM kardex_movimientos k
                      WHERE k.producto_id = p.id
                        AND k.factura_numero = %s
                        AND k.automatico = TRUE
                  ), 0) AS stock_disponible
           FROM productos p
           WHERE NOT p.es_insumo
           ORDER BY p.nombre''',
        (numero,)
    )
    productos_catalogo = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        'formulario_facturacion.html',
        form=form,
        editando=True,
        numero=numero,
        productos_catalogo=productos_catalogo,
        clientes_registrados=clientes_registrados,
        tipos_cliente=tipos_cliente,
        impuestos_activos=impuestos_activos,
        detalle_existente=factura['productos_detalle']
    )


@app.route('/facturacion/abono/<numero>', methods=['POST'])
@role_required('Administrador', 'Encargado', 'Vendedor')
@permission_required('facturas.ver')
def registrar_abono(numero):
    """
    Registra un abono/pago parcial o total para una factura comercial.
    Aplica controles críticos (Reglas 10 A - 10 I):
    - Transacción atómica en PostgreSQL.
    - Validación estricta: monto > 0 y monto <= saldo_pendiente.
    - Registro en historial individual (pagos_factura).
    - Generación atómica de Comprobante de Pago único (comprobantes_pago).
    - Amortización progresiva de pagos en pagos_factura si aplica.
    - Emisión del comprobante de venta únicamente cuando el saldo queda en cero.
    """
    monto_str = request.form.get('monto') or (request.json.get('monto') if request.is_json else '')
    fecha_pago = request.form.get('fecha') or (request.json.get('fecha') if request.is_json else '') or str(date.today())
    metodo_pago = request.form.get('metodo_pago') or (request.json.get('metodo_pago') if request.is_json else 'Transferencia bancaria')
    referencia = request.form.get('referencia') or (request.json.get('referencia') if request.is_json else '')
    notas = request.form.get('notas') or (request.json.get('notas') if request.is_json else '')

    asegurar_campos_cliente()
    asegurar_snapshots_documentos()
    try:
        monto_decimal = Decimal(str(monto_str)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        flash('El monto del abono debe ser un número válido.', 'danger')
        return redirect(url_for('facturacion'))

    if not monto_decimal.is_finite() or monto_decimal <= 0:
        flash('El monto del abono debe ser mayor a $0.00.', 'danger')
        return redirect(url_for('facturacion'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Bloquear fila con FOR UPDATE para concurrencia segura
        cursor.execute('''
            SELECT f.*, c.cedula AS c_cedula, c.nombre AS c_nombre
            FROM facturacion f
            JOIN clientes c ON f.cliente_cedula = c.cedula
            WHERE f.numero = %s
            FOR UPDATE
        ''', (numero,))
        factura = cursor.fetchone()

        if not factura:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(f'El documento "{numero}" no fue encontrado.', 'danger')
            return redirect(url_for('facturacion'))

        if factura['tipo'] == 'Cotizacion':
            conn.rollback()
            cursor.close()
            conn.close()
            flash('No se pueden registrar pagos sobre una cotización o proforma comercial. Conviértela o emite una factura.', 'warning')
            return redirect(url_for('facturacion'))

        total_deuda_decimal = Decimal(str(factura.get('monto') or 0)).quantize(Decimal('0.01'))

        # Calcular total acumulado previo desde base de datos
        cursor.execute('SELECT COALESCE(SUM(monto), 0) AS total_pagado, COUNT(*) AS conteo FROM pagos_factura WHERE factura_numero = %s', (numero,))
        res_pagos = cursor.fetchone()
        total_pagado_decimal = Decimal(str(res_pagos['total_pagado'] or 0)).quantize(Decimal('0.01'))
        if total_pagado_decimal == 0 and Decimal(str(factura.get('anticipo') or 0)) > 0:
            total_pagado_decimal = Decimal(str(factura['anticipo'])).quantize(Decimal('0.01'))

        saldo_anterior_decimal = (total_deuda_decimal - total_pagado_decimal).quantize(Decimal('0.01'))

        # REGLA CRÍTICA C: No permitir monto_abono > saldo_pendiente (Caso de prueba 4)
        if monto_decimal > saldo_anterior_decimal:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(f'Operación rechazada: El pago ingresado (${monto_decimal:.2f}) supera el saldo pendiente de ${saldo_anterior_decimal:.2f}. No se permiten sobrepagos.', 'danger')
            return redirect(url_for('facturacion'))

        saldo_anterior = float(saldo_anterior_decimal)
        monto_abono = float(monto_decimal)
        total_deuda = float(total_deuda_decimal)
        saldo_posterior = float(max(Decimal('0.00'), saldo_anterior_decimal - monto_decimal))
        nuevo_total_abonado = float((total_pagado_decimal + monto_decimal).quantize(Decimal('0.01')))
        numero_pago = int(res_pagos['conteo']) + 1

        # 1. Insertar pago individual en el historial (Regla 10 F)
        cursor.execute('''
            INSERT INTO pagos_factura (
                factura_numero, numero_pago, monto, fecha, metodo_pago, referencia,
                saldo_anterior, saldo_posterior, total_acumulado, registrado_por, notas, usuario_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (
            numero, numero_pago, monto_abono, fecha_pago, metodo_pago,
            referencia.strip() if referencia else None, saldo_anterior, saldo_posterior,
            nuevo_total_abonado, current_user.usuario, notas.strip() if notas else None,
            current_user.id if current_user.is_authenticated else None
        ))
        pago_id = cursor.fetchone()['id']

        # 2. Generar número único de Comprobante de Pago (Regla 10 E)
        cursor.execute("SELECT nextval('secuencia_comprobantes') AS seq")
        seq_comp = cursor.fetchone()['seq']
        numero_comprobante = f"REC-{date.today().year}-{seq_comp:04d}"

        # 3. Amortizar pagos pendientes si existen
        cursor.execute('''
            SELECT * FROM cuotas_factura
            WHERE factura_numero = %s
            ORDER BY numero_pago ASC
            FOR UPDATE
        ''', (numero,))
        pagos_existentes = cursor.fetchall()

        monto_restante_pago = monto_abono
        for c in pagos_existentes:
            if c['estado'] == 'Pagada':
                continue
            if monto_restante_pago <= 0:
                break
            saldo_c = float(c['saldo_pago'])
            pagado_actual = float(c['monto_pagado'])
            if monto_restante_pago >= saldo_c:
                monto_restante_pago = round(monto_restante_pago - saldo_c, 2)
                cursor.execute('''
                    UPDATE cuotas_factura
                    SET monto_pagado = %s, saldo_pago = 0, estado = 'Pagada', fecha_pago = %s,
                        pago_id = %s
                    WHERE id = %s
                ''', (float(c['valor_pago']), fecha_pago, pago_id, c['id']))
            else:
                nuevo_saldo_c = round(saldo_c - monto_restante_pago, 2)
                nuevo_pagado_c = round(pagado_actual + monto_restante_pago, 2)
                monto_restante_pago = 0.0
                cursor.execute('''
                    UPDATE cuotas_factura
                    SET monto_pagado = %s, saldo_pago = %s, estado = 'Parcial', fecha_pago = %s,
                        pago_id = %s
                    WHERE id = %s
                ''', (nuevo_pagado_c, nuevo_saldo_c, fecha_pago, pago_id, c['id']))

        # Obtener próxima pago pendiente
        cursor.execute('''
            SELECT * FROM cuotas_factura
            WHERE factura_numero = %s AND estado != 'Pagada'
            ORDER BY numero_pago ASC
            LIMIT 1
        ''', (numero,))
        prox_c = cursor.fetchone()
        proxima_pago_num = prox_c['numero_pago'] if prox_c else None
        proxima_pago_fecha = prox_c['fecha_vencimiento'] if prox_c else None
        proxima_pago_monto = float(prox_c['saldo_pago']) if prox_c else None

        # 4. Insertar comprobante de pago
        cursor.execute('''
            INSERT INTO comprobantes_pago (
                numero_comprobante, pago_id, factura_numero, cliente_cedula, fecha,
                monto_abonado, total_deuda, total_acumulado_pagado, saldo_pendiente,
                proxima_pago_num, proxima_pago_fecha, proxima_pago_monto, observaciones,
                cliente_nombre_snapshot, cliente_apellido_snapshot, cliente_correo_snapshot,
                cliente_telefono_snapshot, cliente_direccion_snapshot, cliente_ciudad_snapshot
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            numero_comprobante, pago_id, numero, factura['cliente_cedula'], fecha_pago,
            monto_abono, total_deuda, nuevo_total_abonado, saldo_posterior,
            proxima_pago_num, proxima_pago_fecha, proxima_pago_monto,
            notas.strip() if notas else f'Abono #{numero_pago} registrado vía {metodo_pago}',
            factura.get('cliente_nombre_snapshot'), factura.get('cliente_apellido_snapshot'),
            factura.get('cliente_correo_snapshot'), factura.get('cliente_telefono_snapshot'),
            factura.get('cliente_direccion_snapshot'), factura.get('cliente_ciudad_snapshot')
        ))

        cursor.execute('SELECT id, nombre FROM estados_documento')
        estados_dict = {e['nombre']: e['id'] for e in cursor.fetchall()}

        # 5. REGLA CRÍTICA B: Factura final generada ÚNICAMENTE cuando saldo <= 0
        numero_factura_asignado = factura.get('numero_factura')
        if saldo_posterior <= 0:
            estado_id_nuevo = estados_dict.get('Pagada', 1)
            if not numero_factura_asignado:
                numero_factura_asignado = numero
            cursor.execute('''
                UPDATE facturacion
                SET anticipo = %s, total_abonado = %s, saldo_pendiente = 0,
                    estado_id = %s, numero_factura = %s, proxima_pago_fecha = NULL, proxima_pago_monto = NULL
                WHERE numero = %s
            ''', (nuevo_total_abonado, nuevo_total_abonado, estado_id_nuevo, numero_factura_asignado, numero))
        else:
            estado_id_nuevo = estados_dict.get('Parcial') or estados_dict.get('Pendiente', 2)
            cursor.execute('''
                UPDATE facturacion
                SET anticipo = %s, total_abonado = %s, saldo_pendiente = %s,
                    estado_id = %s, proxima_pago_fecha = %s, proxima_pago_monto = %s
                WHERE numero = %s
            ''', (nuevo_total_abonado, nuevo_total_abonado, saldo_posterior, estado_id_nuevo, proxima_pago_fecha, proxima_pago_monto, numero))

        conn.commit()
        cursor.close()
        conn.close()

        registrar_log(
            'REGISTRAR_ABONO',
            f"Abono #{numero_pago} de ${monto_abono:.2f} registrado en {numero}. Comprobante: {numero_comprobante}. Saldo restante: ${saldo_posterior:.2f}"
        )

        if saldo_posterior <= 0:
            flash(
                f'¡Abono de ${monto_abono:.2f} registrado exitosamente! Se emitió el Comprobante de Pago "{numero_comprobante}". '
                f'La deuda ha sido liquidada y se ha generado el comprobante de venta Nº "{numero_factura_asignado}".',
                'success'
            )
            return redirect(url_for('ver_comprobante_venta', numero=numero))
        else:
            flash(
                f'Abono de ${monto_abono:.2f} registrado exitosamente. Se emitió el Comprobante de Pago "{numero_comprobante}". '
                f'Saldo pendiente actual: ${saldo_posterior:.2f}. El comprobante final estará disponible al completar el pago.',
                'info'
            )
            return redirect(url_for('ver_comprobante_pago', numero_comprobante=numero_comprobante))

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        flash(f'Ocurrió un error inesperado al procesar el pago: {str(e)}', 'danger')
        return redirect(url_for('facturacion'))


@app.route('/facturacion/comprobante-pago/<numero_comprobante>')
@role_required('Administrador', 'Encargado', 'Vendedor', 'Cliente')
@permission_required('facturas.ver')
def ver_comprobante_pago(numero_comprobante):
    """
    Genera la vista imprimible del Comprobante de Pago emitido por un abono.
    Un comprobante de pago NO es una factura.
    """
    asegurar_campos_cliente()
    asegurar_snapshots_documentos()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT cp.*, p.metodo_pago, p.referencia, p.notas,
               COALESCE(cp.cliente_nombre_snapshot, c.nombre) AS cliente_nombre,
               COALESCE(cp.cliente_apellido_snapshot, c.apellido) AS cliente_apellido,
               COALESCE(cp.cliente_correo_snapshot, c.correo) AS cliente_correo,
               COALESCE(cp.cliente_telefono_snapshot, c.telefono) AS cliente_telefono,
               COALESCE(cp.cliente_direccion_snapshot, c.direccion) AS cliente_direccion,
               COALESCE(cp.cliente_ciudad_snapshot, c.ciudad) AS cliente_ciudad,
               c.correo AS cliente_correo_actual,
               f.tipo AS doc_tipo
        FROM comprobantes_pago cp
        JOIN pagos_factura p ON cp.pago_id = p.id
        JOIN clientes c ON cp.cliente_cedula = c.cedula
        JOIN facturacion f ON cp.factura_numero = f.numero
        WHERE cp.numero_comprobante = %s
    ''', (numero_comprobante,))
    fila = cursor.fetchone()

    if not fila:
        cursor.close()
        conn.close()
        flash(f'El comprobante de pago "{numero_comprobante}" no fue encontrado.', 'danger')
        return redirect(url_for('facturacion'))

    if current_user.rol_nombre == 'Cliente':
        cliente_correo = (fila.get('cliente_correo_actual') or '').strip().lower()
        cliente_cedula = (fila.get('cliente_cedula') or '').strip()
        usuario_actual = current_user.usuario.strip().lower()
        correo_actual = current_user.correo.strip().lower()
        if (correo_actual != cliente_correo and usuario_actual != cliente_cedula.lower()):
            cursor.close()
            conn.close()
            flash('No tienes autorización para ver comprobantes de otros clientes.', 'danger')
            return redirect(url_for('facturacion'))

    cursor.close()
    conn.close()
    return render_template('comprobante_pago.html', comprobante=dict(fila))


@app.route('/facturacion/comprobante-venta/<numero>')
@role_required('Administrador', 'Encargado', 'Vendedor', 'Cliente')
@permission_required('facturas.ver')
def ver_comprobante_venta(numero):
    """
    Genera el comprobante comercial final cuando la venta está completamente pagada.
    """
    asegurar_campos_cliente()
    asegurar_snapshots_documentos()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT f.*,
               COALESCE(f.cliente_nombre_snapshot, c.nombre) AS cliente_nombre,
               COALESCE(f.cliente_apellido_snapshot, c.apellido) AS cliente_apellido,
               COALESCE(f.cliente_correo_snapshot, c.correo) AS cliente_correo,
               COALESCE(f.cliente_telefono_snapshot, c.telefono) AS cliente_telefono,
               COALESCE(f.cliente_direccion_snapshot, c.direccion) AS cliente_direccion,
               COALESCE(f.cliente_ciudad_snapshot, c.ciudad) AS cliente_ciudad,
               c.correo AS cliente_correo_actual,
               e.nombre AS estado_nombre
        FROM facturacion f
        JOIN clientes c ON f.cliente_cedula = c.cedula
        JOIN estados_documento e ON f.estado_id = e.id
        WHERE f.numero = %s
    ''', (numero,))
    fila = cursor.fetchone()

    if not fila:
        cursor.close()
        conn.close()
        flash('El documento seleccionado no existe.', 'danger')
        return redirect(url_for('facturacion'))

    factura = dict(fila)

    saldo_pendiente = float(factura.get('saldo_pendiente') or 0.0)
    if saldo_pendiente > 0:
        cursor.close()
        conn.close()
        registrar_log(
            'ACCESO_DENEGADO_COMPROBANTE_SALDO_PENDIENTE',
            f"Intento de ver factura para {numero} con saldo pendiente de ${saldo_pendiente:.2f}"
        )
        flash(
            f'Acceso bloqueado: el documento "{numero}" '
            f'tiene un saldo pendiente de ${saldo_pendiente:.2f}. '
            'El comprobante final estará disponible cuando el pago quede liquidado.',
            'warning'
        )
        return redirect(url_for('facturacion'))

    if current_user.rol_nombre == 'Cliente':
        cliente_correo = (factura.get('cliente_correo_actual') or '').strip().lower()
        cliente_cedula = (factura.get('cliente_cedula') or '').strip()
        usuario_actual = current_user.usuario.strip().lower()
        correo_actual = current_user.correo.strip().lower()
        if (correo_actual != cliente_correo and usuario_actual != cliente_cedula.lower()):
            cursor.close()
            conn.close()
            flash('No tienes autorización para ver facturas de otros clientes.', 'danger')
            return redirect(url_for('facturacion'))

    cursor.execute('SELECT * FROM detalle_factura WHERE factura_numero = %s', (numero,))
    detalle = cursor.fetchall()
    factura['productos_detalle'] = [
        {'id': d['producto_id'], 'producto': d['nombre_producto'], 'cantidad': d['cantidad'],
         'precio': d['precio_base'], 'ajuste': d['ajuste'], 'total': d['total'],
         'descripcion': d.get('descripcion_linea'), 'unidad_medida': d.get('unidad_medida'),
         'es_adicional': bool(d.get('es_adicional'))}
        for d in detalle
    ]

    cursor.execute('''
        SELECT p.*, cp.numero_comprobante
        FROM pagos_factura p
        LEFT JOIN comprobantes_pago cp ON cp.pago_id = p.id
        WHERE p.factura_numero = %s
        ORDER BY p.numero_pago ASC
    ''', (numero,))
    factura['pagos'] = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('comprobante_factura.html', factura=factura, numero=numero)


@app.route('/facturacion/eliminar/<numero>', methods=['POST'])
@role_required('Administrador')
@permission_required('facturas.eliminar')
def eliminar_factura(numero):
    """
    Elimina un documento comercial identificado por su número.
    El detalle, pagos, comprobantes y pagos asociadas se borran automáticamente (ON DELETE CASCADE).
    Acceso exclusivo para el rol Administrador.
    """
    asegurar_inventario_base()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM facturacion WHERE numero = %s FOR UPDATE', (numero,))
    fila = cursor.fetchone()

    if fila is None:
        cursor.close()
        conn.close()
        flash('El documento seleccionado no existe.', 'danger')
        return redirect(url_for('facturacion'))

    tipo_str = "Cotización" if fila['tipo'] == 'Cotizacion' else "Factura"

    if fila['tipo'] == 'Factura':
        error_stock = ajustar_kardex_venta(
            cursor, numero, [], current_user.id, 'Cotizacion'
        )
        if error_stock:
            conn.rollback()
            cursor.close()
            conn.close()
            flash(error_stock, 'danger')
            return redirect(url_for('facturacion'))

    cursor.execute('DELETE FROM facturacion WHERE numero = %s', (numero,))
    conn.commit()
    cursor.close()
    conn.close()

    registrar_log('ELIMINAR_FACTURA', f"{tipo_str} {numero} eliminada por {current_user.usuario}")
    flash(f'{tipo_str} "{numero}" eliminada correctamente.', 'success')
    return redirect(url_for('facturacion'))


@app.route('/facturacion/comprobante/<numero>')
@role_required('Administrador', 'Encargado', 'Cliente')
@permission_required('facturas.ver_propias')
def ver_comprobante(numero):
    """
    Ruta compatible con accesos directos previos.
    - Si es Cotización: la muestra.
    - Si la venta tiene saldo cero: redirige al comprobante de venta.
    - Si es Factura con saldo > 0: redirige al último Comprobante de Pago emitido.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT f.*, c.nombre AS cliente_nombre, c.correo AS cliente_correo,
               c.telefono AS cliente_telefono, c.ciudad AS cliente_ciudad,
               e.nombre AS estado_nombre
        FROM facturacion f
        JOIN clientes c ON f.cliente_cedula = c.cedula
        JOIN estados_documento e ON f.estado_id = e.id
        WHERE f.numero = %s
    ''', (numero,))
    fila = cursor.fetchone()

    if fila is None:
        cursor.close()
        conn.close()
        flash('El documento seleccionado no existe.', 'danger')
        return redirect(url_for('facturacion'))

    factura = dict(fila)

    if factura['tipo'] == 'Cotizacion':
        if current_user.rol_nombre == 'Cliente':
            cliente_correo = (factura.get('cliente_correo') or '').strip().lower()
            cliente_cedula = (factura.get('cliente_cedula') or '').strip()
            usuario_actual = current_user.usuario.strip().lower()
            correo_actual = current_user.correo.strip().lower()
            if (correo_actual != cliente_correo and usuario_actual != cliente_cedula.lower()):
                cursor.close()
                conn.close()
                flash('No tienes autorización para ver cotizaciones emitidas a otros clientes.', 'danger')
                return redirect(url_for('facturacion'))

        cursor.execute('SELECT * FROM detalle_factura WHERE factura_numero = %s', (numero,))
        detalle = cursor.fetchall()
        cursor.close()
        conn.close()
        factura['productos_detalle'] = [
            {'id': d['producto_id'], 'producto': d['nombre_producto'], 'cantidad': d['cantidad'],
             'precio': d['precio_base'], 'ajuste': d['ajuste'], 'total': d['total'],
             'descripcion': d.get('descripcion_linea'), 'unidad_medida': d.get('unidad_medida'),
             'es_adicional': bool(d.get('es_adicional'))}
            for d in detalle
        ]
        return render_template('comprobante_factura.html', factura=factura, numero=numero)

    # Es Factura / Venta
    saldo = float(factura.get('saldo_pendiente') or 0.0)
    if saldo <= 0:
        cursor.close()
        conn.close()
        return redirect(url_for('ver_comprobante_venta', numero=numero))
    else:
        cursor.execute(
            'SELECT numero_comprobante FROM comprobantes_pago WHERE factura_numero = %s ORDER BY id DESC LIMIT 1',
            (numero,)
        )
        comp = cursor.fetchone()
        cursor.close()
        conn.close()
        if comp:
            flash('Este documento tiene saldo pendiente. Mostrando el último comprobante de pago emitido.', 'info')
            return redirect(url_for('ver_comprobante_pago', numero_comprobante=comp['numero_comprobante']))
        else:
            flash(f'El documento {numero} tiene un saldo pendiente de ${saldo:.2f} y aún no registra abonos.', 'warning')
            return redirect(url_for('facturacion'))



# ==============================================================================
# MÓDULO: PANEL DE ESTADÍSTICAS (solo lectura)
# ==============================================================================
# Panel de resultados para la toma de decisiones del negocio. Muestra qué
# productos son los más solicitados, usando una consulta RELACIONADA entre dos
# tablas (detalle_factura y productos) mediante la clave foránea producto_id.
# Cumple el requisito de "consulta relacionada entre dos tablas con JOIN".

@app.route('/estadisticas')
@role_required('Administrador', 'Encargado', 'Cliente')
@permission_required('reportes.ver')
def estadisticas():
    """
    Pulso diario de ventas, demanda de productos, pedidos e inventario.
    Los indicadores de producción y reseñas no se estiman si no tienen registros.
    """
    asegurar_detalles_factura()
    conn = get_db_connection()
    cursor = conn.cursor()
    es_cliente = (current_user.rol_nombre == 'Cliente')
    filtro_cliente = '''
        AND (LOWER(TRIM(c.correo)) = LOWER(TRIM(%s)) OR c.cedula = %s)
    ''' if es_cliente else ''
    parametros_cliente = (current_user.correo, current_user.usuario) if es_cliente else ()

    if es_cliente:
        cursor.execute('''
            SELECT s.id AS producto_id, s.nombre AS producto, s.imagen,
                   t.nombre AS categoria, SUM(d.cantidad) AS unidades,
                   SUM(d.total) AS ingresos
            FROM detalle_factura d
            JOIN facturacion f ON f.numero = d.factura_numero
            JOIN estados_documento e ON e.id = f.estado_id
            JOIN clientes c ON c.cedula = f.cliente_cedula
            JOIN productos s ON d.producto_id = s.id
            JOIN categorias_producto t ON s.categoria_producto_id = t.id
            WHERE f.tipo = 'Factura' AND d.es_adicional = FALSE
              AND POSITION('cancel' IN LOWER(e.nombre)) = 0
              AND POSITION('anulad' IN LOWER(e.nombre)) = 0
            {filtro_cliente}
            GROUP BY s.id, s.nombre, s.imagen, t.nombre
            ORDER BY unidades DESC, s.nombre ASC
        '''.format(filtro_cliente=filtro_cliente), parametros_cliente)
    else:
        cursor.execute('''
            SELECT s.id AS producto_id, s.nombre AS producto, s.imagen,
                   t.nombre AS categoria,
                   SUM(d.cantidad) AS unidades,
                   SUM(d.total) AS ingresos
            FROM detalle_factura d
            JOIN facturacion f ON f.numero = d.factura_numero
            JOIN estados_documento e ON e.id = f.estado_id
            JOIN productos s ON d.producto_id = s.id
            JOIN categorias_producto t ON s.categoria_producto_id = t.id
            WHERE f.tipo = 'Factura' AND d.es_adicional = FALSE
              AND POSITION('cancel' IN LOWER(e.nombre)) = 0
              AND POSITION('anulad' IN LOWER(e.nombre)) = 0
            GROUP BY s.id, s.nombre, s.imagen, t.nombre
            ORDER BY unidades DESC, s.nombre ASC
        ''')
    ranking = cursor.fetchall()

    cursor.execute('''
        SELECT COUNT(*) AS pedidos_hoy,
               COALESCE(SUM(f.monto), 0) AS ventas_hoy
        FROM facturacion f
        JOIN estados_documento e ON e.id = f.estado_id
        JOIN clientes c ON c.cedula = f.cliente_cedula
        WHERE f.tipo = 'Factura' AND f.fecha = CURRENT_DATE
          AND POSITION('cancel' IN LOWER(e.nombre)) = 0
          AND POSITION('anulad' IN LOWER(e.nombre)) = 0
        {filtro_cliente}
    '''.format(filtro_cliente=filtro_cliente), parametros_cliente)
    resumen_hoy = cursor.fetchone()

    cursor.execute('''
        SELECT s.nombre AS producto, s.imagen, SUM(d.cantidad) AS unidades
        FROM detalle_factura d
        JOIN facturacion f ON f.numero = d.factura_numero
        JOIN estados_documento e ON e.id = f.estado_id
        JOIN clientes c ON c.cedula = f.cliente_cedula
        JOIN productos s ON s.id = d.producto_id
        WHERE f.tipo = 'Factura' AND f.fecha = CURRENT_DATE
          AND d.es_adicional = FALSE
          AND POSITION('cancel' IN LOWER(e.nombre)) = 0
          AND POSITION('anulad' IN LOWER(e.nombre)) = 0
        {filtro_cliente}
        GROUP BY s.id, s.nombre, s.imagen
        ORDER BY unidades DESC, s.nombre ASC
        LIMIT 1
    '''.format(filtro_cliente=filtro_cliente), parametros_cliente)
    producto_estrella_hoy = cursor.fetchone()

    cursor.execute('''
        SELECT s.nombre AS producto, s.imagen, SUM(d.cantidad) AS unidades
        FROM detalle_factura d
        JOIN facturacion f ON f.numero = d.factura_numero
        JOIN estados_documento e ON e.id = f.estado_id
        JOIN clientes c ON c.cedula = f.cliente_cedula
        JOIN productos s ON s.id = d.producto_id
        WHERE f.tipo = 'Factura'
          AND f.fecha >= date_trunc('month', CURRENT_DATE)::date
          AND d.es_adicional = FALSE
          AND POSITION('cancel' IN LOWER(e.nombre)) = 0
          AND POSITION('anulad' IN LOWER(e.nombre)) = 0
        {filtro_cliente}
        GROUP BY s.id, s.nombre, s.imagen
        ORDER BY unidades DESC, s.nombre ASC
        LIMIT 1
    '''.format(filtro_cliente=filtro_cliente), parametros_cliente)
    producto_estrella_mes = cursor.fetchone()

    if es_cliente:
        cursor.execute('''
            SELECT f.numero, f.fecha_entrega, f.monto, c.nombre AS cliente,
                   (SELECT string_agg(d.nombre_producto, ', ' ORDER BY d.id)
                    FROM detalle_factura d
                    WHERE d.factura_numero = f.numero AND d.es_adicional = FALSE) AS productos
            FROM facturacion f
            JOIN clientes c ON c.cedula = f.cliente_cedula
            JOIN estados_documento e ON e.id = f.estado_id
            WHERE f.tipo = 'Factura'
              AND f.fecha_entrega >= CURRENT_DATE
              AND f.fecha_entrega < CURRENT_DATE + INTERVAL '3 days'
              AND POSITION('cancel' IN LOWER(e.nombre)) = 0
              AND POSITION('anulad' IN LOWER(e.nombre)) = 0
              {filtro_cliente}
            ORDER BY f.fecha_entrega, f.numero
            LIMIT 8
        '''.format(filtro_cliente=filtro_cliente), parametros_cliente)
    else:
        cursor.execute('''
            SELECT f.numero, f.fecha_entrega, f.monto, c.nombre AS cliente,
                   (SELECT string_agg(d.nombre_producto, ', ' ORDER BY d.id)
                    FROM detalle_factura d
                    WHERE d.factura_numero = f.numero AND d.es_adicional = FALSE) AS productos
            FROM facturacion f
            JOIN clientes c ON c.cedula = f.cliente_cedula
            JOIN estados_documento e ON e.id = f.estado_id
            WHERE f.tipo = 'Factura'
              AND f.fecha_entrega >= CURRENT_DATE
              AND f.fecha_entrega < CURRENT_DATE + INTERVAL '3 days'
              AND POSITION('cancel' IN LOWER(e.nombre)) = 0
              AND POSITION('anulad' IN LOWER(e.nombre)) = 0
            ORDER BY f.fecha_entrega, f.numero
            LIMIT 8
        ''')
    pedidos_proximos = cursor.fetchall()

    alertas_inventario = []
    if not es_cliente:
        cursor.execute('''
            SELECT p.id, p.nombre AS producto, p.stock_actual, p.stock_minimo,
                   c.nombre AS categoria
            FROM productos p
            JOIN categorias_producto c ON c.id = p.categoria_producto_id
            WHERE p.disponible = TRUE
              AND p.stock_minimo > 0
              AND p.stock_actual <= p.stock_minimo
            ORDER BY p.stock_actual ASC, p.nombre ASC
            LIMIT 5
        ''')
        alertas_inventario = cursor.fetchall()

    cursor.close()
    conn.close()

    producto_top = producto_estrella_mes['producto'] if producto_estrella_mes else 'Sin ventas este mes'
    fila_mayor_ingreso = (
        max(ranking, key=lambda fila: fila['ingresos'] or 0)
        if ranking and not es_cliente else None
    )
    producto_mayor_ingreso = fila_mayor_ingreso['producto'] if fila_mayor_ingreso else 'Sin datos aún'
    mayor_ingreso_monto = float(fila_mayor_ingreso['ingresos'] or 0.0) if fila_mayor_ingreso else 0.0

    max_unidades = max((fila['unidades'] for fila in ranking), default=0)
    total_unidades = sum((fila['unidades'] for fila in ranking), 0)

    return render_template(
        'estadisticas.html',
        ranking=ranking,
        total_unidades=total_unidades,
        producto_top=producto_top,
        producto_mayor_ingreso=producto_mayor_ingreso,
        mayor_ingreso_monto=mayor_ingreso_monto,
        max_unidades=max_unidades,
        es_cliente=es_cliente,
        resumen_hoy=resumen_hoy,
        producto_estrella_hoy=producto_estrella_hoy,
        producto_estrella_mes=producto_estrella_mes,
        pedidos_proximos=pedidos_proximos,
        alertas_inventario=alertas_inventario,
    )


# ==============================================================================
# MANEJADORES DE ERRORES PERSONALIZADOS (404, 403, 500)
# ==============================================================================

@app.errorhandler(404)
def error_404(e):
    """Manejo elegante de rutas inexistentes o recursos no encontrados."""
    return render_template('404.html'), 404


@app.errorhandler(403)
def error_403(e):
    """Manejo de acceso denegado por falta de permisos o roles."""
    registrar_log('ERROR_403_ACCESO_PROHIBIDO', f"Ruta: {request.path}")
    return render_template('403.html'), 403


@app.errorhandler(psycopg2.Error)
def error_postgresql(e):
    """Evita mostrar un 500 genérico cuando PostgreSQL está temporalmente ocupado."""
    app.logger.exception('Error de PostgreSQL en %s.', request.path)
    return render_template(
        '500.html',
        codigo_http=503,
        titulo_error='Base de datos temporalmente no disponible',
        mensaje_error='La operación no se completó. Tus datos no se guardaron o quedaron a medias; inténtalo nuevamente en unos segundos.'
    ), 503


@app.errorhandler(500)
def error_500(e):
    """Manejo de errores internos del servidor o desconexión de base de datos."""
    registrar_log('ERROR_500_SERVIDOR', f"Excepción interna en {request.path}: {str(e)}")
    return render_template('500.html'), 500


@app.errorhandler(Exception)
def error_general(e):
    """
    Captura global de excepciones no controladas en producción.
    Si estamos en modo DEBUG de desarrollo, permite la propagación para que Flask
    muestre el depurador detallado en consola.
    """
    if app.debug:
        raise e
    if isinstance(e, HTTPException):
        codigo = e.code or 500
        errores_conocidos = {
            400: (
                'La solicitud necesita una revisión',
                'No pudimos interpretar la información enviada. Revisa los datos y vuelve a intentarlo.',
            ),
            401: (
                'Inicia sesión para continuar',
                'Esta parte de la pastelería requiere una cuenta autorizada.',
            ),
            405: (
                'Esta acción no está disponible aquí',
                'La página no acepta esta forma de acceso. Regresa al panel y continúa desde sus opciones.',
            ),
            408: (
                'La solicitud tardó demasiado',
                'La operación no llegó a tiempo. Actualiza la página e inténtalo nuevamente.',
            ),
            413: (
                'La imagen es demasiado grande',
                'El archivo supera el tamaño permitido. Elige una imagen más liviana e inténtalo de nuevo.',
            ),
            429: (
                'Necesitamos un momento',
                'Se realizaron demasiadas solicitudes seguidas. Espera un poco y vuelve a intentarlo.',
            ),
            502: (
                'Estamos preparando el pedido',
                'Uno de nuestros servicios no respondió correctamente. Inténtalo de nuevo en un momento.',
            ),
            503: (
                'El servidor está temporalmente ocupado',
                'No pudimos atender esta solicitud ahora. Espera un momento y vuelve a intentarlo.',
            ),
            504: (
                'La respuesta está tardando',
                'El servicio no respondió a tiempo. Inténtalo nuevamente en unos momentos.',
            ),
        }
        titulo, mensaje = errores_conocidos.get(
            codigo,
            ('Esta página no está disponible por ahora', 'Vuelve al inicio y continúa desde las opciones disponibles.'),
        )
        return render_template(
            '500.html',
            codigo_http=codigo,
            titulo_error=titulo,
            mensaje_error=mensaje,
        ), codigo
    registrar_log('EXCEPCION_NO_CONTROLADA', f"Error en {request.path}: {str(e)}")
    return render_template(
        '500.html',
        codigo_http=500,
        titulo_error='Tuvimos un contratiempo en el servidor',
        mensaje_error='No pudimos completar esta solicitud. Inténtalo de nuevo en un momento; si el problema continúa, avisa al equipo de Dulce Delicia.',
    ), 500


# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL DE LA APLICACIÓN
# ==============================================================================

# Aplica migraciones idempotentes al arrancar para que las consultas que
# usan columnas nuevas (es_insumo, costo_unitario) no fallen en producción.
try:
    with app.app_context():
        asegurar_inventario_base()
except Exception as error_migracion:
    app.logger.warning('No se pudo aplicar la migración de inventario al iniciar: %s', error_migracion)


if __name__ == '__main__':
    # Render proporciona el puerto mediante la variable PORT.
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', '5000')),
        debug=os.getenv('FLASK_DEBUG', '').lower() == 'true'
    )
