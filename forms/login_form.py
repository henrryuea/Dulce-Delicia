"""Formulario WTForms para el acceso de clientes y personal."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    """
    Formulario común; el rol y estado aprobado determinan los permisos de la cuenta.
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
            'autofocus': True,
            'autocomplete': 'username'
        }
    )

    password = PasswordField(
        'Contraseña de Acceso',
        validators=[
            DataRequired(message='Por favor ingrese su contraseña.'),
            Length(min=1, max=128, message='La contraseña no puede superar 128 caracteres.')
        ],
        render_kw={
            'placeholder': '••••••••',
            'class': 'form-control',
            'autocomplete': 'current-password'
        }
    )

    submit = SubmitField(
        'Ingresar al Sistema',
        render_kw={
            'class': 'btn btn-caramelo w-100 py-2 fw-semibold'
        }
    )
