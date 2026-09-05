# 🍰 Dulce Delicia - Sistema de Gestión de Pastelería Artesanal

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.1.3-black?logo=flask)
![Flask-WTF](https://img.shields.io/badge/Flask--WTF-1.3.0-orange)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.3-purple?logo=bootstrap)
![UEA](https://img.shields.io/badge/Universidad-Estatal%20Amaz%C3%B3nica-green)

> **Proyecto Integrador Unidad 3 - Avance 11/16: Validación de Formularios con Flask-WTF y WTForms**  
> **Asignatura:** Desarrollo de Aplicaciones Web  
> **Estudiante:** Henrry Ivan Espinosa Guevara  
> **Universidad Estatal Amazónica (UEA)** — 2026  

---

## 📌 Descripción del Proyecto

**Dulce Delicia** es una aplicación web integral desarrollada con **Flask** para la gestión operativa, comercial y administrativa de una pastelería y repostería fina artesanal.

En esta **Semana 11 (Avance 11/16)**, el sistema incorpora el manejo avanzado de **formularios web del lado del servidor** mediante **Flask-WTF** y **WTForms**, aplicando reglas de validación estrictas, protección contra ataques **CSRF**, mensajes de retroalimentación dinámicos (*Flash messages*) y un diseño visual gourmet, cálido y elegante orientado al nicho gastronómico.

---

## 📁 Estructura del Proyecto

```text
Dulce-Delicia/
│
├── app.py                         # Configuración SECRET_KEY, rutas GET/POST, validación y persistencia
├── requirements.txt               # Dependencias del proyecto
├── README.md                      # Documentación del repositorio
├── GUIA_RAPIDA.md                 # Guía rápida de uso y referencia
│
├── forms/                         # Clases de formularios WTForms organizadas por módulos
│   ├── __init__.py                # Exportación centralizada
│   ├── producto_form.py           # Clase ProductoForm(FlaskForm)
│   ├── cliente_form.py            # Clase ClienteForm(FlaskForm)
│   ├── proveedor_form.py          # Clase ProveedorForm(FlaskForm)
│   └── facturacion_form.py        # Clase FacturacionForm(FlaskForm)
│
├── templates/                     # Plantillas Jinja2 con herencia y componentes
│   ├── base.html                  # Plantilla base con Bootstrap 5, FontAwesome y alertas Flash
│   ├── index.html                 # Inicio con métricas dinámicas y catálogo destacado
│   │
│   ├── productos.html             # Listado de productos con stock y precios
│   ├── formulario_producto.html   # Formulario WTForms para creación/edición de productos
│   │
│   ├── clientes.html              # Directorio de clientes registrados
│   ├── formulario_cliente.html    # Formulario WTForms para clientes (cédula, email, teléfono)
│   │
│   ├── proveedores.html           # Red de proveedores comerciales e insumos
│   ├── formulario_proveedor.html  # Formulario WTForms para proveedores (RUC, categorías)
│   │
│   ├── facturacion.html           # Registro de facturas y ventas emitidas
│   ├── formulario_facturacion.html# Formulario WTForms para facturación (subtotal, IVA 15%, total)
│   │
│   └── components/
│       ├── navbar.html            # Barra de navegación con accesos rápidos para registrar
│       └── footer.html            # Pie de página institucional y créditos
│
└── static/
    ├── css/
    │   ├── style.css              # Hoja de estilos con paleta gourmet artesanal
    │   └── estilo.css             # Compatibilidad
    ├── js/
    │   └── script.js              # Cálculo automático de IVA/Total y efectos interactivos
    └── img/                       # Recursos visuales y postres del catálogo
```

---

## 🧩 Módulos y Formularios Implementados

| Módulo | Formulario | Validadores Principales | Reutilización |
| :--- | :--- | :--- | :--- |
| **Productos** | `ProductoForm` | `DataRequired`, `Length(3, 100)`, `NumberRange(min=0.50)` | Registro y Edición |
| **Clientes** | `ClienteForm` | `DataRequired`, `Length`, `Email`, `Regexp` (Cédula 10 dígitos / RUC) | Registro y Edición |
| **Proveedores** | `ProveedorForm` | `DataRequired`, `Length`, `Email`, `Regexp` (RUC 13 dígitos numéricos) | Registro y Edición |
| **Facturación** | `FacturacionForm` | `DataRequired`, `NumberRange`, `Regexp`, cálculo dinámico de totales | Emisión y Edición |

---

## 🎨 Paleta de Colores y Diseño Visual

La interfaz fue diseñada con una estética **cálida, artesanal y profesional**:

* **Moka Espresso (`#2A1A13` / `#3D261C`)**: Navegación, títulos y textos de contraste.
* **Caramelo & Terracota (`#B85D3B` / `#9E4B2C`)**: Botones de acción, acentos y llamadas a la acción.
* **Crema de Vainilla (`#FAF7F2` / `#F3ECE2`)**: Fondos limpios y agradables a la vista.
* **Verde Salvia (`#206E43`) & Ámbar (`#A15C07`)**: Badges de stock, facturas pagadas y estados activos.

---

## 🚀 Instalación y Ejecución Local

### 1. Clonar el repositorio
```bash
git clone https://github.com/henrryuea/Dulce-Delicia.git
cd Dulce-Delicia
```

### 2. Activar el Entorno Virtual
* **En Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
* **En Windows (CMD):**
  ```cmd
  venv\Scripts\activate.bat
  ```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación
```bash
python app.py
```

### 5. Abrir en el navegador
Ingresar a: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔒 Seguridad y Buenas Prácticas

1. **Protección CSRF**: Toda petición POST de formulario valida el token CSRF generado mediante `{{ form.hidden_tag() }}`.
2. **Validación del lado del Servidor**: Se utiliza `form.validate_on_submit()` para garantizar la integridad de los datos antes de procesarlos.
3. **Mensajes de Error Contextuales**: Errores renderizados directamente debajo de cada campo (`.invalid-feedback`).
4. **Preparación para Persistencia**: Estructura modular diseñada para conectar con MySQL o PostgreSQL en las semanas 12-16 sin reestructurar las vistas.