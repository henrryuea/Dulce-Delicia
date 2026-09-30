from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class TipoClienteForm(FlaskForm):
    """
    Formulario para administrar las categorías de cliente.
    """
    nombre = StringField(
        'Nombre del tipo de cliente',
        validators=[
            DataRequired(message='El nombre del tipo de cliente es obligatorio.'),
            Length(min=3, max=60, message='Debe tener entre 3 y 60 caracteres.')
        ]
    )

    submit = SubmitField('Guardar Tipo de Cliente')
