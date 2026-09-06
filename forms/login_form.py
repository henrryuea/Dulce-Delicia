"""Formulario WTForms para el acceso administrativo."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    """
    Formulario para el control de acceso al sistema administrativo.
    Permite validar que solo usuarios autorizados gestionen los datos.
    """
    usuario = StringField(
        'Nombre de Usuario',
        validators=[
            DataRequired(message='Por favor ingrese su nombre de usuario.'),
            Length(min=3, max=30, message='El usuario debe tener entre 3 y 30 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ej. admin',
            'class': 'form-control',
            'autofocus': True
        }
    )

    password = PasswordField(
        'Contraseña de Acceso',
        validators=[
            DataRequired(message='Por favor ingrese su contraseña.'),
            Length(min=4, max=50, message='La contraseña debe tener al menos 4 caracteres.')
        ],
        render_kw={
            'placeholder': '••••••••',
            'class': 'form-control'
        }
    )

    submit = SubmitField(
        'Ingresar al Sistema',
        render_kw={
            'class': 'btn btn-caramelo w-100 py-2 fw-semibold'
        }
    )
