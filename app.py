"""Rutas Flask del sistema administrativo y sitio público de Dulce Delicia."""

# ===============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS Y MÓDULOS DE PYTHON Y FLASK
# ===============================================================================
import sqlite3                        # Excepción de integridad usada por las rutas
from datetime import date, datetime  # Manipulación de fechas para comprobantes
from functools import wraps          # Utilidad para construir decoradores en Python
from flask import (
    Flask,                           # Clase constructora de la app web
    render_template,                 # Procesamiento de plantillas HTML con Jinja2
    request,                         # Acceso a los datos de peticiones HTTP
    redirect,                        # Redireccionamiento entre vistas
    url_for,                         # Generador de rutas seguras por nombre de función
    flash,                           # Envío de notificaciones temporales al usuario
    session,                         # Almacén de sesiones cifradas del navegador
)

# Importamos las clases de formularios desarrolladas en la carpeta forms/
from forms import (
    ProductoForm,                    # Formulario para postres (3FN)
    ClienteForm,                     # Formulario para clientes (3FN)
    ProveedorForm,                   # Formulario para proveedores (3FN)
    FacturacionForm                  # Formulario para facturación (3FN)
)


# ==============================================================================
# 2. INICIALIZACIÓN Y CONFIGURACIÓN DE FLASK
# ==============================================================================
app = Flask(__name__)

# Clave secreta para la firma criptográfica de sesiones y protección CSRF
app.config['SECRET_KEY'] = 'dulce-delicia-pasteleria-semana12-sqlite-uea-2026'

from database import (
    obtener_conexion,
    guardar_imagen_producto,
    sincronizar_opciones_producto,
    sincronizar_opciones_cliente,
    sincronizar_opciones_proveedor,
    sincronizar_opciones_factura
)


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
    Abre directamente el sistema administrativo desde el botón de acceso.

    El proyecto conserva la plantilla de login como referencia académica, pero
    el flujo solicitado no requiere una pantalla intermedia de credenciales.
    """
    if session.get('usuario'):
        return redirect(url_for('panel'))

    session['usuario'] = 'Administrador'
    session['rol'] = 'admin'
    flash('¡Bienvenido al sistema administrativo!', 'success')
    return redirect(url_for('panel'))


@app.route('/logout')
def logout():
    """Cierra la sesión administrativa y vuelve a la portada pública."""
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
@app.route('/index.html')
def inicio_externo():
    """Mantiene la URL de GitHub Pages dentro de la portada dinámica."""
    return redirect(url_for('inicio'))


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
            imagen,
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
