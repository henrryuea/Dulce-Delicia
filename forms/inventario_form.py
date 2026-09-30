"""Formulario WTForms para registrar ajustes de inventario."""
from flask_wtf import FlaskForm
from wtforms import DecimalField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError


def decimal_finito(form, field):
    del form
    if field.data is not None and not field.data.is_finite():
        raise ValidationError('Ingrese un número válido y finito.')


class InventarioForm(FlaskForm):
    id_producto = SelectField(
        'Producto',
        coerce=int,
        validators=[DataRequired(message='Seleccione un producto.')],
        render_kw={'class': 'form-select'}
    )
    tipo = SelectField(
        'Tipo de movimiento',
        choices=[('entrada', 'Entrada'), ('salida', 'Salida')],
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    cantidad = DecimalField(
        'Cantidad',
        places=3,
        validators=[
            DataRequired(message='Ingrese la cantidad.'),
            decimal_finito,
            NumberRange(min=0.001, max=100000, message='La cantidad debe ser mayor a cero.')
        ],
        render_kw={'class': 'form-control', 'min': '0.001', 'step': '0.001'}
    )
    observaciones = TextAreaField(
        'Motivo',
        validators=[DataRequired(message='Indique el motivo del ajuste.'), Length(max=250)],
        render_kw={'class': 'form-control', 'rows': 2}
    )
    submit = SubmitField(
        'Registrar movimiento',
        render_kw={'class': 'btn btn-caramelo text-white'}
    )
