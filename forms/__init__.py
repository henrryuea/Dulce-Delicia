"""
Módulo de Formularios para Dulce Delicia
Organización de clases Flask-WTF / WTForms
Avance 11/16 - Proyecto Integrador U3
"""
from .producto_form import ProductoForm
from .cliente_form import ClienteForm
from .proveedor_form import ProveedorForm
from .facturacion_form import FacturacionForm
from .login_form import LoginForm

__all__ = [
    'ProductoForm',
    'ClienteForm',
    'ProveedorForm',
    'FacturacionForm',
    'LoginForm'
]

