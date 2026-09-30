"""Formulario para crear pedidos con validación del servidor."""

from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, HiddenField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, Regexp


class FacturacionForm(FlaskForm):
    clave_idempotencia = HiddenField(
        validators=[
            DataRequired(),
            Regexp(r'^[A-Za-z0-9_-]{32,64}$', message='Clave de operación inválida.')
        ]
    )
    cedula_ruc = StringField(
        'Cédula o RUC',
        validators=[
            Regexp(r'^\d{10,13}$', message='Ingrese una identificación de 10 a 13 dígitos.')
        ],
        render_kw={'class': 'form-control', 'inputmode': 'numeric', 'autocomplete': 'off'}
    )
    nombre_cliente = StringField(
        'Nombre o razón social',
        validators=[Optional(), Length(max=120)],
        render_kw={'class': 'form-control', 'autocomplete': 'name'}
    )
    id_tipo_cliente = SelectField(
        'Tipo de cliente',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    correo = StringField(
        'Correo electrónico',
        validators=[Optional(), Email(message='Ingrese un correo electrónico válido.'), Length(max=120)],
        render_kw={'class': 'form-control', 'type': 'email', 'autocomplete': 'email'}
    )
    telefono = StringField(
        'Teléfono',
        validators=[Optional(), Length(max=30)],
        render_kw={'class': 'form-control', 'autocomplete': 'tel'}
    )
    direccion = StringField(
        'Dirección',
        validators=[Optional(), Length(max=200)],
        render_kw={'class': 'form-control', 'autocomplete': 'street-address'}
    )
    id_metodo_pago = SelectField(
        'Método del primer abono',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-select'}
    )
    monto_inicial = DecimalField(
        'Abono inicial (USD)',
        places=2,
        default=Decimal('0.00'),
        validators=[Optional(), NumberRange(
            min=0, max=Decimal('9999999999.99'),
            message='El abono debe estar entre $0 y $9,999,999,999.99.'
        )],
        render_kw={'class': 'form-control', 'min': '0', 'step': '0.01'}
    )
    observaciones = TextAreaField(
        'Observaciones del pedido',
        validators=[Optional(), Length(max=300)],
        render_kw={'class': 'form-control', 'rows': 2}
    )
    submit = SubmitField(
        'Crear pedido',
        render_kw={'class': 'btn btn-caramelo px-4 py-2 text-white shadow-sm'}
    )


class AbonoForm(FlaskForm):
    clave_idempotencia = HiddenField(
        validators=[
            DataRequired(),
            Regexp(r'^[A-Za-z0-9_-]{32,64}$', message='Clave de operación inválida.')
        ]
    )
    monto = DecimalField(
        'Monto del abono (USD)',
        places=2,
        validators=[NumberRange(
            min=Decimal('0.01'), max=Decimal('9999999999.99'),
            message='El abono debe estar entre $0.01 y $9,999,999,999.99.'
        )],
        render_kw={'class': 'form-control', 'min': '0.01', 'step': '0.01', 'required': True}
    )
    id_metodo_pago = SelectField(
        'Método de pago',
        coerce=int,
        validators=[NumberRange(min=1, message='Seleccione un método de pago.')],
        render_kw={'class': 'form-select', 'required': True}
    )
    observaciones = TextAreaField(
        'Referencia o nota',
        validators=[Optional(), Length(max=200)],
        render_kw={'class': 'form-control', 'rows': 1}
    )
    submit = SubmitField(
        'Registrar abono y emitir comprobante',
        render_kw={'class': 'btn btn-caramelo text-white'}
    )
