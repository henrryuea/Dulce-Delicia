# ==============================================================================
# PROYECTO: DULCE DELICIA - FORMULARIO DE REGISTRO SEGURIZADO
# ==============================================================================
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SelectField, SubmitField, BooleanField, DateField
)
from wtforms.validators import DataRequired, Length, EqualTo, Email, Regexp


class UsuarioForm(FlaskForm):
    """
    Formulario completo para el registro de nuevos usuarios.
    Incluye datos básicos, consentimiento y comprobación anti-bot en servidor.
    """
    fecha_nacimiento = DateField(
        'Fecha de nacimiento',
        format='%Y-%m-%d',
        validators=[DataRequired(message='Ingresa tu fecha de nacimiento en formato AAAA-MM-DD.')]
    )

    es_mayor_edad = BooleanField(
        'Declaro que soy mayor de edad.',
        validators=[DataRequired(message='Debes declarar que eres mayor de edad para crear la cuenta.')]
    )

    nombres = StringField(
        'Nombres',
        validators=[
            DataRequired(message='Ingresa tus nombres.'),
            Length(min=4, max=80, message='Los nombres deben tener al menos 4 caracteres.'),
            Regexp(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', message='Los nombres solo pueden contener letras y espacios.')
        ]
    )

    apellidos = StringField(
        'Apellidos',
        validators=[
            DataRequired(message='Ingresa tus apellidos.'),
            Length(min=4, max=80, message='Los apellidos deben tener al menos 4 caracteres.'),
            Regexp(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', message='Los apellidos solo pueden contener letras y espacios.')
        ]
    )

    usuario = StringField(
        'Nombre de Usuario',
        validators=[
            DataRequired(message='El nombre de usuario es obligatorio.'),
            Length(min=3, max=50, message='El usuario debe tener entre 3 y 50 caracteres.')
        ]
    )

    correo = StringField(
        'Correo Electrónico',
        validators=[
            DataRequired(message='El correo electrónico es obligatorio.'),
            Email(message='Ingresa un formato de correo válido (ej: usuario@empresa.com).')
        ]
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            DataRequired(message='El teléfono es obligatorio.'),
            Regexp(r'^\d{10}$', message='El teléfono debe contener exactamente 10 dígitos numéricos.')
        ]
    )

    rol_id = SelectField(
        'Perfil al que deseas acceder',
        coerce=int,
        validators=[DataRequired(message='Selecciona el rol correspondiente.')]
    )

    password = PasswordField(
        'Contraseña',
        validators=[
            DataRequired(message='La contraseña es obligatoria.'),
            Length(min=12, message='La clave debe tener al menos 12 caracteres.')
        ]
    )

    confirm_password = PasswordField(
        'Confirmar Contraseña',
        validators=[
            DataRequired(message='Por favor confirma tu contraseña.'),
            EqualTo('password', message='Las contraseñas ingresadas no coinciden.')
        ]
    )

    acepta_terminos = BooleanField(
        'Acepto los Términos de uso.',
        validators=[DataRequired(message='Debes aceptar los Términos de uso.')]
    )
    acepta_tratamiento_datos = BooleanField(
        'He leído el Aviso de Privacidad y autorizo el tratamiento necesario para gestionar mi cuenta y mis pedidos.',
        validators=[DataRequired(message='Debes revisar y aceptar el Aviso de Privacidad para crear tu cuenta.')]
    )

    sitio_web = StringField('Deja este campo vacío')

    submit = SubmitField('Registrar Cuenta')
