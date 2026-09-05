"""
================================================================================
PROYECTO: Dulce Delicia - Sistema de Gestión de Pastelería Artesanal
ARCHIVO: forms/producto_form.py
ASIGNATURA: Desarrollo de Aplicaciones Web
UNIVERSIDAD: Universidad Estatal Amazónica (UEA)
DOCENTE / EVALUADOR: Carrera de Tecnologías de la Información
ESTUDIANTE: Desarrollo Web 2026
SEMANA: 11 y 12 - Proyecto Integrador U3 (12/16)
TEMA: Validación de Formularios con Flask-WTF y Modelo Normalizado (3FN)
================================================================================
DESCRIPCIÓN DEL ARCHIVO:
En este archivo definimos la clase de formulario 'ProductoForm' utilizando las
herramientas de Flask-WTF y WTForms. Este formulario representa la interfaz
de entrada para el módulo de inventario y catálogo de la pastelería.

A diferencia de modelos planos o no estructurados, este formulario implementa
la estructura correspondiente al modelo relacional normalizado en Tercera
Forma Normal (3FN), vinculándose con:
  1. Catálogo de Categorías (tabla 'categorias_producto')
  2. Catálogo de Unidades de Medida (tabla 'unidades_medida')
  3. Campos financieros y de control de stock (precio_venta, costo_referencial,
     stock_actual, stock_minimo, código único correlativo).

MEDIDAS DE SEGURIDAD Y VALIDACIÓN:
  - Token CSRF automático generado por FlaskForm para mitigar falsificación
    de peticiones en sitios cruzados.
  - DataRequired(): Impide el envío de campos obligatorios en blanco.
  - Length(): Limita el número de caracteres para prevenir ataques de desbordamiento.
  - NumberRange(): Asegura que precios y cantidades sean estrictamente no negativos.
  - Regexp(): Valida la nomenclatura estandarizada de los códigos de producto.
================================================================================
"""

# ==============================================================================
# 1. IMPORTACIONES DE LIBRERÍAS Y COMPONENTES DE FLASK-WTF Y WTFORMS
# ==============================================================================
from flask_wtf import FlaskForm  # Clase base para crear formularios seguros con CSRF
from wtforms import (
    StringField,       # Campo para cadenas de texto cortas (código, nombre)
    TextAreaField,     # Campo multilínea para la descripción detallada del postre
    DecimalField,      # Campo numérico de coma flotante para valores monetarios y stock
    IntegerField,      # Campo numérico entero para cantidades enteras
    SelectField,       # Lista desplegable para claves foráneas y selecciones
    SubmitField        # Botón de envío procesado por el servidor
)
from wtforms.validators import (
    DataRequired,      # Validador: El campo no puede quedar vacío
    Length,            # Validador: Rango mínimo y máximo de caracteres permitidos
    NumberRange,       # Validador: Rango numérico permitido (ej. precio >= 0)
    Regexp             # Validador: Expresión regular para verificar formatos específicos
)


# ==============================================================================
# 2. DEFINICIÓN DE LA CLASE DEL FORMULARIO DE PRODUCTOS (3FN)
# ==============================================================================
class ProductoForm(FlaskForm):
    """
    Formulario web para la creación y modificación de productos en Dulce Delicia.
    
    Este formulario se reutiliza tanto en la ruta de registro ('/productos/nuevo')
    como en la ruta de actualización ('/productos/editar/<id>').
    
    Cada atributo de clase corresponde directamente a una columna de la tabla
    'productos' del modelo relacional normalizado en 3FN.
    """

    # --------------------------------------------------------------------------
    # Campo 1: Código único del producto (Ej: TOR-001, POS-001, PAN-001)
    # --------------------------------------------------------------------------
    codigo = StringField(
        'Código del Producto',
        validators=[
            DataRequired(message='El código del producto es obligatorio.'),
            Length(min=3, max=20, message='El código debe tener entre 3 y 20 caracteres.'),
            Regexp(r'^[A-Z0-9\-]+$', message='El código solo permite letras mayúsculas, números y guiones (ej. TOR-001).')
        ],
        render_kw={
            'placeholder': 'Ej. TOR-001, POS-001',
            'class': 'form-control font-monospace fw-bold',
            'autofocus': True
        }
    )

    # --------------------------------------------------------------------------
    # Campo 2: Nombre comercial del postre o producto
    # --------------------------------------------------------------------------
    nombre = StringField(
        'Nombre del Postre / Especialidad',
        validators=[
            DataRequired(message='El nombre del producto es obligatorio.'),
            Length(min=3, max=120, message='El nombre debe contener entre 3 y 120 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ej. Torta de chocolate fino de aroma',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 3: Clave Foránea a la tabla 'categorias_producto' (Catálogo 3FN)
    # --------------------------------------------------------------------------
    id_categoria_producto = SelectField(
        'Categoría (Catálogo Normalizado)',
        coerce=int,
        choices=[
            (1, '🎂 TORTAS (Tortas y Pasteles de Celebración)'),
            (2, '🍰 POSTRES (Postres Individuales y Dulces Finos)'),
            (3, '🥐 PANADERIA (Panadería Artesanal y Hojaldres)'),
            (4, '☕ BEBIDAS (Bebidas Frías y Cafetería de Especialidad)'),
            (5, '📦 OTROS (Complementos y Empaques de Regalo)')
        ],
        validators=[
            DataRequired(message='Debe seleccionar una categoría del catálogo.')
        ],
        render_kw={
            'class': 'form-select'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 4: Clave Foránea a la tabla 'unidades_medida' (Catálogo 3FN)
    # --------------------------------------------------------------------------
    id_unidad = SelectField(
        'Unidad de Medida',
        coerce=int,
        choices=[
            (1, 'UND - Unidad / Pieza Entera'),
            (2, 'KG - Kilogramo'),
            (3, 'L - Litro'),
            (4, 'POR - Porción Individual')
        ],
        validators=[
            DataRequired(message='Debe seleccionar la unidad de medida.')
        ],
        render_kw={
            'class': 'form-select'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 5: Descripción detallada de ingredientes, textura y presentación
    # --------------------------------------------------------------------------
    descripcion = TextAreaField(
        'Descripción del Postre',
        validators=[
            DataRequired(message='La descripción del producto es obligatoria.'),
            Length(min=10, max=250, message='La descripción debe contener entre 10 y 250 caracteres.')
        ],
        render_kw={
            'rows': 3,
            'placeholder': 'Describe los ingredientes principales, el tipo de masa, cobertura y notas de sabor...',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 6: Precio de venta al público en dólares ($ USD)
    # --------------------------------------------------------------------------
    precio_venta = DecimalField(
        'Precio de Venta ($ USD)',
        places=2,
        validators=[
            DataRequired(message='El precio de venta es obligatorio.'),
            NumberRange(min=0.25, max=500.00, message='El precio de venta debe estar entre $0.25 y $500.00.')
        ],
        render_kw={
            'placeholder': '0.00',
            'step': '0.25',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 7: Costo referencial de producción / compra de materia prima
    # --------------------------------------------------------------------------
    costo_referencial = DecimalField(
        'Costo Referencial ($ USD)',
        places=2,
        default=0.00,
        validators=[
            NumberRange(min=0.00, max=500.00, message='El costo no puede ser negativo.')
        ],
        render_kw={
            'placeholder': '0.00',
            'step': '0.10',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 8: Stock actual disponible en vitrina o bodega
    # --------------------------------------------------------------------------
    stock_actual = DecimalField(
        'Stock Actual (Cantidad Disponible)',
        places=2,
        default=10.0,
        validators=[
            DataRequired(message='El stock actual es obligatorio.'),
            NumberRange(min=0.0, max=10000.0, message='El stock debe ser un valor positivo o cero.')
        ],
        render_kw={
            'placeholder': 'Ej. 10',
            'step': '1',
            'min': '0',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 9: Stock mínimo de seguridad para disparar alertas de reabastecimiento
    # --------------------------------------------------------------------------
    stock_minimo = DecimalField(
        'Stock Mínimo (Alerta de Reabastecimiento)',
        places=2,
        default=3.0,
        validators=[
            DataRequired(message='El stock mínimo es obligatorio.'),
            NumberRange(min=0.0, max=1000.0, message='El stock mínimo no puede ser negativo.')
        ],
        render_kw={
            'placeholder': 'Ej. 3',
            'step': '1',
            'min': '0',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 10: Fotografía representativa del postre para el catálogo
    # --------------------------------------------------------------------------
    imagen = SelectField(
        'Fotografía del Producto',
        choices=[
            ('img/CHEESCAKE.png', '🍰 Cheesecake Clásico New York (img/CHEESCAKE.png)'),
            ('img/TARTADEFRUTA.png', '🍓 Tarta de Frutas Tropicales (img/TARTADEFRUTA.png)'),
            ('img/MOUSSE.png', '🍫 Mousse de Chocolate Fino (img/MOUSSE.png)'),
            ('img/DULCEDELICIA.png', '🎂 Especialidad Dulce Delicia (img/DULCEDELICIA.png)')
        ],
        default='img/CHEESCAKE.png',
        validators=[
            DataRequired(message='Debe seleccionar una fotografía para el postre.')
        ],
        render_kw={
            'class': 'form-select',
            'id': 'select_imagen_producto'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 11: Botón de envío procesado por el servidor Flask
    # --------------------------------------------------------------------------
    submit = SubmitField(
        'Guardar Producto en Base de Datos',
        render_kw={
            'class': 'btn btn-caramelo px-4 py-2 text-white shadow-sm'
        }
    )
