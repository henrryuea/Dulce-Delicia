"""Formularios de registro de clientes y solicitudes de acceso interno."""

from flask_wtf import FlaskForm
from wtforms import (
    EmailField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    Regexp,
)


class RegistroForm(FlaskForm):
    usuario = StringField(
        'Usuario',
        validators=[
            DataRequired(),
            Length(min=3, max=30),
            Regexp(r'^[A-Za-z0-9_-]+$', message='Use letras, números, guion o guion bajo.')
        ],
        render_kw={'class': 'form-control', 'autocomplete': 'username'}
    )
    nombre = StringField(
        'Nombre completo',
        validators=[DataRequired(), Length(min=3, max=120)],
        render_kw={'class': 'form-control', 'autocomplete': 'name'}
    )
    correo = EmailField(
        'Correo electrónico',
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={'class': 'form-control', 'autocomplete': 'email'}
    )
    rol_solicitado = SelectField(
        'Tipo de cuenta',
        choices=[('CLIENTE', 'Cliente'), ('STAFF', 'Personal interno')],
        validators=[DataRequired()],
        render_kw={'class': 'form-select'}
    )
    cedula_ruc = StringField(
        'Cédula o RUC',
        validators=[
            Optional(),
            Regexp(r'^\d{10,13}$', message='Ingrese de 10 a 13 dígitos.')
        ],
        render_kw={'class': 'form-control', 'inputmode': 'numeric', 'autocomplete': 'off'}
    )
    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(),
            Length(min=12, max=128, message='Use entre 12 y 128 caracteres.')
        ],
        render_kw={'class': 'form-control', 'autocomplete': 'new-password'}
    )
    confirmar_password = PasswordField(
        'Confirmar contraseña',
        validators=[
            DataRequired(),
            EqualTo('password', message='Las contraseñas no coinciden.')
        ],
        render_kw={'class': 'form-control', 'autocomplete': 'new-password'}
    )
    submit = SubmitField(
        'Enviar solicitud de cuenta',
        render_kw={'class': 'btn btn-caramelo w-100 py-2 text-white'}
    )
