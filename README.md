# 🍰 Dulce Delicia - Sistema de Gestión de Pastelería Artesanal

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.1.3-black?logo=flask)
![Flask-WTF](https://img.shields.io/badge/Flask--WTF-1.3.0-orange)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.3-purple?logo=bootstrap)
![UEA](https://img.shields.io/badge/Universidad-Estatal%20Amaz%C3%B3nica-green)

> **Proyecto Integrador Unidad 4 - Avance 15/16: CRUD, PostgreSQL, autenticación e inventario**
> **Asignatura:** Desarrollo de Aplicaciones Web  
> **Estudiante:** Henrry Ivan Espinosa Guevara  
> **Universidad Estatal Amazónica (UEA)** — 2026  

---

## 📌 Descripción del Proyecto

**Dulce Delicia** es una aplicación web integral desarrollada con **Flask** para la gestión operativa, comercial y administrativa de una pastelería y repostería fina artesanal.

En este avance de **Semana 15**, el sistema integra formularios validados con **Flask-WTF**,
operaciones CRUD, autenticación con contraseñas hasheadas, protección **CSRF**,
PostgreSQL para producción e inventario reconciliado con las ventas.

---

## 📁 Estructura del Proyecto

```text
Dulce-Delicia/
│
├── app.py                         # Configuración SECRET_KEY, rutas GET/POST, validación y persistencia
├── database.py                    # Conexión PostgreSQL/SQLite, esquema relacional y catálogos
├── requirements.txt               # Dependencias del proyecto
├── render.yaml                    # Servicio web y PostgreSQL en Render
├── data/postgresql_facturacion.sql# DDL/migración PostgreSQL para pedidos, abonos y facturas
├── README.md                      # Documentación del repositorio
├── GUIA_RAPIDA.md                 # Guía rápida de uso y referencia
│
├── forms/                         # Clases de formularios WTForms organizadas por módulos
│   ├── __init__.py                # Exportación centralizada
│   ├── producto_form.py           # Clase ProductoForm(FlaskForm)
│   ├── cliente_form.py            # Clase ClienteForm(FlaskForm)
│   ├── proveedor_form.py          # Clase ProveedorForm(FlaskForm)
│   ├── facturacion_form.py        # Clase FacturacionForm(FlaskForm)
│   ├── registro_form.py           # Registro de cliente o solicitud de acceso interno
│   └── inventario_form.py         # Formulario para ajustes de stock
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
│   ├── formulario_facturacion.html# Facturación con líneas de productos y control de stock
│   ├── mi_cuenta.html             # Facturas propias y catálogo disponible de cliente
│   ├── registro.html              # Solicitud de cuenta cliente o personal
│   ├── comprobante_pago.html      # Recibo de abono para consulta/impresión
│   └── solicitudes_acceso.html    # Aprobación de cuentas reservada a ADMIN
│   ├── inventario.html            # Existencias, ajustes e historial de movimientos
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
| **Productos** | `ProductoForm` | `DataRequired`, `Length`, `NumberRange`, decimales finitos | Registro y Edición |
| **Clientes** | `ClienteForm` | `DataRequired`, `Length`, `Email`, `Regexp` (Cédula 10 dígitos / RUC) | Registro y Edición |
| **Proveedores** | `ProveedorForm` | `DataRequired`, `Length`, `Email`, `Regexp` (RUC 13 dígitos numéricos) | Registro y Edición |
| **Facturación** | `FacturacionForm` | `DataRequired`, `Length`, `Regexp`; precios y totales recalculados en servidor | Emisión y Edición |

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

### 4. Crear el primer usuario administrativo

En PowerShell configure una clave de sesión privada y cree la cuenta:
```powershell
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
flask --app app crear-admin
```

### 5. Ejecutar la aplicación
```bash
python app.py
```

### 6. Abrir en el navegador
Ingresar a: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔒 Seguridad y Buenas Prácticas

1. **Protección CSRF**: Toda petición POST de formulario valida el token CSRF generado mediante `{{ form.hidden_tag() }}`.
2. **Validación del lado del Servidor**: Se utiliza `form.validate_on_submit()` para garantizar la integridad de los datos antes de procesarlos.
3. **Mensajes de Error Contextuales**: Errores renderizados directamente debajo de cada campo (`.invalid-feedback`).
4. **Autenticación**: No existe contraseña predeterminada de administrador. Los clientes y el personal pueden solicitar una cuenta, pero el administrador debe aprobarla; se guardan hashes seguros y hay bloqueo temporal tras cinco intentos fallidos.
5. **Persistencia**: SQLite se usa en desarrollo local; configure `DATABASE_URL` para utilizar PostgreSQL en producción.

---

## Avance 15/16: CRUD, autenticación, PostgreSQL e inventario

El sistema contiene tablas relacionales para clientes, productos, pedidos, detalles de pedido,
pagos, facturas y detalles de factura, además de los catálogos e historial de inventario. Las
claves primarias y foráneas relacionan los registros; los identificadores de clientes, códigos
de producto, pedidos, comprobantes y facturas tienen restricciones únicas. Los listados usan
`JOIN`, las consultas reciben parámetros y las rutas administrativas exigen autenticación y CSRF.

La venta crea un pedido y reserva el stock dentro de una transacción: si falla la validación,
la base de datos revierte el pedido, el detalle, el movimiento y cualquier abono. El servidor
calcula el subtotal y el IVA del 15 %. Cada abono positivo produce un comprobante; no se admite
pagar más del saldo. Al llegar el pago acumulado al total se cambia automáticamente el estado
a **PAGADO** y se emite una sola factura con sus líneas. Los números se forman usando las claves
primarias autogeneradas y restricciones `UNIQUE`, no conteos de filas. Los importes nuevos usan
`NUMERIC(12,2)` y las cantidades `NUMERIC(12,3)` en PostgreSQL. Una factura emitida es inmutable;
la anulación o devolución requiere un proceso contable separado. La página **Inventario** muestra
existencias, alertas y movimientos auditables sin permitir stock negativo.
Las claves de idempotencia persistidas con índice único evitan duplicar pedidos o abonos si se
reenvía un formulario tras una interrupción o doble clic.

En producción use PostgreSQL mediante `DATABASE_URL`; el esquema crea o migra la columna de
relación de facturas sin borrar el historial existente. SQLite queda disponible para desarrollo
local, no como almacenamiento persistente en un servicio Render.

### Desarrollo local

Sin `DATABASE_URL`, la aplicación usa `data/dulce_delicia.db` (SQLite). Instale dependencias,
cree una clave privada y una cuenta administrativa antes de arrancar:

```powershell
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
flask --app app crear-admin
python app.py
```

No hay contraseña predeterminada: el sistema no puede revelar la contraseña actual porque solo
guarda su hash. `crear-admin` solicita el nombre y una contraseña nueva (12–128 caracteres) sin
mostrarla; ese valor lo define quien instala/despliega la aplicación. Si ya existe la cuenta,
restablézcala con `flask --app app restablecer-admin`, que habilita también el rol ADMIN. Los
usuarios no pueden autoasignarse privilegios: `ADMIN` se crea por CLI/entorno; los usuarios que
soliciten acceso de personal quedan `PENDIENTE` hasta ser aprobados por un administrador.
Las cuentas de cliente también esperan verificación/aprobación; después solo ven sus propias
facturas y productos en existencia, en modo lectura. El catálogo público puede consultarse sin
iniciar sesión.

Los roles internos tienen permisos distintos: `ADMIN` gestiona el catálogo, clientes,
proveedores, facturas y solicitudes de acceso. `STAFF` puede registrar ventas y abonos, atender
ajustes de inventario y consultar productos/clientes; no puede modificar registros maestros,
gestionar proveedores ni aprobar cuentas. La autorización se comprueba en las rutas del servidor.

### Producción y Render

El archivo `render.yaml` define el servicio Flask, Gunicorn y una base PostgreSQL administrada.
Al crear el Blueprint en Render, configure `ADMIN_USERNAME` (3-30 caracteres) y
`ADMIN_PASSWORD` (12–128 caracteres) como variables privadas; Render genera `SECRET_KEY`
y conecta `DATABASE_URL`. Si prefiere no sembrar las credenciales mediante variables de entorno,
cree la cuenta con `flask --app app crear-admin` desde la consola del servicio. La aplicación
crea las tablas y catálogos al arrancar y protege las cookies de sesión con HTTPS en producción.
Defina una contraseña propia segura en `ADMIN_PASSWORD`; no hay un usuario/contraseña demo.
Para recuperar acceso a una cuenta existente use el comando `restablecer-admin` en una consola
segura con acceso al servicio/base de datos.
El esquema PostgreSQL explícito está en [`data/postgresql_facturacion.sql`](./data/postgresql_facturacion.sql);
requiere que las tablas base (`clientes`, `productos`, `metodos_pago`, `facturas` y
`detalle_factura`) ya existan. El arranque de Flask realiza la inicialización idempotente
automáticamente, así que Render no requiere ejecutar ese archivo manualmente.

En el plan gratuito de Render, los servicios web pueden suspenderse y las bases PostgreSQL
gratuitas pueden tener límites de disponibilidad/retención establecidos por Render. Para uso
continuo, seleccione planes de pago y configure copias de seguridad desde Render. No use SQLite
en el disco efímero de un servicio desplegado.

Las imágenes cargadas se guardan en el sistema de archivos local. En Render, use un disco
persistente o almacenamiento de objetos antes de depender de imágenes propias tras reinicios
o despliegues; las imágenes incluidas en `static/img` sí forman parte del código publicado.

### Prueba funcional recomendada

Inicie sesión, consulte Productos/Clientes/Proveedores, registre y edite un producto, y haga una
entrada o ajuste en Inventario. En Facturación, busque un cliente por cédula o regístrelo,
cree un pedido con stock disponible, registre uno o más abonos, abra cada comprobante y confirme
que la factura aparece solo al cancelar el saldo. Verifique que no se acepte una sobreventa o un
sobrepago, que el stock se reserve al crear el pedido y que cierre sesión correctamente.