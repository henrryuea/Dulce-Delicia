from flask_wtf import FlaskForm
from wtforms import FileField, StringField


class MiCuentaForm(FlaskForm):
    nombres = StringField('Nombres')
    apellidos = StringField('Apellidos')
    telefono = StringField('Teléfono')
    foto_perfil = FileField('Foto de perfil')
