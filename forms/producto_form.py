from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ProductoForm(FlaskForm):
    """Formulario de alta y edición de productos del catálogo."""

    categoria_producto_id = SelectField(
        'Categoría',
        coerce=int,
        validators=[DataRequired(message='Selecciona una categoría.')],
    )
    nombre = StringField(
        'Nombre del producto',
        validators=[
            DataRequired(message='El nombre del producto es obligatorio.'),
            Length(min=3, max=100, message='Debe tener entre 3 y 100 caracteres.'),
        ],
    )
    precio = FloatField(
        'Precio ($)',
        validators=[
            DataRequired(message='Ingresa un precio válido.'),
            NumberRange(min=0.01, message='El precio debe ser mayor que cero.'),
        ],
    )
    imagen = StringField(
        'URL de imagen (opcional)',
        validators=[
            Optional(),
            Length(max=500, message='La URL no puede exceder 500 caracteres.'),
        ],
    )
    descripcion = TextAreaField(
        'Descripción',
        validators=[
            DataRequired(message='La descripción es obligatoria.'),
            Length(min=10, max=500, message='Debe tener entre 10 y 500 caracteres.'),
        ],
    )
    disponible = BooleanField('Disponible para pedidos')
    es_insumo = BooleanField('Es insumo (materia prima, no se vende)')
    stock_entrada = IntegerField(
        'Unidades recibidas para agregar al stock',
        validators=[
            Optional(),
            NumberRange(min=0, message='Las unidades recibidas no pueden ser negativas.')
        ],
        default=0
    )
    submit = SubmitField('Guardar producto')
