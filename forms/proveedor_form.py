"""
================================================================================
PROYECTO: Dulce Delicia - Sistema de Gestión de Pastelería Artesanal
ARCHIVO: forms/proveedor_form.py
ASIGNATURA: Desarrollo de Aplicaciones Web
UNIVERSIDAD: Universidad Estatal Amazónica (UEA)
ESTUDIANTE: Desarrollo Web 2026
SEMANA: 11 y 12 - Proyecto Integrador U3 (12/16)
TEMA: Validación de Proveedores con Flask-WTF y Normalización en 3FN
================================================================================
DESCRIPCIÓN DEL ARCHIVO:
En este archivo implementamos la clase 'ProveedorForm' para la captura y
actualización de los datos de proveedores de materias primas (harinas, lácteos,
chocolates, frutas e insumos de panadería).

Estructura Normalizada (3FN):
  - Vinculación mediante clave foránea (id_categoria_proveedor) con la tabla
    'categorias_proveedor' (Materia Prima, Empaques, Bebidas, Otros).
  - Vinculación mediante clave foránea (id_estado_proveedor) con la tabla
    'estados_proveedor' (Activo, Inactivo).
  - Almacena Razón Social, RUC tributario único, Representante comercial,
    contacto telefónico, correo institucional y dirección física de bodega.
================================================================================
"""

# ==============================================================================
# 1. IMPORTACIONES DE FLASK-WTF Y WTFORMS
# ==============================================================================
from flask_wtf import FlaskForm
from wtforms import (
    StringField,       # Campo de texto para razón social, ruc, contacto y dirección
    EmailField,        # Campo especializado para correo electrónico de compras
    SelectField,       # Lista desplegable para catálogos foráneos (categoría y estado)
    SubmitField        # Botón para emitir la petición POST
)
from wtforms.validators import (
    DataRequired,      # Impide campos vacíos
    Length,            # Control de longitud máxima y mínima
    Email,             # Validación de estructura de email
    Regexp             # Expresión regular para dígitos numéricos
)


# ==============================================================================
# 2. DEFINICIÓN DE LA CLASE DEL FORMULARIO DE PROVEEDORES (3FN)
# ==============================================================================
class ProveedorForm(FlaskForm):
    """
    Formulario web para el registro y modificación de proveedores comerciales.
    Reutilizado en '/proveedores/nuevo' y '/proveedores/editar/<id>'.
    """

    # --------------------------------------------------------------------------
    # Campo 1: Razón Social de la empresa proveedora
    # --------------------------------------------------------------------------
    razon_social = StringField(
        'Razón Social / Nombre Comercial',
        validators=[
            DataRequired(message='La razón social de la empresa es obligatoria.'),
            Length(min=3, max=150, message='La razón social debe tener entre 3 y 150 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ej. Lácteos Andinos Cía. Ltda.',
            'class': 'form-control',
            'autofocus': True
        }
    )

    # --------------------------------------------------------------------------
    # Campo 2: RUC Tributario ecuatoriano (10 a 13 dígitos numéricos)
    # --------------------------------------------------------------------------
    ruc = StringField(
        'RUC / Identificación Fiscal',
        validators=[
            DataRequired(message='El RUC del proveedor es obligatorio.'),
            Length(min=10, max=13, message='El RUC debe tener entre 10 y 13 dígitos.'),
            Regexp(r'^\d{10,13}$', message='El RUC solo debe contener dígitos numéricos.')
        ],
        render_kw={
            'placeholder': 'Ej. 1791234567001',
            'maxlength': '13',
            'class': 'form-control font-monospace'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 3: Persona de contacto / Asesor comercial
    # --------------------------------------------------------------------------
    contacto = StringField(
        'Persona de Contacto / Representante',
        validators=[
            DataRequired(message='El nombre de la persona de contacto es obligatorio.'),
            Length(min=3, max=120, message='El contacto debe tener entre 3 y 120 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ej. Ing. María León Valdivieso',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 4: Correo electrónico de ventas o pedidos
    # --------------------------------------------------------------------------
    correo = EmailField(
        'Correo Institucional / Pedidos',
        validators=[
            DataRequired(message='El correo electrónico es obligatorio.'),
            Email(message='Ingrese una dirección de correo válida (ej. ventas@empresa.com).'),
            Length(max=120, message='El correo no debe superar los 120 caracteres.')
        ],
        render_kw={
            'placeholder': 'ventas@lacteosandinos.com',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 5: Teléfono o celular para recepción de pedidos
    # --------------------------------------------------------------------------
    telefono = StringField(
        'Teléfono de Pedidos / Celular',
        validators=[
            DataRequired(message='El teléfono de contacto es obligatorio.'),
            Length(min=9, max=20, message='El teléfono debe tener entre 9 y 20 caracteres.'),
            Regexp(r'^\d{9,20}$', message='El teléfono debe contener solo números.')
        ],
        render_kw={
            'placeholder': 'Ej. 0224588990 / 0987654321',
            'maxlength': '20',
            'class': 'form-control font-monospace'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 6: Categoría de insumos (Catálogo 3FN: 'categorias_proveedor')
    # --------------------------------------------------------------------------
    id_categoria_proveedor = SelectField(
        'Categoría de Insumos (Catálogo 3FN)',
        coerce=int,
        choices=[
            (1, '🌾 MATERIA PRIMA (Harina, azúcar, huevos, lácteos y cacao)'),
            (2, '📦 EMPAQUES (Cajas, fundas, vasos y empaques)'),
            (3, '☕ BEBIDAS (Proveedores de café, té e infusiones)'),
            (4, '🔧 OTROS (Otros insumos y mantenimiento)')
        ],
        validators=[
            DataRequired(message='Debe seleccionar una categoría de insumos.')
        ],
        render_kw={
            'class': 'form-select'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 7: Estado del proveedor (Catálogo 3FN: 'estados_proveedor')
    # --------------------------------------------------------------------------
    id_estado_proveedor = SelectField(
        'Estado de Homologación (Catálogo 3FN)',
        coerce=int,
        choices=[
            (1, '✅ ACTIVO (Proveedor Habilitado y Confiable)'),
            (2, '⏸️ INACTIVO (Proveedor Temporalmente Suspendido)')
        ],
        default=1,
        validators=[
            DataRequired(message='Debe seleccionar el estado del proveedor.')
        ],
        render_kw={
            'class': 'form-select'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 8: Dirección física de la planta o bodega del proveedor
    # --------------------------------------------------------------------------
    direccion = StringField(
        'Dirección de Planta / Bodega',
        validators=[
            DataRequired(message='La dirección del proveedor es obligatoria.'),
            Length(min=4, max=200, message='La dirección debe tener entre 4 y 200 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ej. Parque Industrial Machachi, Pichincha',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 9: Botón de confirmación y guardado
    # --------------------------------------------------------------------------
    submit = SubmitField(
        'Guardar Proveedor en Base de Datos',
        render_kw={
            'class': 'btn btn-caramelo px-4 py-2 text-white shadow-sm'
        }
    )
