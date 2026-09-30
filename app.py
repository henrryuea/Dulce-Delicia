"""Rutas Flask del sistema administrativo y sitio público de Dulce Delicia."""

# ===============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS Y MÓDULOS DE PYTHON Y FLASK
# ===============================================================================
import os
import secrets
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from getpass import getpass
from urllib.parse import urlsplit
from flask import (
    Flask,                           # Clase constructora de la app web
    render_template,                 # Procesamiento de plantillas HTML con Jinja2
    request,                         # Acceso a los datos de peticiones HTTP
    redirect,                        # Redireccionamiento entre vistas
    url_for,                         # Generador de rutas seguras por nombre de función
    flash,                           # Envío de notificaciones temporales al usuario
    session,                         # Almacén de sesiones cifradas del navegador
    send_file,                        # Sirve la portada estática externa
    jsonify
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

# Importamos las clases de formularios desarrolladas en la carpeta forms/
from forms import (
    ProductoForm,                    # Formulario para postres (3FN)
    ClienteForm,                     # Formulario para clientes (3FN)
    ProveedorForm,                   # Formulario para proveedores (3FN)
    FacturacionForm,                 # Formulario para facturación (3FN)
    AbonoForm,
    LoginForm,
    InventarioForm,
    RegistroForm
)


# ==============================================================================
# 2. INICIALIZACIÓN Y CONFIGURACIÓN DE FLASK
# ==============================================================================
app = Flask(__name__)

_secret_key = os.environ.get('SECRET_KEY')
if os.environ.get('DATABASE_URL') and not _secret_key:
    raise RuntimeError('Configure SECRET_KEY en el entorno antes de iniciar en producción.')
if _secret_key and len(_secret_key) < 32:
    raise RuntimeError('SECRET_KEY debe tener al menos 32 caracteres aleatorios.')
app.config.update(
    SECRET_KEY=_secret_key or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=bool(os.environ.get('DATABASE_URL') or os.environ.get('RENDER')),
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
)
csrf = CSRFProtect(app)

from database import (
    BASE_DIR,
    obtener_conexion,
    guardar_imagen_producto,
    sincronizar_opciones_producto,
    sincronizar_opciones_cliente,
    sincronizar_opciones_proveedor,
    USE_POSTGRES,
    INTEGRITY_ERRORS
)

app.logger.setLevel(logging.INFO)


def _database_unavailable(error):
    app.logger.error('Database operation failed: %s', error)
    return 'El servicio de base de datos no está disponible. Intente nuevamente.', 503


app.register_error_handler(sqlite3.OperationalError, _database_unavailable)
if USE_POSTGRES:
    import psycopg
    app.register_error_handler(psycopg.OperationalError, _database_unavailable)


@app.after_request
def aplicar_cabeceras_seguras(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    if app.config['SESSION_COOKIE_SECURE']:
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response

_admin_username = os.environ.get('ADMIN_USERNAME', '').strip().lower()
_admin_password = os.environ.get('ADMIN_PASSWORD', '')
_dummy_password_hash = generate_password_hash(secrets.token_urlsafe(32))
if bool(_admin_username) != bool(_admin_password):
    raise RuntimeError('Configure ADMIN_USERNAME y ADMIN_PASSWORD juntos o cree el usuario con flask crear-admin.')
if _admin_username:
    if (len(_admin_username) < 3 or len(_admin_username) > 30 or
            len(_admin_password) < 12 or len(_admin_password) > 128):
        raise RuntimeError('El administrador inicial requiere usuario de 3-30 caracteres y contraseña de 12-128.')
    with obtener_conexion() as _connection:
        _connection.execute(
            "INSERT INTO usuarios (usuario, password_hash, rol, estado) "
            "VALUES (?, ?, 'ADMIN', 'ACTIVO') ON CONFLICT(usuario) DO NOTHING",
            (_admin_username, generate_password_hash(_admin_password))
        )
        bootstrap_account = _connection.execute(
            'SELECT rol, estado FROM usuarios WHERE usuario = ?', (_admin_username,)
        ).fetchone()
        if not bootstrap_account or bootstrap_account['rol'] != 'ADMIN' or bootstrap_account['estado'] != 'ACTIVO':
            raise RuntimeError(
                'ADMIN_USERNAME ya pertenece a una cuenta que no es administradora; '
                'configure otro usuario de arranque.'
            )
        _connection.commit()


# ==============================================================================
# 6. SEGURIDAD: DECORADOR DE SESIÓN ADMINISTRATIVA
# ==============================================================================
def login_required(f):
    """
    Decorador que valida la existencia de la sesión activa del usuario.
    Si el usuario no ha iniciado sesión, es redirigido a /login.
    """
    @wraps(f)
    def decorada(*args, **kwargs):
        cuenta = _cuenta_sesion_activa()
        if not cuenta:
            flash('Debe iniciar sesión para acceder al sistema administrativo.', 'warning')
            return redirect(url_for('login'))
        if cuenta['rol'] == 'CLIENTE':
            return redirect(url_for('mi_cuenta'))
        return f(*args, **kwargs)
    return decorada


def _cuenta_sesion_activa():
    id_usuario = session.get('id_usuario')
    if not id_usuario:
        return None
    conn = obtener_conexion()
    cuenta = conn.execute('''
        SELECT id_usuario, usuario, rol, estado, id_cliente
        FROM usuarios
        WHERE id_usuario = ? AND activo = 1 AND estado = 'ACTIVO'
    ''', (id_usuario,)).fetchone()
    conn.close()
    if not cuenta:
        session.clear()
    return cuenta


def admin_required(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        cuenta = _cuenta_sesion_activa()
        if not cuenta:
            flash('Inicie sesión con una cuenta autorizada.', 'warning')
            return redirect(url_for('login'))
        if cuenta['rol'] != 'ADMIN':
            flash('Esta operación requiere autorización de un administrador.', 'danger')
            return redirect(url_for('panel'))
        return f(*args, **kwargs)
    return decorada


def cliente_required(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        cuenta = _cuenta_sesion_activa()
        if not cuenta:
            flash('Inicie sesión para consultar su cuenta.', 'warning')
            return redirect(url_for('login'))
        if cuenta['rol'] != 'CLIENTE' or not cuenta['id_cliente']:
            return redirect(url_for('panel'))
        return f(*args, **kwargs)
    return decorada


# ==============================================================================
# 7. MÓDULO DE AUTENTICACIÓN (LOGIN Y LOGOUT)
# ==============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Autentica cuentas aprobadas y redirige según el rol asignado."""
    cuenta_sesion = _cuenta_sesion_activa()
    if cuenta_sesion:
        return redirect(url_for('mi_cuenta' if cuenta_sesion['rol'] == 'CLIENTE' else 'panel'))

    form = LoginForm()
    if form.validate_on_submit():
        conn = obtener_conexion()
        _iniciar_transaccion(conn)
        usuario = form.usuario.data.strip()
        consulta_usuario = (
            'SELECT id_usuario, usuario, password_hash, intentos_fallidos, bloqueado_hasta, '
            'rol, estado, id_cliente FROM usuarios WHERE LOWER(usuario) = LOWER(?) AND activo = 1'
        )
        if USE_POSTGRES:
            consulta_usuario += ' FOR UPDATE'
        cuenta = conn.execute(consulta_usuario, (usuario,)).fetchone()
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        bloqueado = bool(cuenta and cuenta['bloqueado_hasta'] and
                         datetime.fromisoformat(cuenta['bloqueado_hasta']) > ahora)
        password_correcta = check_password_hash(
            cuenta['password_hash'] if cuenta else _dummy_password_hash,
            form.password.data
        )

        if cuenta and not bloqueado and password_correcta and cuenta['estado'] == 'ACTIVO':
            conn.execute(
                'UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL, ultimo_acceso = ? '
                'WHERE id_usuario = ?',
                (ahora.isoformat(timespec='seconds'), cuenta['id_usuario'])
            )
            conn.commit()
            conn.close()
            session.clear()
            session.permanent = True
            session['usuario'] = cuenta['usuario']
            session['id_usuario'] = cuenta['id_usuario']
            session['rol'] = cuenta['rol']
            session['id_cliente'] = cuenta['id_cliente']
            destino = request.args.get('next', '')
            parsed = urlsplit(destino)
            if destino.startswith('/') and not destino.startswith('//') and not parsed.netloc and not parsed.scheme:
                return redirect(destino)
            return redirect(url_for('mi_cuenta' if cuenta['rol'] == 'CLIENTE' else 'panel'))

        if cuenta and not bloqueado and not password_correcta:
            intentos = int(cuenta['intentos_fallidos']) + 1
            bloqueado_hasta = (ahora + timedelta(minutes=15)).isoformat(timespec='seconds') if intentos >= 5 else None
            conn.execute(
                'UPDATE usuarios SET intentos_fallidos = ?, bloqueado_hasta = ? WHERE id_usuario = ?',
                (intentos, bloqueado_hasta, cuenta['id_usuario'])
            )
            conn.commit()
        conn.close()
        if cuenta and password_correcta and cuenta['estado'] == 'PENDIENTE':
            flash('La solicitud está pendiente de aprobación del administrador.', 'warning')
        elif cuenta and password_correcta and cuenta['estado'] == 'RECHAZADO':
            flash('La solicitud de acceso no fue aprobada. Contacte al local.', 'danger')
        else:
            flash('Usuario o contraseña incorrectos, o cuenta temporalmente bloqueada.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout', methods=['POST'])
def logout():
    """Cierra la sesión administrativa y vuelve a la portada pública."""
    session.clear()
    flash('Ha cerrado su sesión correctamente.', 'info')
    return redirect(url_for('inicio'))


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if _cuenta_sesion_activa():
        return redirect(url_for('inicio'))
    form = RegistroForm()
    if form.validate_on_submit():
        conn = obtener_conexion()
        try:
            _iniciar_transaccion(conn)
            usuario = form.usuario.data.strip().lower()
            correo = form.correo.data.strip().lower()
            rol = form.rol_solicitado.data
            cliente = None
            if rol == 'CLIENTE':
                identificacion = (form.cedula_ruc.data or '').strip()
                if not identificacion:
                    raise ValueError('Ingrese su cédula o RUC para solicitar una cuenta de cliente.')
                cliente = conn.execute(
                    'SELECT id_cliente, correo FROM clientes WHERE cedula_ruc = ?',
                    (identificacion,)
                ).fetchone()
                if cliente:
                    if (cliente['correo'] or '').strip().lower() != correo:
                        raise ValueError(
                            'La identificación existe con otro correo. Contacte al local para validar sus datos.'
                        )
                    cuenta_cliente = conn.execute(
                        'SELECT 1 FROM usuarios WHERE id_cliente = ?',
                        (cliente['id_cliente'],)
                    ).fetchone()
                    if cuenta_cliente:
                        raise ValueError('El cliente ya tiene una cuenta o una solicitud registrada.')
                    id_cliente = cliente['id_cliente']
                else:
                    tipo = conn.execute(
                        "SELECT id_tipo_cliente FROM tipos_cliente WHERE nombre = 'PERSONA NATURAL'"
                    ).fetchone()
                    if not tipo:
                        raise RuntimeError('No está configurado el tipo de cliente PERSONA NATURAL.')
                    conn.execute('''
                        INSERT INTO clientes (
                            id_tipo_cliente, nombre, cedula_ruc, correo,
                            telefono, direccion, activo
                        ) VALUES (?, ?, ?, ?, NULL, NULL, 0)
                    ''', (
                        tipo['id_tipo_cliente'], form.nombre.data.strip(),
                        identificacion, correo
                    ))
                    id_cliente = conn.execute(
                        'SELECT id_cliente FROM clientes WHERE cedula_ruc = ?',
                        (identificacion,)
                    ).fetchone()['id_cliente']
            else:
                id_cliente = None

            conn.execute('''
                INSERT INTO usuarios (
                    usuario, password_hash, nombre, correo, rol,
                    estado, id_cliente
                ) VALUES (?, ?, ?, ?, ?, 'PENDIENTE', ?)
            ''', (
                usuario, generate_password_hash(form.password.data),
                form.nombre.data.strip(), correo, rol, id_cliente
            ))
            conn.commit()
            flash(
                'Solicitud recibida. Un administrador debe verificarla y aprobarla antes de habilitar el acceso.',
                'success'
            )
            return redirect(url_for('login'))
        except ValueError as error:
            conn.rollback()
            flash(str(error), 'danger')
        except INTEGRITY_ERRORS:
            conn.rollback()
            flash('Ese usuario, correo o identificación ya está registrado.', 'danger')
        finally:
            conn.close()
    return render_template('registro.html', form=form)


@app.route('/mi-cuenta')
@cliente_required
def mi_cuenta():
    cuenta = _cuenta_sesion_activa()
    conn = obtener_conexion()
    productos = conn.execute('''
        SELECT id_producto, codigo, nombre, descripcion, precio_venta,
               stock_actual, imagen
        FROM productos
        WHERE activo = 1 AND stock_actual > 0
        ORDER BY nombre
    ''').fetchall()
    facturas = conn.execute('''
        SELECT f.id_factura, f.numero, f.fecha_emision, f.subtotal, f.iva, f.total,
               mp.nombre AS metodo_pago
        FROM facturas f
        JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
        JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
        WHERE f.id_cliente = ? AND ef.nombre = 'EMITIDA'
        ORDER BY f.fecha_emision DESC, f.id_factura DESC
    ''', (cuenta['id_cliente'],)).fetchall()
    detalles = conn.execute('''
        SELECT df.id_factura, df.codigo_producto, df.nombre_producto,
               df.cantidad, df.precio_unitario, df.subtotal
        FROM detalle_factura df
        JOIN facturas f ON f.id_factura = df.id_factura
        JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
        WHERE f.id_cliente = ? AND ef.nombre = 'EMITIDA'
        ORDER BY df.id_factura, df.id_detalle
    ''', (cuenta['id_cliente'],)).fetchall()
    conn.close()
    detalles_por_factura = {}
    for detalle in detalles:
        detalles_por_factura.setdefault(detalle['id_factura'], []).append(detalle)
    return render_template(
        'mi_cuenta.html', cuenta=cuenta, productos=productos, facturas=facturas,
        detalles_por_factura=detalles_por_factura
    )


@app.route('/administracion/solicitudes')
@admin_required
def solicitudes_acceso():
    conn = obtener_conexion()
    solicitudes = conn.execute('''
        SELECT u.id_usuario, u.usuario, u.nombre, u.correo, u.rol,
               c.cedula_ruc, c.activo AS cliente_activo
        FROM usuarios u
        LEFT JOIN clientes c ON c.id_cliente = u.id_cliente
        WHERE u.estado = 'PENDIENTE' AND u.activo = 1
        ORDER BY u.id_usuario
    ''').fetchall()
    conn.close()
    return render_template('solicitudes_acceso.html', solicitudes=solicitudes)


@app.route('/administracion/solicitudes/<int:id>/<accion>', methods=['POST'])
@admin_required
def resolver_solicitud_acceso(id, accion):
    if accion not in {'aprobar', 'rechazar'}:
        flash('La acción solicitada no es válida.', 'danger')
        return redirect(url_for('solicitudes_acceso'))
    cuenta_admin = _cuenta_sesion_activa()
    conn = obtener_conexion()
    try:
        _iniciar_transaccion(conn)
        consulta = (
            "SELECT id_usuario, rol, id_cliente FROM usuarios "
            "WHERE id_usuario = ? AND estado = 'PENDIENTE' AND activo = 1"
        )
        if USE_POSTGRES:
            consulta += ' FOR UPDATE'
        solicitud = conn.execute(consulta, (id,)).fetchone()
        if not solicitud:
            raise ValueError('La solicitud ya fue atendida o no existe.')
        nuevo_estado = 'ACTIVO' if accion == 'aprobar' else 'RECHAZADO'
        conn.execute(
            'UPDATE usuarios SET estado = ?, revisado_por = ?, fecha_revision = ? '
            'WHERE id_usuario = ? AND estado = ?',
            (
                nuevo_estado, cuenta_admin['id_usuario'],
                datetime.now(timezone.utc).isoformat(timespec='seconds'),
                id, 'PENDIENTE'
            )
        )
        if accion == 'aprobar' and solicitud['rol'] == 'CLIENTE':
            conn.execute(
                'UPDATE clientes SET activo = 1 WHERE id_cliente = ?',
                (solicitud['id_cliente'],)
            )
        conn.commit()
        flash(
            'Acceso aprobado.' if accion == 'aprobar' else 'Solicitud rechazada.',
            'success' if accion == 'aprobar' else 'warning'
        )
    except ValueError as error:
        conn.rollback()
        flash(str(error), 'danger')
    finally:
        conn.close()
    return redirect(url_for('solicitudes_acceso'))


def _parsear_lineas_pedido():
    productos = request.form.getlist('producto_id')
    cantidades = request.form.getlist('cantidad')
    if not productos or len(productos) != len(cantidades) or len(productos) > 30:
        raise ValueError('Agregue entre 1 y 30 líneas válidas al pedido.')

    lineas = {}
    for producto, cantidad in zip(productos, cantidades):
        try:
            id_producto = int(producto)
            cantidad_decimal = Decimal(cantidad)
        except (ValueError, InvalidOperation):
            raise ValueError('Seleccione productos válidos e indique cantidades numéricas.')
        if (id_producto <= 0 or not cantidad_decimal.is_finite() or
                cantidad_decimal <= 0 or cantidad_decimal > Decimal('100000')):
            raise ValueError('Las cantidades deben estar entre 0.001 y 100000.')
        if cantidad_decimal != cantidad_decimal.quantize(Decimal('0.001')):
            raise ValueError('La cantidad admite hasta tres decimales.')
        lineas[id_producto] = lineas.get(id_producto, Decimal('0')) + cantidad_decimal
    return lineas


def _validar_decimal_entrada(valor, decimales, etiqueta):
    try:
        importe = Decimal(valor)
    except (TypeError, InvalidOperation):
        raise ValueError(f'Ingrese un valor numérico válido para {etiqueta}.')
    if not importe.is_finite():
        raise ValueError(f'Ingrese un valor numérico válido para {etiqueta}.')
    unidad = Decimal(1).scaleb(-decimales)
    if importe != importe.quantize(unidad):
        raise ValueError(f'{etiqueta} admite como máximo {decimales} decimales.')
    return importe


def _reservar_stock_pedido(conn, id_pedido, numero, lineas):
    ids = sorted(lineas)
    if not ids:
        raise ValueError('El pedido debe incluir al menos un producto.')
    marcadores = ','.join('?' for _ in ids)
    consulta = (
        'SELECT id_producto, codigo, nombre, precio_venta, stock_actual, activo '
        f'FROM productos WHERE id_producto IN ({marcadores}) ORDER BY id_producto'
    )
    if USE_POSTGRES:
        consulta += ' FOR UPDATE'
    productos = {
        int(producto['id_producto']): producto
        for producto in conn.execute(consulta, ids).fetchall()
    }
    if len(productos) != len(ids):
        raise ValueError('Uno de los productos seleccionados ya no existe.')

    subtotal = Decimal('0.00')
    detalles = []
    for id_producto, cantidad in lineas.items():
        producto = productos[id_producto]
        if not producto['activo']:
            raise ValueError(f'El producto "{producto["nombre"]}" está inactivo y no se puede vender.')
        stock = Decimal(str(producto['stock_actual']))
        if cantidad > stock:
            raise ValueError(
                f'Stock insuficiente para "{producto["nombre"]}". '
                f'Disponible: {stock:g}; solicitado: {cantidad:g}.'
            )
        precio = Decimal(str(producto['precio_venta']))
        total_linea = (precio * cantidad).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        subtotal += total_linea
        detalles.append((id_producto, cantidad, precio, total_linea))

    tipo_venta = conn.execute(
        "SELECT id_tipo_movimiento FROM tipos_movimiento_inventario WHERE nombre = 'RESERVA PEDIDO'"
    ).fetchone()
    if not tipo_venta:
        raise RuntimeError('Falta configurar el tipo de movimiento de inventario RESERVA PEDIDO.')
    for id_producto, cantidad in lineas.items():
        producto = productos[id_producto]
        stock_anterior = Decimal(str(producto['stock_actual']))
        stock_nuevo = stock_anterior - cantidad
        actualizacion = conn.execute(
            'UPDATE productos SET stock_actual = ? '
            'WHERE id_producto = ? AND stock_actual >= ?',
            (float(stock_nuevo), id_producto, float(cantidad))
        )
        if actualizacion.rowcount != 1:
            raise ValueError(f'El stock de "{producto["nombre"]}" cambió. Actualice la página e intente otra vez.')
        conn.execute(
            'INSERT INTO movimientos_inventario '
            '(id_producto, id_tipo_movimiento, cantidad, stock_anterior, stock_nuevo, referencia, observaciones) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                id_producto, tipo_venta['id_tipo_movimiento'], float(cantidad),
                float(stock_anterior), float(stock_nuevo), numero,
                'Reserva de stock por creación de pedido'
            )
        )

    for id_producto, cantidad, precio, total_linea in detalles:
        conn.execute(
            'INSERT INTO detalle_pedido '
            '(id_pedido, id_producto, codigo_producto, nombre_producto, cantidad, precio_unitario, descuento, subtotal) '
            'VALUES (?, ?, ?, ?, ?, ?, 0, ?)',
            (
                id_pedido, id_producto, productos[id_producto]['codigo'],
                productos[id_producto]['nombre'], _valor_numerico_db(cantidad),
                _valor_numerico_db(precio), _valor_numerico_db(total_linea)
            )
        )

    subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    iva = (subtotal * Decimal('0.15')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if subtotal + iva > Decimal('9999999999.99'):
        raise ValueError('El total del pedido supera el límite monetario permitido.')
    return subtotal, iva, subtotal + iva


def _iniciar_transaccion(conn):
    if not USE_POSTGRES:
        conn.execute('BEGIN IMMEDIATE')


def _valor_numerico_db(valor):
    return valor if USE_POSTGRES else float(valor)


@app.cli.command('crear-admin')
def crear_admin():
    """Crea una cuenta administrativa interactiva; no existe registro público."""
    usuario = input('Usuario administrador (3-30 caracteres): ').strip().lower()
    password = getpass('Contraseña (mínimo 12 caracteres): ')
    if not 3 <= len(usuario) <= 30 or not 12 <= len(password) <= 128:
        raise RuntimeError('El usuario debe tener 3-30 caracteres y la contraseña 12-128.')
    with obtener_conexion() as conn:
        conn.execute(
            "INSERT INTO usuarios (usuario, password_hash, rol, estado) "
            "VALUES (?, ?, 'ADMIN', 'ACTIVO')",
            (usuario, generate_password_hash(password))
        )
        conn.commit()
    print(f'Cuenta administrativa "{usuario}" creada.')


@app.cli.command('restablecer-admin')
def restablecer_admin():
    """Restablece una cuenta administrativa sin exponer la contraseña."""
    usuario = input('Usuario administrador existente: ').strip().lower()
    password = getpass('Nueva contraseña (mínimo 12 caracteres): ')
    if not usuario or not 12 <= len(password) <= 128:
        raise RuntimeError('Ingrese un usuario existente y una contraseña de 12-128 caracteres.')
    with obtener_conexion() as conn:
        resultado = conn.execute(
            "UPDATE usuarios SET password_hash = ?, rol = 'ADMIN', estado = 'ACTIVO', "
            'id_cliente = NULL, activo = 1, intentos_fallidos = 0, bloqueado_hasta = NULL '
            'WHERE LOWER(usuario) = LOWER(?)',
            (generate_password_hash(password), usuario)
        )
        if resultado.rowcount != 1:
            raise RuntimeError('No se encontró exactamente una cuenta para restablecer.')
        conn.commit()
    print(f'Contraseña de "{usuario}" restablecida de forma segura.')


# ==============================================================================
# 8. PANEL ADMINISTRATIVO PRINCIPAL (PERSISTENCIA 3FN)
# ==============================================================================
@app.route('/panel')
@login_required
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

    productos_stock_bajo = cursor.execute('''
        SELECT COUNT(*) FROM productos
        WHERE activo = 1 AND stock_actual <= stock_minimo
    ''').fetchone()[0]
    pedidos_pendientes = cursor.execute('''
        SELECT COUNT(*) FROM pedidos WHERE estado = 'PENDIENTE'
    ''').fetchone()[0]
    ventas_hoy = cursor.execute('''
        SELECT COALESCE(SUM(total), 0)
        FROM facturas
        WHERE DATE(fecha_emision) = CURRENT_DATE
    ''').fetchone()[0]
    solicitudes_pendientes = cursor.execute('''
        SELECT COUNT(*) FROM usuarios
        WHERE estado = 'PENDIENTE' AND activo = 1
    ''').fetchone()[0]

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
        "total_facturas": total_facturas,
        "productos_stock_bajo": productos_stock_bajo,
        "pedidos_pendientes": pedidos_pendientes,
        "ventas_hoy": ventas_hoy,
        "solicitudes_pendientes": solicitudes_pendientes
    }

    return render_template(
        'panel.html', metricas=metricas, ultimos_productos=ultimos_productos,
        database_tipo='PostgreSQL' if USE_POSTGRES else 'SQLite (desarrollo)'
    )


# ==============================================================================
# 9. RUTA PÚBLICA PRINCIPAL (CATÁLOGO PARA CLIENTES)
# ==============================================================================
@app.route('/index.html')
def inicio_externo():
    """Sirve la portada raíz usada también por GitHub Pages."""
    return send_file(os.path.join(BASE_DIR, 'index.html'))


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
# 10. CONTROL DE INVENTARIO
# ==============================================================================
@app.route('/inventario', methods=['GET', 'POST'])
@login_required
def inventario():
    """Presenta existencias y movimientos; permite ajustes validados y auditables."""
    form = InventarioForm()
    conn = obtener_conexion()
    form.id_producto.choices = [
        (row['id_producto'], f"{row['codigo']} - {row['nombre']} (stock: {row['stock_actual']:g})")
        for row in conn.execute(
            'SELECT id_producto, codigo, nombre, stock_actual FROM productos '
            'WHERE activo = 1 ORDER BY nombre'
        ).fetchall()
    ]

    if form.validate_on_submit():
        try:
            _iniciar_transaccion(conn)
            query = 'SELECT id_producto, nombre, stock_actual FROM productos WHERE id_producto = ? AND activo = 1'
            if USE_POSTGRES:
                query += ' FOR UPDATE'
            producto = conn.execute(query, (form.id_producto.data,)).fetchone()
            if not producto:
                raise ValueError('El producto seleccionado ya no existe o está inactivo.')

            cantidad = Decimal(form.cantidad.data)
            stock_anterior = Decimal(str(producto['stock_actual']))
            es_entrada = form.tipo.data == 'entrada'
            stock_nuevo = stock_anterior + cantidad if es_entrada else stock_anterior - cantidad
            if stock_nuevo < 0:
                raise ValueError(
                    f'Stock insuficiente de "{producto["nombre"]}". Disponible: {stock_anterior:g}.'
                )
            tipo_movimiento = 'AJUSTE ENTRADA' if es_entrada else 'AJUSTE SALIDA'
            movimiento = conn.execute(
                'SELECT id_tipo_movimiento FROM tipos_movimiento_inventario WHERE nombre = ?',
                (tipo_movimiento,)
            ).fetchone()
            if not movimiento:
                raise RuntimeError(f'Falta configurar el movimiento de inventario "{tipo_movimiento}".')
            conn.execute(
                'UPDATE productos SET stock_actual = ? WHERE id_producto = ?',
                (float(stock_nuevo), form.id_producto.data)
            )
            conn.execute(
                'INSERT INTO movimientos_inventario '
                '(id_producto, id_tipo_movimiento, cantidad, stock_anterior, stock_nuevo, referencia, observaciones) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    form.id_producto.data, movimiento['id_tipo_movimiento'], float(cantidad),
                    float(stock_anterior), float(stock_nuevo), 'AJUSTE MANUAL',
                    form.observaciones.data.strip()
                )
            )
            conn.commit()
            flash('Movimiento de inventario registrado correctamente.', 'success')
            return redirect(url_for('inventario'))
        except ValueError as error:
            conn.rollback()
            flash(str(error), 'danger')

    productos_stock = conn.execute('''
        SELECT p.id_producto, p.codigo, p.nombre, p.stock_actual, p.stock_minimo,
               u.abreviatura AS unidad, cp.nombre AS categoria
        FROM productos p
        JOIN unidades_medida u ON u.id_unidad = p.id_unidad
        JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
        WHERE p.activo = 1
        ORDER BY p.nombre
    ''').fetchall()
    movimientos = conn.execute('''
        SELECT m.fecha_movimiento, m.referencia, m.cantidad, m.stock_anterior, m.stock_nuevo,
               m.observaciones, p.codigo, p.nombre AS producto, tm.nombre AS tipo
        FROM movimientos_inventario m
        JOIN productos p ON p.id_producto = m.id_producto
        JOIN tipos_movimiento_inventario tm ON tm.id_tipo_movimiento = m.id_tipo_movimiento
        ORDER BY m.id_movimiento DESC
        LIMIT 100
    ''').fetchall()
    conn.close()
    return render_template(
        'inventario.html', form=form, productos=productos_stock, movimientos=movimientos
    )


# ==============================================================================
# 11. MÓDULO PRODUCTOS: PERSISTENCIA COMPLETA CRUD (3FN)
# ==============================================================================
@app.route('/productos')
@login_required
def productos():
    """
    Consulta y lista todos los productos mediante JOIN
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
@admin_required
def nuevo_producto():
    """
    Inserta un nuevo producto en la base de datos configurada utilizando
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
        try:
            imagen = guardar_imagen_producto(form.imagen.data)
        except ValueError as error:
            form.imagen.errors.append(str(error))
            return render_template("formulario_producto.html", form=form, modo="registro", producto=None)

        if not imagen:
            imagen = form.imagen_existente.data or 'img/CHEESCAKE.png'

        codigo = form.codigo.data.strip().upper()
        nombre = form.nombre.data.strip()
        id_categoria = int(form.id_categoria_producto.data)
        id_unidad = int(form.id_unidad.data)
        descripcion = form.descripcion.data.strip()
        precio_venta = float(form.precio_venta.data)
        costo = float(form.costo_referencial.data) if form.costo_referencial.data else 0.0
        stock_actual = float(form.stock_actual.data)
        stock_minimo = float(form.stock_minimo.data)
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
            if stock_actual > 0:
                producto_id = conn.execute(
                    'SELECT id_producto FROM productos WHERE codigo = ?', (codigo,)
                ).fetchone()['id_producto']
                tipo_entrada = conn.execute(
                    "SELECT id_tipo_movimiento FROM tipos_movimiento_inventario WHERE nombre = 'AJUSTE ENTRADA'"
                ).fetchone()
                conn.execute(
                    'INSERT INTO movimientos_inventario '
                    '(id_producto, id_tipo_movimiento, cantidad, stock_anterior, stock_nuevo, referencia, observaciones) '
                    'VALUES (?, ?, ?, 0, ?, ?, ?)',
                    (producto_id, tipo_entrada['id_tipo_movimiento'], stock_actual, stock_actual, codigo, 'Stock inicial del producto')
                )
            conn.commit()
            flash(f'¡Producto "{nombre}" ({codigo}) guardado correctamente!', 'success')
            return redirect(url_for('productos'))
        except INTEGRITY_ERRORS:
            flash(f'Error de integridad: El código "{codigo}" ya está registrado.', 'danger')
        finally:
            conn.close()

    return render_template("formulario_producto.html", form=form, modo="registro", producto=None)


@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_producto(id):
    """
    Recupera y actualiza los datos de un producto existente (3FN).
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
        form.imagen.data = None
        form.imagen_existente.data = producto['imagen']

    # Procesar actualización al superar validaciones
    if form.validate_on_submit():
        imagen = producto['imagen']
        if form.imagen.data and form.imagen.data.filename:
            try:
                imagen = guardar_imagen_producto(form.imagen.data)
            except ValueError as error:
                form.imagen.errors.append(str(error))
                return render_template("formulario_producto.html", form=form, modo="edicion", producto=producto)
        elif form.imagen_existente.data:
            imagen = form.imagen_existente.data

        conn = obtener_conexion()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE productos
                SET codigo = ?, nombre = ?, id_categoria_producto = ?, id_unidad = ?,
                    descripcion = ?, precio_venta = ?, costo_referencial = ?,
                    stock_minimo = ?, imagen = ?
                WHERE id_producto = ?
            ''', (
                form.codigo.data.strip().upper(),
                form.nombre.data.strip(),
                int(form.id_categoria_producto.data),
                int(form.id_unidad.data),
                form.descripcion.data.strip(),
                float(form.precio_venta.data),
                float(form.costo_referencial.data) if form.costo_referencial.data else 0.0,
                float(form.stock_minimo.data),
                imagen,
                id
            ))
            conn.commit()
            flash(f'¡Producto "{form.nombre.data.strip()}" actualizado con éxito!', 'info')
            return redirect(url_for('productos'))
        except INTEGRITY_ERRORS:
            conn.rollback()
            flash('El código del producto ya está registrado.', 'danger')
        finally:
            conn.close()

    return render_template("formulario_producto.html", form=form, modo="edicion", producto=producto)


@app.route('/productos/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_producto(id):
    """
    Elimina físicamente un producto mediante petición POST protegida.
    """
    conn = obtener_conexion()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM productos WHERE id_producto = ?", (id,))
        conn.commit()
        flash('El producto ha sido eliminado del catálogo.', 'warning')
    except INTEGRITY_ERRORS:
        conn.rollback()
        flash('No se puede eliminar: el producto tiene movimientos o facturas relacionadas. Desactívelo o conserve su historial.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('productos'))


# ==============================================================================
# 11. MÓDULO CLIENTES: GESTIÓN CON MODELO NORMALIZADO (3FN)
# ==============================================================================
@app.route('/clientes')
@login_required
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
@admin_required
def nuevo_cliente():
    """Registra un nuevo cliente mediante ClienteForm."""
    form = ClienteForm()
    sincronizar_opciones_cliente(form)

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        try:
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
            flash(f'¡Cliente "{form.nombre.data.strip()}" registrado exitosamente!', 'success')
            return redirect(url_for('clientes'))
        except INTEGRITY_ERRORS:
            conn.rollback()
            flash('La identificación del cliente ya está registrada.', 'danger')
        finally:
            conn.close()

    return render_template("formulario_cliente.html", form=form, modo="registro", cliente=None)


@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_cliente(id):
    """Actualiza la información de un cliente."""
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
        try:
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
            flash(f'¡Cliente "{form.nombre.data.strip()}" actualizado correctamente!', 'info')
            return redirect(url_for('clientes'))
        except INTEGRITY_ERRORS:
            conn.rollback()
            flash('La identificación del cliente ya está registrada.', 'danger')
        finally:
            conn.close()

    return render_template("formulario_cliente.html", form=form, modo="edicion", cliente=cliente)


@app.route('/clientes/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_cliente(id):
    conn = obtener_conexion()
    try:
        conn.execute('DELETE FROM clientes WHERE id_cliente = ?', (id,))
        conn.commit()
        flash('Cliente eliminado correctamente.', 'warning')
    except INTEGRITY_ERRORS:
        conn.rollback()
        flash('No se puede eliminar el cliente porque tiene facturas asociadas.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('clientes'))


# ==============================================================================
# 12. MÓDULO PROVEEDORES: GESTIÓN CON MODELO NORMALIZADO (3FN)
# ==============================================================================
@app.route('/provedores')
@app.route('/proveedores')
@admin_required
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
@admin_required
def nuevo_proveedor():
    """Inserta un nuevo proveedor comercial."""
    form = ProveedorForm()
    sincronizar_opciones_proveedor(form)

    if form.validate_on_submit():
        conn = obtener_conexion()
        cursor = conn.cursor()
        try:
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
            flash(f'¡Proveedor "{form.razon_social.data.strip()}" registrado exitosamente!', 'success')
            return redirect(url_for('proveedores'))
        except INTEGRITY_ERRORS:
            conn.rollback()
            flash('El RUC del proveedor ya está registrado.', 'danger')
        finally:
            conn.close()

    return render_template("formulario_proveedor.html", form=form, modo="registro", proveedor=None)


@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_proveedor(id):
    """Actualiza la información de un proveedor comercial."""
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
        try:
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
            flash(f'¡Proveedor "{form.razon_social.data.strip()}" actualizado correctamente!', 'info')
            return redirect(url_for('proveedores'))
        except INTEGRITY_ERRORS:
            conn.rollback()
            flash('El RUC del proveedor ya está registrado.', 'danger')
        finally:
            conn.close()

    # Adaptador para compatibilidad visual con la plantilla
    prov_dict = dict(proveedor)
    prov_dict['empresa'] = proveedor['razon_social']
    return render_template("formulario_proveedor.html", form=form, modo="edicion", proveedor=prov_dict)


@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_proveedor(id):
    conn = obtener_conexion()
    try:
        conn.execute('DELETE FROM proveedores WHERE id_proveedor = ?', (id,))
        conn.commit()
        flash('Proveedor eliminado correctamente.', 'warning')
    except INTEGRITY_ERRORS:
        conn.rollback()
        flash('No se puede eliminar el proveedor porque tiene compras relacionadas.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('proveedores'))


# ==============================================================================
# 13. MÓDULO DE PEDIDOS, ABONOS, COMPROBANTES Y FACTURACIÓN
# ==============================================================================
def _opciones_metodos_pago(conn):
    return [
        (int(row['id_metodo_pago']), row['nombre'])
        for row in conn.execute(
            'SELECT id_metodo_pago, nombre FROM metodos_pago WHERE activo = 1 ORDER BY id_metodo_pago'
        ).fetchall()
    ]


def _numero_comprobante_unico(conn, entidad, prefijo, identificador):
    columnas = {
        'pedidos': 'numero',
        'pagos_pedido': 'numero_comprobante',
        'facturas': 'numero',
    }
    columna = columnas.get(entidad)
    if not columna:
        raise ValueError('Tipo de comprobante no reconocido.')
    base = f'{prefijo}-{int(identificador):06d}'
    candidato = base
    sufijo = 1
    while conn.execute(
        f'SELECT 1 FROM {entidad} WHERE {columna} = ?', (candidato,)
    ).fetchone():
        candidato = f'{base}-{sufijo}'
        sufijo += 1
    return candidato


def _registrar_pago_y_facturar(
    conn, id_pedido, monto, id_metodo_pago, observaciones, clave_idempotencia
):
    consulta = 'SELECT * FROM pedidos WHERE id_pedido = ?'
    if USE_POSTGRES:
        consulta += ' FOR UPDATE'
    pedido = conn.execute(consulta, (id_pedido,)).fetchone()
    if not pedido:
        raise ValueError('El pedido no existe.')
    pago_anterior = conn.execute(
        'SELECT id_pedido, numero_comprobante FROM pagos_pedido WHERE clave_idempotencia = ?',
        (clave_idempotencia,)
    ).fetchone()
    if pago_anterior:
        if int(pago_anterior['id_pedido']) != id_pedido:
            raise ValueError('La clave de esta operación ya fue utilizada en otro pedido.')
        factura_anterior = conn.execute(
            'SELECT numero FROM facturas WHERE id_pedido = ?', (id_pedido,)
        ).fetchone()
        return pago_anterior['numero_comprobante'], (
            factura_anterior['numero'] if factura_anterior else None
        )
    if pedido['estado'] != 'PENDIENTE':
        raise ValueError('El pedido no existe o ya fue pagado.')

    total = Decimal(str(pedido['total'])).quantize(Decimal('0.01'))
    pagado = Decimal(str(pedido['monto_pagado'])).quantize(Decimal('0.01'))
    monto = monto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    saldo = total - pagado
    if monto <= 0 or monto > saldo:
        raise ValueError(f'El abono debe ser mayor que cero y no superar el saldo de ${saldo:.2f}.')

    token = secrets.token_hex(16)
    conn.execute('''
        INSERT INTO pagos_pedido
            (id_pedido, numero_comprobante, clave_idempotencia,
             monto, id_metodo_pago, observaciones)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        id_pedido, f'REC-PROCESO-{token}', clave_idempotencia,
        _valor_numerico_db(monto), id_metodo_pago,
        observaciones.strip() if observaciones else ''
    ))
    pago = conn.execute(
        'SELECT id_pago FROM pagos_pedido WHERE numero_comprobante = ?',
        (f'REC-PROCESO-{token}',)
    ).fetchone()
    fecha = datetime.now(timezone.utc)
    numero_recibo = _numero_comprobante_unico(
        conn, 'pagos_pedido', f'REC-{fecha.year}', pago['id_pago']
    )
    conn.execute(
        'UPDATE pagos_pedido SET numero_comprobante = ?, fecha_pago = ? WHERE id_pago = ?',
        (numero_recibo, fecha.isoformat(timespec='seconds'), pago['id_pago'])
    )

    nuevo_pagado = pagado + monto
    completado = nuevo_pagado == total
    conn.execute(
        'UPDATE pedidos SET monto_pagado = ?, estado = ? WHERE id_pedido = ?',
        (float(nuevo_pagado), 'PAGADO' if completado else 'PENDIENTE', id_pedido)
    )
    if not completado:
        return numero_recibo, None

    metodo_unico = conn.execute(
        'SELECT COUNT(DISTINCT id_metodo_pago) AS cantidad, MIN(id_metodo_pago) AS id_metodo '
        'FROM pagos_pedido WHERE id_pedido = ?',
        (id_pedido,)
    ).fetchone()
    if int(metodo_unico['cantidad']) > 1:
        id_metodo_factura = conn.execute(
            "SELECT id_metodo_pago FROM metodos_pago WHERE nombre = 'VARIOS'"
        ).fetchone()['id_metodo_pago']
    else:
        id_metodo_factura = metodo_unico['id_metodo']
    id_estado = conn.execute(
        "SELECT id_estado_factura FROM estados_factura WHERE nombre = 'EMITIDA'"
    ).fetchone()
    if not id_estado:
        raise RuntimeError('Falta configurar el estado de factura EMITIDA.')

    numero_temporal = f'FAC-PROCESO-{secrets.token_hex(16)}'
    conn.execute('''
        INSERT INTO facturas (
            numero, id_cliente, id_metodo_pago, id_estado_factura, subtotal,
            iva, total, observaciones, id_pedido
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        numero_temporal, pedido['id_cliente'], id_metodo_factura,
        id_estado['id_estado_factura'], pedido['subtotal'], pedido['iva'],
        pedido['total'], pedido['observaciones'], id_pedido
    ))
    factura = conn.execute(
        'SELECT id_factura FROM facturas WHERE numero = ?', (numero_temporal,)
    ).fetchone()
    numero_factura = _numero_comprobante_unico(
        conn, 'facturas', f'FAC-{fecha.year}', factura['id_factura']
    )
    conn.execute(
        'UPDATE facturas SET numero = ?, fecha_emision = ? WHERE id_factura = ?',
        (numero_factura, fecha.date().isoformat(), factura['id_factura'])
    )
    conn.execute('''
        INSERT INTO detalle_factura
            (id_factura, id_producto, codigo_producto, nombre_producto,
             cantidad, precio_unitario, descuento, subtotal)
        SELECT ?, id_producto, codigo_producto, nombre_producto,
               cantidad, precio_unitario, descuento, subtotal
        FROM detalle_pedido WHERE id_pedido = ?
    ''', (factura['id_factura'], id_pedido))
    return numero_recibo, numero_factura


def _datos_productos_pedido(conn):
    return conn.execute('''
        SELECT id_producto, codigo, nombre, precio_venta, stock_actual
        FROM productos WHERE activo = 1 AND stock_actual > 0 ORDER BY nombre
    ''').fetchall()


@app.route('/facturacion')
@login_required
def facturacion():
    conn = obtener_conexion()
    pedidos = conn.execute('''
        SELECT p.*, c.nombre AS cliente, c.cedula_ruc,
               COALESCE(p.total - p.monto_pagado, p.total) AS saldo
        FROM pedidos p JOIN clientes c ON c.id_cliente = p.id_cliente
        ORDER BY p.id_pedido DESC
    ''').fetchall()
    pagos = conn.execute('''
        SELECT pg.*, mp.nombre AS metodo_pago
        FROM pagos_pedido pg JOIN metodos_pago mp ON mp.id_metodo_pago = pg.id_metodo_pago
        ORDER BY pg.id_pago
    ''').fetchall()
    facturas = conn.execute('''
        SELECT f.*, c.nombre AS cliente, c.cedula_ruc, mp.nombre AS metodo_pago
        FROM facturas f
        JOIN clientes c ON c.id_cliente = f.id_cliente
        JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
        ORDER BY f.id_factura DESC
    ''').fetchall()
    lineas_pedido = conn.execute('''
        SELECT dp.id_pedido,
               COALESCE(dp.codigo_producto, p.codigo) AS codigo_producto,
               COALESCE(dp.nombre_producto, p.nombre) AS producto,
               dp.cantidad, dp.precio_unitario, dp.subtotal
        FROM detalle_pedido dp JOIN productos p ON p.id_producto = dp.id_producto
        ORDER BY dp.id_pedido, p.nombre
    ''').fetchall()
    lineas_factura = conn.execute('''
        SELECT df.id_factura,
               COALESCE(df.codigo_producto, p.codigo) AS codigo_producto,
               COALESCE(df.nombre_producto, p.nombre) AS producto,
               df.cantidad, df.precio_unitario, df.subtotal
        FROM detalle_factura df JOIN productos p ON p.id_producto = df.id_producto
        ORDER BY df.id_factura, p.nombre
    ''').fetchall()
    metodos = _opciones_metodos_pago(conn)
    conn.close()

    pagos_por_pedido = {}
    for pago in pagos:
        pagos_por_pedido.setdefault(pago['id_pedido'], []).append(pago)
    detalles_pedido = {}
    for linea in lineas_pedido:
        detalles_pedido.setdefault(linea['id_pedido'], []).append(linea)
    detalles_factura = {}
    for linea in lineas_factura:
        detalles_factura.setdefault(linea['id_factura'], []).append(linea)
    formularios_abono = {}
    for pedido in pedidos:
        if pedido['estado'] == 'PENDIENTE':
            form = AbonoForm(prefix=f'abono-{pedido["id_pedido"]}')
            form.id_metodo_pago.choices = metodos
            form.clave_idempotencia.data = secrets.token_urlsafe(32)
            formularios_abono[pedido['id_pedido']] = form

    return render_template(
        'facturacion.html', pedidos=pedidos, facturas=facturas,
        pagos_por_pedido=pagos_por_pedido, detalles_pedido=detalles_pedido,
        detalles_factura=detalles_factura, formularios_abono=formularios_abono
    )


@app.route('/clientes/consultar/<cedula_ruc>')
@login_required
def consultar_cliente(cedula_ruc):
    if not cedula_ruc.isdigit() or not 10 <= len(cedula_ruc) <= 13:
        return jsonify({'error': 'Ingrese una identificación de 10 a 13 dígitos.'}), 400
    conn = obtener_conexion()
    cliente = conn.execute('''
        SELECT nombre, correo, telefono, direccion, activo
        FROM clientes WHERE cedula_ruc = ?
    ''', (cedula_ruc,)).fetchone()
    conn.close()
    if not cliente:
        return jsonify({'exists': False})
    return jsonify({'exists': True, **dict(cliente)})


@app.route('/facturacion/nueva', methods=['GET', 'POST'])
@login_required
def nueva_factura():
    form = FacturacionForm()
    catalog_conn = obtener_conexion()
    form.id_metodo_pago.choices = [(0, 'Seleccione método')] + _opciones_metodos_pago(catalog_conn)
    form.id_tipo_cliente.choices = [(0, 'No aplica para cliente registrado')] + [
        (int(row['id_tipo_cliente']), row['nombre'])
        for row in catalog_conn.execute(
            'SELECT id_tipo_cliente, nombre FROM tipos_cliente ORDER BY id_tipo_cliente'
        ).fetchall()
    ]
    productos_stock = _datos_productos_pedido(catalog_conn)
    catalog_conn.close()
    if request.method == 'GET':
        form.clave_idempotencia.data = secrets.token_urlsafe(32)
        return render_template(
            'formulario_facturacion.html', form=form,
            productos_stock=productos_stock
        )

    conn = None
    try:
        lineas = _parsear_lineas_pedido()
        if not form.validate_on_submit():
            raise ValueError('Revise los campos del pedido e inténtelo de nuevo.')
        conn = obtener_conexion()
        _iniciar_transaccion(conn)
        clave_idempotencia = form.clave_idempotencia.data
        pedido_anterior = conn.execute(
            'SELECT numero FROM pedidos WHERE clave_idempotencia = ?',
            (clave_idempotencia,)
        ).fetchone()
        if pedido_anterior:
            conn.commit()
            conn.close()
            conn = None
            flash(f'El pedido {pedido_anterior["numero"]} ya se había registrado.', 'info')
            return redirect(url_for('facturacion'))
        cedula = form.cedula_ruc.data.strip()
        cliente = conn.execute(
            'SELECT id_cliente, activo FROM clientes WHERE cedula_ruc = ?',
            (cedula,)
        ).fetchone()
        if cliente:
            if not cliente['activo']:
                raise ValueError('El cliente está inactivo y no puede realizar pedidos.')
            id_cliente = cliente['id_cliente']
        else:
            nombre = (form.nombre_cliente.data or '').strip()
            if not nombre:
                raise ValueError('La identificación no está registrada. Ingrese el nombre para registrar al cliente.')
            tipo_seleccionado = int(form.id_tipo_cliente.data or 0)
            tipo = conn.execute(
                'SELECT id_tipo_cliente FROM tipos_cliente WHERE id_tipo_cliente = ?',
                (tipo_seleccionado,)
            ).fetchone()
            if not tipo:
                raise ValueError('Seleccione un tipo de cliente válido.')
            conn.execute('''
                INSERT INTO clientes (id_tipo_cliente, nombre, cedula_ruc, correo, telefono, direccion)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                tipo['id_tipo_cliente'], nombre, cedula,
                (form.correo.data or '').strip().lower() or None,
                (form.telefono.data or '').strip() or None,
                (form.direccion.data or '').strip() or None
            ))
            id_cliente = conn.execute(
                'SELECT id_cliente FROM clientes WHERE cedula_ruc = ?', (cedula,)
            ).fetchone()['id_cliente']

        token = secrets.token_hex(16)
        numero_temporal = f'PED-PROCESO-{token}'
        conn.execute('''
            INSERT INTO pedidos (
                numero, clave_idempotencia, id_cliente,
                subtotal, iva, total, observaciones
            ) VALUES (?, ?, ?, 0, 0, 0.01, ?)
        ''', (
            numero_temporal, clave_idempotencia, id_cliente,
            (form.observaciones.data or '').strip() or None
        ))
        id_pedido = conn.execute(
            'SELECT id_pedido FROM pedidos WHERE numero = ?', (numero_temporal,)
        ).fetchone()['id_pedido']
        fecha = datetime.now(timezone.utc)
        numero_pedido = _numero_comprobante_unico(
            conn, 'pedidos', f'PED-{fecha.year}', id_pedido
        )
        conn.execute(
            'UPDATE pedidos SET numero = ? WHERE id_pedido = ?',
            (numero_pedido, id_pedido)
        )
        subtotal, iva, total = _reservar_stock_pedido(conn, id_pedido, numero_pedido, lineas)
        if total <= 0:
            raise ValueError('El pedido debe tener un total mayor que cero.')
        conn.execute(
            'UPDATE pedidos SET subtotal = ?, iva = ?, total = ? WHERE id_pedido = ?',
            tuple(_valor_numerico_db(value) for value in (subtotal, iva, total)) + (id_pedido,)
        )

        abono_inicial = _validar_decimal_entrada(
            request.form.get(form.monto_inicial.name, form.monto_inicial.data or '0'),
            2, 'el abono inicial'
        )
        if abono_inicial > 0:
            metodo = form.id_metodo_pago.data
            metodos_validos = {choice[0] for choice in form.id_metodo_pago.choices if choice[0]}
            if metodo not in metodos_validos:
                raise ValueError('Seleccione un método válido para el abono inicial.')
            recibo, factura = _registrar_pago_y_facturar(
                conn, id_pedido, abono_inicial, metodo, '',
                f'{clave_idempotencia}:inicial'
            )
        else:
            recibo = factura = None
        conn.commit()
        conn.close()
        conn = None
        mensaje = f'Pedido {numero_pedido} creado.'
        if recibo:
            mensaje += f' Comprobante {recibo} emitido.'
        if factura:
            mensaje += f' Factura {factura} emitida por pago completo.'
        flash(mensaje, 'success')
        return redirect(url_for('facturacion'))
    except ValueError as exception:
        if conn is not None:
            conn.rollback()
        error = str(exception)
    except INTEGRITY_ERRORS:
        if conn is not None:
            conn.rollback()
        error = 'No se pudo registrar el pedido. Revise la identificación del cliente y vuelva a intentarlo.'
    finally:
        if conn is not None:
            conn.close()

    flash(error, 'danger')
    return render_template(
        'formulario_facturacion.html', form=form, productos_stock=productos_stock
    )


@app.route('/pedidos/<int:id>/abonos', methods=['POST'])
@login_required
def registrar_abono(id):
    form = AbonoForm(prefix=f'abono-{id}')
    conn = obtener_conexion()
    form.id_metodo_pago.choices = _opciones_metodos_pago(conn)
    try:
        if not form.validate_on_submit():
            raise ValueError('Ingrese un monto y método de pago válidos.')
        monto_abono = _validar_decimal_entrada(
            request.form.get(form.monto.name, ''), 2, 'el abono'
        )
        numero_recibo, numero_factura = _registrar_pago_y_facturar(
            conn, id, monto_abono, form.id_metodo_pago.data,
            form.observaciones.data or '', form.clave_idempotencia.data
        )
        conn.commit()
        mensaje = f'Abono registrado. Comprobante {numero_recibo}.'
        if numero_factura:
            mensaje += f' Pedido cancelado; factura {numero_factura} emitida.'
        flash(mensaje, 'success')
    except ValueError as error:
        conn.rollback()
        flash(str(error), 'danger')
    except INTEGRITY_ERRORS:
        conn.rollback()
        flash('No se pudo guardar el abono por un conflicto de datos. Verifique el pedido e intente otra vez.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('facturacion'))


@app.route('/pagos/<int:id>/comprobante')
@login_required
def comprobante_pago(id):
    conn = obtener_conexion()
    pago = conn.execute('''
        SELECT pg.*, p.numero AS numero_pedido, p.total, p.monto_pagado,
               c.nombre AS cliente, c.cedula_ruc, mp.nombre AS metodo_pago
        FROM pagos_pedido pg
        JOIN pedidos p ON p.id_pedido = pg.id_pedido
        JOIN clientes c ON c.id_cliente = p.id_cliente
        JOIN metodos_pago mp ON mp.id_metodo_pago = pg.id_metodo_pago
        WHERE pg.id_pago = ?
    ''', (id,)).fetchone()
    conn.close()
    if not pago:
        flash('El comprobante solicitado no existe.', 'warning')
        return redirect(url_for('facturacion'))
    return render_template('comprobante_pago.html', pago=pago)


@app.route('/facturacion/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_factura(id):
    del id
    flash('Las facturas emitidas son inmutables. Los pagos se registran desde el pedido.', 'warning')
    return redirect(url_for('facturacion'))


@app.route('/facturacion/eliminar/<int:id>', methods=['POST'])
@admin_required
def eliminar_factura(id):
    del id
    flash('Las facturas emitidas no se eliminan; conserve su historial contable.', 'warning')
    return redirect(url_for('facturacion'))


# ==============================================================================
# 14. EJECUCIÓN DEL SERVIDOR LOCAL DE DESARROLLO
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
