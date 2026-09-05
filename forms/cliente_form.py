"""
================================================================================
PROYECTO: Dulce Delicia - Sistema de Gestión de Pastelería Artesanal
ARCHIVO: forms/cliente_form.py
ASIGNATURA: Desarrollo de Aplicaciones Web
UNIVERSIDAD: Universidad Estatal Amazónica (UEA)
ESTUDIANTE: Desarrollo Web 2026
SEMANA: 11 y 12 - Proyecto Integrador U3 (12/16)
TEMA: Validación de Clientes con Flask-WTF y Normalización en 3FN
================================================================================
DESCRIPCIÓN DEL ARCHIVO:
Este módulo define la clase de formulario 'ClienteForm' que gestiona la entrada
y modificación de datos de clientes en la pastelería artesanal Dulce Delicia.

Estructura Relacional Normalizada (3FN):
  - Se vincula mediante clave foránea (id_tipo_cliente) con el catálogo
    'tipos_cliente' ('PERSONA NATURAL' o 'EMPRESA').
  - Almacena identificación fiscal única (cedula_ruc), nombres completos,
    correo electrónico institucional o personal, número telefónico y domicilio.

VALIDACIONES INTEGRADAS DEL LADO DEL SERVIDOR:
  - Token CSRF obligatorio mediante FlaskForm.
  - DataRequired: Previene registros incompletos.
  - Length: Limita longitudes según las restricciones de la base de datos.
  - Email: Verifica la estructura sintáctica estándar de correos.
  - Regexp: Valida que cédula/RUC y teléfono contengan únicamente dígitos.
================================================================================
"""

# ==============================================================================
# 1. IMPORTACIONES DE MÓDULOS DE FLASK-WTF Y WTFORMS
# ==============================================================================
from flask_wtf import FlaskForm
from wtforms import (
    StringField,       # Campo para nombres, identificación y dirección
    EmailField,        # Campo especializado para direcciones de correo
    SelectField,       # Selector para el catálogo 'tipos_cliente'
    SubmitField        # Botón de envío procesado en el servidor
)
from wtforms.validators import (
    DataRequired,      # Obliga a ingresar un valor
    Length,            # Valida el rango de caracteres
    Email,             # Valida el formato de correo electrónico
    Regexp             # Expresión regular para dígitos numéricos
)


# ==============================================================================
# 2. DEFINICIÓN DE LA CLASE DEL FORMULARIO CLIENTEFORM (3FN)
# ==============================================================================
class ClienteForm(FlaskForm):
    """
    Formulario web para el registro y edición de clientes.
    Reutilizado en las rutas '/clientes/nuevo' y '/clientes/editar/<id>'.
    """

    # --------------------------------------------------------------------------
    # Campo 1: Tipo de Cliente (Clave foránea hacia 'tipos_cliente')
    # --------------------------------------------------------------------------
    id_tipo_cliente = SelectField(
        'Tipo de Cliente (Catálogo Normalizado)',
        coerce=int,
        choices=[
            (1, '👤 PERSONA NATURAL (Consumidor Final o Particular)'),
            (2, '🏢 EMPRESA (Cliente Corporativo o Institucional)')
        ],
        validators=[
            DataRequired(message='Debe seleccionar el tipo de cliente.')
        ],
        render_kw={
            'class': 'form-select',
            'autofocus': True
        }
    )

    # --------------------------------------------------------------------------
    # Campo 2: Nombres completos del cliente o Razón Social
    # --------------------------------------------------------------------------
    nombre = StringField(
        'Nombres Completos / Razón Social',
        validators=[
            DataRequired(message='El nombre del cliente es obligatorio.'),
            Length(min=3, max=120, message='El nombre debe tener entre 3 y 120 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ej. Ana Lucía Torres Mendoza / Eventos Gourmet S.A.',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 3: Cédula de identidad ecuatoriana o RUC (10 a 13 dígitos)
    # --------------------------------------------------------------------------
    cedula_ruc = StringField(
        'Cédula de Identidad / RUC',
        validators=[
            DataRequired(message='La identificación es obligatoria.'),
            Length(min=10, max=13, message='La identificación debe contener entre 10 y 13 dígitos.'),
            Regexp(r'^\d{10,13}$', message='La identificación debe contener solo números (10 dígitos para cédula, 13 para RUC).')
        ],
        render_kw={
            'placeholder': 'Ej. 1718293841 / 1791234567001',
            'maxlength': '13',
            'class': 'form-control font-monospace'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 4: Correo electrónico para facturas y confirmación de pedidos
    # --------------------------------------------------------------------------
    correo = EmailField(
        'Correo Electrónico',
        validators=[
            DataRequired(message='El correo electrónico es obligatorio.'),
            Email(message='Ingrese un correo electrónico válido (ej. cliente@email.com).'),
            Length(max=120, message='El correo no debe superar los 120 caracteres.')
        ],
        render_kw={
            'placeholder': 'cliente@correo.com',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 5: Teléfono celular de contacto (10 dígitos numéricos)
    # --------------------------------------------------------------------------
    telefono = StringField(
        'Teléfono Celular de Contacto',
        validators=[
            DataRequired(message='El teléfono de contacto es obligatorio.'),
            Length(min=9, max=15, message='El teléfono debe tener entre 9 y 15 dígitos.'),
            Regexp(r'^\d{9,15}$', message='El teléfono solo debe contener números.')
        ],
        render_kw={
            'placeholder': 'Ej. 0991112233',
            'maxlength': '15',
            'class': 'form-control font-monospace'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 6: Dirección domiciliaria o lugar de entrega
    # --------------------------------------------------------------------------
    direccion = StringField(
        'Dirección Domiciliaria / Entrega',
        validators=[
            DataRequired(message='La dirección domiciliaria es obligatoria.'),
            Length(min=5, max=200, message='La dirección debe tener entre 5 y 200 caracteres.')
        ],
        render_kw={
            'placeholder': 'Ej. Av. República y Eloy Alfaro N34-12, Quito',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 7: Botón de envío procesado por Flask
    # --------------------------------------------------------------------------
    submit = SubmitField(
        'Guardar Cliente en Base de Datos',
        render_kw={
            'class': 'btn btn-caramelo px-4 py-2 text-white shadow-sm'
        }
    )
