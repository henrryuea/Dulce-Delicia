"""
================================================================================
PROYECTO: Dulce Delicia - Sistema de Gestión de Pastelería Artesanal
ARCHIVO: forms/facturacion_form.py
ASIGNATURA: Desarrollo de Aplicaciones Web
UNIVERSIDAD: Universidad Estatal Amazónica (UEA)
ESTUDIANTE: Desarrollo Web 2026
SEMANA: 11 y 12 - Proyecto Integrador U3 (12/16)
TEMA: Validación de Facturación con Flask-WTF y Normalización en 3FN
================================================================================
DESCRIPCIÓN DEL ARCHIVO:
En este archivo estructuramos el formulario 'FacturacionForm' para la emisión
y corrección de comprobantes de venta en la pastelería.

Estructura Normalizada (3FN):
  - Se vincula mediante clave foránea (id_cliente) con la tabla 'clientes'.
  - Se vincula mediante clave foránea (id_metodo_pago) con el catálogo 'metodos_pago'
    (Efectivo, Transferencia, Tarjeta, Depósito).
  - Se vincula mediante clave foránea (id_estado_factura) con el catálogo
    'estados_factura' (Emitida, Anulada, Pendiente).
  - Almacena el número correlativo único de comprobante, fecha de emisión,
    subtotal, valor de IVA al 15% (Ecuador), total y notas u observaciones.
================================================================================
"""

# ==============================================================================
# 1. IMPORTACIONES DE LIBRERÍAS Y COMPONENTES
# ==============================================================================
from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField,       # Campo para el número de comprobante
    DateField,         # Selector de fecha en formato YYYY-MM-DD
    DecimalField,      # Valores numéricos monetarios con dos decimales
    SelectField,       # Selectores para cliente, método de pago y estado
    TextAreaField,     # Observaciones o notas adicionales de la venta
    SubmitField        # Botón de confirmación
)
from wtforms.validators import (
    DataRequired,      # Validación de campo obligatorio
    Length,            # Restricción de longitud de texto
    NumberRange,       # Restricción de valores positivos
    Regexp             # Formato correlativo (ej. FAC-001)
)


# ==============================================================================
# 2. DEFINICIÓN DE LA CLASE DEL FORMULARIO DE FACTURACIÓN (3FN)
# ==============================================================================
class FacturacionForm(FlaskForm):
    """
    Formulario web para la emisión y gestión de facturas de venta.
    Reutilizado en '/facturacion/nueva' y '/facturacion/editar/<id>'.
    """

    # --------------------------------------------------------------------------
    # Campo 1: Número correlativo único de factura (Ej: FAC-001, FAC-002)
    # --------------------------------------------------------------------------
    numero = StringField(
        'N° de Factura / Comprobante',
        validators=[
            DataRequired(message='El número de factura es obligatorio.'),
            Length(min=5, max=30, message='El número debe tener entre 5 y 30 caracteres.'),
            Regexp(r'^[A-Z0-9\-]+$', message='El formato solo permite mayúsculas, números y guiones (ej. FAC-001).')
        ],
        render_kw={
            'placeholder': 'Ej. FAC-001',
            'class': 'form-control font-monospace fw-bold',
            'autofocus': True
        }
    )

    # --------------------------------------------------------------------------
    # Campo 2: Cliente asociado (Clave Foránea a la tabla 'clientes')
    # --------------------------------------------------------------------------
    id_cliente = SelectField(
        'Cliente Registrado (Catálogo de Clientes)',
        coerce=int,
        choices=[
            (1, 'Consumidor Final (9999999999999)'),
            (2, 'Ana Torres Mendoza (1718293841)')
        ],
        validators=[
            DataRequired(message='Debe seleccionar el cliente para la factura.')
        ],
        render_kw={
            'class': 'form-select'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 3: Fecha de emisión de la factura
    # --------------------------------------------------------------------------
    fecha_emision = DateField(
        'Fecha de Emisión',
        validators=[
            DataRequired(message='La fecha de emisión es obligatoria.')
        ],
        default=date.today,
        format='%Y-%m-%d',
        render_kw={
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 4: Método de pago (Catálogo 3FN: 'metodos_pago')
    # --------------------------------------------------------------------------
    id_metodo_pago = SelectField(
        'Método de Pago (Catálogo 3FN)',
        coerce=int,
        choices=[
            (1, '💵 EFECTIVO (Cobro en Caja)'),
            (2, '🏦 TRANSFERENCIA (Banco Pichincha / Guayaquil / Produbanco)'),
            (3, '💳 TARJETA (Débito o Crédito Datafast)'),
            (4, '📱 DEPOSITO (Depósito Bancario Directo)')
        ],
        validators=[
            DataRequired(message='Debe seleccionar el método de pago.')
        ],
        render_kw={
            'class': 'form-select'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 5: Subtotal antes de impuestos ($ USD)
    # --------------------------------------------------------------------------
    subtotal = DecimalField(
        'Subtotal ($ USD)',
        places=2,
        validators=[
            DataRequired(message='El subtotal es obligatorio.'),
            NumberRange(min=0.01, max=10000.00, message='El subtotal debe ser mayor a $0.00.')
        ],
        render_kw={
            'placeholder': '0.00',
            'step': '0.01',
            'class': 'form-control',
            'id': 'subtotal_input'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 6: IVA 15% vigente en Ecuador ($ USD)
    # --------------------------------------------------------------------------
    iva = DecimalField(
        'IVA 15% ($ USD)',
        places=2,
        validators=[
            DataRequired(message='El cálculo de IVA es obligatorio.'),
            NumberRange(min=0.00, max=2000.00, message='El IVA debe ser mayor o igual a $0.00.')
        ],
        render_kw={
            'placeholder': '0.00',
            'step': '0.01',
            'class': 'form-control',
            'id': 'iva_input'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 7: Total a cancelar ($ USD)
    # --------------------------------------------------------------------------
    total = DecimalField(
        'Total de la Factura ($ USD)',
        places=2,
        validators=[
            DataRequired(message='El valor total es obligatorio.'),
            NumberRange(min=0.01, max=12000.00, message='El total debe ser mayor a $0.00.')
        ],
        render_kw={
            'placeholder': '0.00',
            'step': '0.01',
            'class': 'form-control font-monospace fw-bold fs-5 text-dark',
            'id': 'total_input'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 8: Estado del comprobante (Catálogo 3FN: 'estados_factura')
    # --------------------------------------------------------------------------
    id_estado_factura = SelectField(
        'Estado del Comprobante (Catálogo 3FN)',
        coerce=int,
        choices=[
            (1, '✅ EMITIDA (Comprobante Válido y Cobrado)'),
            (2, '❌ ANULADA (Comprobante Anulado)'),
            (3, '⏳ PENDIENTE (Pendiente de Confirmación de Pago)')
        ],
        default=1,
        validators=[
            DataRequired(message='Debe seleccionar el estado de la factura.')
        ],
        render_kw={
            'class': 'form-select'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 9: Observaciones o descripción de postres vendidos
    # --------------------------------------------------------------------------
    observaciones = TextAreaField(
        'Observaciones / Detalle de la Venta',
        validators=[
            Length(max=300, message='Las observaciones no pueden superar los 300 caracteres.')
        ],
        render_kw={
            'rows': 2,
            'placeholder': 'Detalle de postres vendidos (ej. 2x Torta de chocolate, 1x Café americano)...',
            'class': 'form-control'
        }
    )

    # --------------------------------------------------------------------------
    # Campo 10: Botón de emisión de factura
    # --------------------------------------------------------------------------
    submit = SubmitField(
        'Emitir y Guardar Factura en Base de Datos',
        render_kw={
            'class': 'btn btn-caramelo px-4 py-2 text-white shadow-sm'
        }
    )
