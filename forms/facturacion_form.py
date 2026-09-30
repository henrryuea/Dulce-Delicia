# ==============================================================================
# FORMULARIO: FACTURACIÓN Y COTIZACIONES COMERCIALES
# ==============================================================================
# Gestiona la emisión y edición de comprobantes de venta y propuestas económicas.
# Soporta detalle dinámico de ítems y pagos al confirmar el pedido o al retirarlo.
# ==============================================================================

from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, TextAreaField, HiddenField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp


class FacturacionForm(FlaskForm):
    """
    Formulario unificado para Facturas de Venta y Cotizaciones Comerciales.
    """
    # Clasificación del comprobante
    tipo = SelectField(
        'Tipo de Documento',
        choices=[
            ('Factura', 'Comprobante de venta'),
            ('Cotizacion', 'Cotización / Proforma Comercial')
        ],
        validators=[DataRequired(message='Selecciona el tipo de documento.')]
    )

    # Número secuencial o código identificador (se autogenera si se deja vacío)
    numero = StringField(
        'N° Documento / Código (Auto-generado)',
        validators=[
            Optional(),
            Length(max=40, message='Debe contener hasta 40 caracteres.')
        ]
    )

    # La cédula se escribe y se valida contra el padrón real de clientes.
    cliente_cedula = StringField(
        'Cliente',
        validators=[
            DataRequired(message='Ingresa la cédula o RUC del cliente.'),
            Regexp(r'^\d{10}(?:\d{3})?$', message='Ingresa una cédula de 10 o un RUC de 13 dígitos.')
        ]
    )
    tipo_identificacion = SelectField(
        'Tipo de identificación',
        choices=[
            ('', 'Selecciona el tipo'),
            ('cedula', 'Cédula (10 dígitos)'),
            ('ruc', 'RUC (13 dígitos)'),
        ],
        validators=[Optional()]
    )
    cliente_nombre = StringField('Nombres / Razón social', validators=[Optional(), Length(max=150)])
    cliente_apellido = StringField('Apellidos', validators=[Optional(), Length(max=100)])
    cliente_correo = StringField('Correo electrónico', validators=[Optional(), Length(max=150)])
    cliente_direccion = StringField('Dirección del domicilio', validators=[Optional(), Length(max=300)])
    cliente_ciudad = StringField('Ciudad', validators=[Optional(), Length(max=100)])
    cliente_telefono = StringField('Celular / Teléfono', validators=[Optional(), Length(max=20)])

    # Fecha de emisión del documento (formato YYYY-MM-DD)
    fecha = StringField(
        'Fecha de emisión',
        validators=[
            DataRequired(message='La fecha es obligatoria.'),
            Length(min=8, max=10, message='Formato de fecha no válido.')
        ]
    )

    # Plazo de vigencia de la oferta comercial (aplica principalmente para cotizaciones)
    validez = StringField(
        'Vigencia / Plazo de la oferta',
        validators=[
            Optional(),
            Length(max=50, message='Máximo 50 caracteres para la vigencia.')
        ]
    )

    # Forma de pago registrada para el documento de venta
    forma_pago = SelectField(
        'Forma de Pago',
        choices=[
            ('Transferencia bancaria', 'Transferencia bancaria (Directa / Interbancaria)'),
            ('Efectivo', 'Efectivo (Sin utilización del sistema financiero)'),
            ('Tarjeta de débito', 'Tarjeta de débito'),
            ('Tarjeta de crédito', 'Tarjeta de crédito'),
            ('Depósito bancario', 'Depósito bancario en cuenta')
        ],
        default='Transferencia bancaria',
        validators=[Optional()]
    )

    # Modalidad de cobro: un pago al confirmar o dos pagos hasta el retiro.
    tipo_pago = SelectField(
        'Forma de completar el pago',
        choices=[
            ('contado', 'Un solo pago al confirmar el pedido'),
            ('plazos', 'Dos pagos: al confirmar y al retirar')
        ],
        default='contado',
        validators=[Optional()]
    )

    # Campo interno conservado para compatibilidad con documentos existentes.
    plazo_meses = SelectField(
        'Número de pagos',
        coerce=int,
        choices=[
            (1, 'Un pago'),
            (2, 'Dos pagos')
        ],
        default=1,
        validators=[Optional()]
    )

    fecha_entrega = StringField(
        'Fecha de entrega',
        validators=[
            Optional(),
            Length(max=10, message='Usa el formato de fecha AAAA-MM-DD.')
        ]
    )

    modalidad_entrega = SelectField(
        'Modalidad de entrega',
        choices=[
            ('retiro_local', 'Retiro en el local'),
            ('domicilio', 'Entrega a domicilio')
        ],
        default='retiro_local',
        validators=[Optional()]
    )

    ubicacion_entrega = StringField(
        'Dirección o referencia de entrega',
        validators=[Optional(), Length(max=300, message='Máximo 300 caracteres.')]
    )
    
    # Campo oculto que almacena la lista de productos/ítems serializada en JSON
    productos_json = HiddenField('Detalle de Productos JSON')
    
    # Subtotal calculado antes de impuestos
    subtotal = FloatField(
        'Subtotal ($)',
        validators=[
            Optional(),
            NumberRange(min=0, message='El subtotal no puede ser un valor negativo.')
        ]
    )

    # Total de impuestos calculado con los parámetros fiscales activos.
    aplica_impuestos = BooleanField('Aplicar impuestos', default=True)
    iva = FloatField(
        'Impuestos calculados ($)',
        validators=[
            Optional(),
            NumberRange(min=0, message='El IVA no puede ser un valor negativo.')
        ]
    )

    # Monto total general del documento (Total Original)
    monto = FloatField(
        'Total General ($)',
        validators=[
            DataRequired(message='El monto total es obligatorio.'),
            NumberRange(min=0, message='El total no puede ser negativo.')
        ]
    )

    # Valor abonado o anticipo entregado por el cliente
    anticipo = FloatField(
        'Abono Recibido ($)',
        validators=[
            Optional(),
            NumberRange(min=0, message='El anticipo no puede ser negativo.')
        ],
        default=0.00
    )

    # Saldo pendiente de cobro contra entrega
    saldo_pendiente = FloatField(
        'Saldo Pendiente / Diferencia ($)',
        validators=[
            Optional(),
            NumberRange(min=0, message='El saldo no puede ser negativo.')
        ],
        default=0.00
    )
    
    # Estado actual del proceso de cobranza o aprobación (clave foránea hacia estados_documento)
    estado_id = SelectField(
        'Estado del Documento',
        coerce=int,
        validators=[DataRequired(message='Selecciona el estado actual del documento.')]
    )

    # Notas, términos de pago y condiciones comerciales
    notas = TextAreaField(
        'Notas, Términos y Condiciones de Pago',
        validators=[
            Optional(),
            Length(max=500, message='Las notas no pueden exceder 500 caracteres.')
        ]
    )

    # Botón de guardado
    submit = SubmitField('Guardar y Emitir Documento')
