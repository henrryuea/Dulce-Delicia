"""
Módulo de Formularios para Dulce Delicia
Organización de clases Flask-WTF / WTForms
Avance 15/16 - Proyecto Integrador U4
"""
from .producto_form import ProductoForm
from .cliente_form import ClienteForm
from .proveedor_form import ProveedorForm
from .facturacion_form import AbonoForm, FacturacionForm
from .login_form import LoginForm
from .inventario_form import InventarioForm
from .registro_form import RegistroForm

__all__ = [
    'ProductoForm',
    'ClienteForm',
    'ProveedorForm',
    'FacturacionForm',
    'AbonoForm',
    'LoginForm',
    'InventarioForm',
    'RegistroForm'
]
