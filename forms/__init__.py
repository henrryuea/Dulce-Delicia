# ==============================================================================
# PAQUETE FORMS - DULCE DELICIA
# ==============================================================================
from forms.cliente_form import ClienteForm
from forms.producto_form import ProductoForm
from forms.categoria_producto_form import CategoriaProductoForm
from forms.proveedor_form import ProveedorForm
from forms.facturacion_form import FacturacionForm
from forms.login_form import LoginForm
from forms.usuario_form import UsuarioForm
from forms.dos_factores_form import DosFactoresForm

__all__ = [
    'ClienteForm',
    'ProductoForm',
    'CategoriaProductoForm',
    'ProveedorForm',
    'FacturacionForm',
    'LoginForm',
    'UsuarioForm',
    'DosFactoresForm'
]
