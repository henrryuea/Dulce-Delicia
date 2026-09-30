"""Formulario WTForms para validar y registrar productos."""

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
    FileField,         # Archivo de imagen elegido desde el equipo
    SubmitField        # Botón de envío procesado por el servidor
)
from wtforms.validators import (
    DataRequired,      # Validador: El campo no puede quedar vacío
    InputRequired,     # Validador: Requiere que se envíe incluso cuando el valor es cero
    Length,            # Validador: Rango mínimo y máximo de caracteres permitidos
    NumberRange,       # Validador: Rango numérico permitido (ej. precio >= 0)
    Regexp,            # Validador: Expresión regular para verificar formatos específicos
    ValidationError
)


def decimal_finito(form, field):
    del form
    if field.data is not None and not field.data.is_finite():
        raise ValidationError('Ingrese un número válido y finito.')



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
            decimal_finito,
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
            decimal_finito,
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
            InputRequired(message='El stock actual es obligatorio.'),
            decimal_finito,
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
            InputRequired(message='El stock mínimo es obligatorio.'),
            decimal_finito,
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
    imagen = FileField(
        'Fotografía del Producto',
        render_kw={
            'class': 'form-control',
            'id': 'select_imagen_producto',
            'accept': '.png,.jpg,.jpeg,.webp,.gif'
        }
    )

    imagen_existente = SelectField(
        'Usar una imagen existente',
        choices=[],
        render_kw={
            'class': 'form-select',
            'id': 'imagen_existente_producto'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 11: Botón de envío procesado por el servidor Flask
    # --------------------------------------------------------------------------
    submit = SubmitField(
        'Guardar Producto',
        render_kw={
            'class': 'btn btn-caramelo px-4 py-2 text-white shadow-sm'
        }
    )
