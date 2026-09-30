# ==============================================================================
# FORMULARIO: REGISTRO Y EDICIÓN DE PROVEEDORES
# ==============================================================================
# Modela los datos de contacto y clasificación de proveedores del negocio.
# ==============================================================================

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp, URL


class ProveedorForm(FlaskForm):
    """
    Formulario para registrar y editar proveedores de insumos y productos.
    """
    nombre = StringField(
        'Nombre del proveedor',
        validators=[
            DataRequired(message='El nombre del proveedor es obligatorio.'),
            Length(min=3, max=100, message='Debe contener entre 3 y 100 caracteres.')
        ]
    )

    ruc = StringField(
        'RUC fiscal',
        validators=[
            Optional(),
            Regexp(r'^\d{13}$', message='El RUC debe contener exactamente 13 dígitos.')
        ]
    )

    categoria_id = SelectField(
        'Categoría del proveedor',
        coerce=int,
        validators=[DataRequired(message='Selecciona una categoría válida.')]
    )

    correo = StringField(
        'Correo electrónico',
        validators=[
            DataRequired(message='El correo del proveedor es obligatorio.'),
            Email(message='Ingresa un correo electrónico válido.'),
            Length(max=150, message='El correo no puede superar 150 caracteres.')
        ]
    )

    sitio_web = StringField(
        'Página web (opcional)',
        validators=[
            Optional(),
            URL(require_tld=True, message='Ingresa una dirección web válida.'),
            Length(max=300, message='La página web no puede superar 300 caracteres.')
        ]
    )

    persona_contacto = StringField(
        'Persona de contacto',
        validators=[Optional(), Length(max=150)]
    )

    telefono = StringField(
        'Teléfono',
        validators=[
            DataRequired(message='El teléfono del proveedor es obligatorio.'),
            Length(min=7, max=30, message='El teléfono debe tener entre 7 y 30 caracteres.'),
            Regexp(r'^[+()\d\s.-]+$', message='Ingresa un teléfono válido.')
        ]
    )

    estado_id = SelectField(
        'Estado operativo',
        coerce=int,
        validators=[DataRequired(message='Selecciona un estado operativo válido.')]
    )

    # Botón de envío
    submit = SubmitField('Guardar proveedor')
