from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp


class ClienteForm(FlaskForm):
    """
    Formulario de registro y edición de clientes.
    Contiene únicamente datos propios del cliente; los productos que compra
    se gestionan de forma independiente en el módulo de Facturación.
    """
    cedula = StringField(
        'Cédula / RUC',
        validators=[
            DataRequired(message='La cédula es obligatoria.'),
            Regexp(r'^(?:\d{10}|\d{13})$', message='Ingresa una cédula de 10 o un RUC de 13 dígitos.')
        ]
    )

    nombre = StringField(
        'Nombre / Razón Social',
        validators=[
            DataRequired(message='El nombre es obligatorio.'),
            Length(min=3, max=150, message='Debe contener entre 3 y 150 caracteres.')
        ]
    )

    apellido = StringField(
        'Apellido(s)',
        validators=[Length(max=100, message='Máximo 100 caracteres.')],
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            DataRequired(message='El teléfono es obligatorio.'),
            Regexp(r'^\d{7,10}$', message='Ingresa un teléfono válido (7 a 10 dígitos).')
        ]
    )

    correo = StringField(
        'Correo electrónico',
        validators=[
            DataRequired(message='El correo es obligatorio.'),
            Regexp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', message='Ingresa un correo electrónico válido.')
        ]
    )

    # Clasificación del cliente seleccionada desde el catálogo de referencia.
    tipo_cliente_id = SelectField(
        'Tipo de cliente',
        coerce=int,
        validators=[DataRequired(message='Selecciona un tipo de cliente.')]
    )

    ciudad = StringField(
        'Ciudad',
        validators=[
            DataRequired(message='La ciudad es obligatoria.'),
            Length(max=50, message='Máximo 50 caracteres.')
        ]
    )

    direccion = StringField(
        'Dirección del domicilio',
        validators=[Length(max=300, message='Máximo 300 caracteres.')],
    )

    submit = SubmitField('Guardar Cliente')
