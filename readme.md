#  Explicación de la Base de Datos

La base de datos `dulce_delicia.db` fue diseñada en **SQLite** para gestionar toda la información del sistema de la pastelería Dulce Delicia.  
Su estructura sigue el modelo **Entidad–Relación (ERD)**, garantizando integridad, organización y facilidad de mantenimiento.

**Objetivo**  
Permitir el manejo completo de clientes, proveedores, productos, facturación, compras e inventario, todo conectado mediante relaciones lógicas y llaves foráneas.

---

##  Módulos de la Base de Datos

| Módulo               | Tablas principales                                                                 | Descripción                                                                 |
|-----------------------|------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| **Catálogos**         | categorias_producto, categorias_proveedor, unidades_medida, tipos_cliente, tipos_movimiento_inventario, metodos_pago, estados_factura, estados_proveedor | Definen listas maestras y valores fijos para clasificar datos.              |
| **Clientes y Proveedores** | clientes, proveedores                                                        | Guardan información de contacto y estado.                                   |
| **Productos e Inventario** | productos, movimientos_inventario                                             | Controlan stock, precios y movimientos de entrada/salida.                   |
| **Facturación y Ventas**   | facturas, detalle_factura                                                     | Manejan ventas, totales y detalle de productos vendidos.                    |
| **Compras**           | compras, detalle_compra                                                           | Registran adquisiciones a proveedores y actualizan inventario.              |
| **Reportes (Vistas)** | vw_facturas_detalladas, vw_productos_stock_bajo, vw_ventas_por_producto            | Generan reportes automáticos y consultas rápidas.                           |

---

##  Relaciones principales

| Relación                                   | Explicación                                                                 |
|--------------------------------------------|-----------------------------------------------------------------------------|
| Clientes → Facturas → Detalle_Factura → Productos | Un cliente puede tener varias facturas, cada factura varios productos.      |
| Proveedores → Compras → Detalle_Compra → Productos | Un proveedor puede abastecer múltiples compras y productos asociados.       |
| Productos ↔ Movimientos_Inventario         | Cada producto registra entradas y salidas de stock en inventario.           |
| Facturas ↔ Métodos de Pago / Estados       | Cada factura está vinculada a un método de pago y un estado específico.     |
| Proveedores ↔ Categorías / Estados         | Los proveedores se clasifican por categoría y estado de habilitación.       |

---
##  Diagrama 

<img width="896" height="1200" alt="Gemini_Generated_Image_nc89xbnc89xbnc89" src="https://github.com/user-attachments/assets/d9f0b0e3-60d1-45d7-864c-7fa76c74bba3" />

El diagrama muestra cómo se relacionan las entidades principales: **Clientes, Facturas, Detalle_Factura, Productos, Proveedores, Compras, Detalle_Compra y Movimientos de Inventario**. Cada relación está definida con llaves foráneas y cardinalidades 1:N o N:1 según corresponda.

---

##  Explicación tabla por tabla

**clientes**  
Contiene la información de los clientes.  
- `id_cliente`: clave primaria.  
- `id_tipo_cliente`: llave foránea que clasifica si es persona natural o empresa.  
- `nombre`, `cedula_ruc`, `correo`, `telefono`, `direccion`: datos de identificación y contacto.  
- `activo`: indica si el cliente está habilitado.  
- `fecha_registro`: guarda la fecha de creación automática.

**proveedores**  
Almacena datos de los proveedores.  
- `id_proveedor`: clave primaria.  
- `id_categoria_proveedor`, `id_estado_proveedor`: llaves foráneas para clasificar y controlar estado.  
- `razon_social`, `ruc`, `contacto`, `telefono`, `correo`, `direccion`: información de identificación y contacto.  
- `fecha_registro`: fecha de alta en el sistema.

**productos**  
Define el catálogo de productos.  
- `id_producto`: clave primaria.  
- `id_categoria_producto`, `id_unidad`: llaves foráneas para clasificación y unidad de medida.  
- `codigo`: identificador único del producto.  
- `nombre`, `descripcion`: información básica.  
- `precio_venta`, `costo_referencial`: valores económicos.  
- `stock_actual`, `stock_minimo`: control de inventario.  
- `imagen`: ruta de imagen asociada.  
- `activo`: estado del producto.  
- `fecha_registro`: fecha de creación.

**facturas**  
Registra las ventas.  
- `id_factura`: clave primaria.  
- `numero`: número único de factura.  
- `id_cliente`, `id_metodo_pago`, `id_estado_factura`: llaves foráneas que vinculan cliente, método de pago y estado.  
- `fecha_emision`: fecha de la factura.  
- `subtotal`, `iva`, `total`: valores económicos.  
- `observaciones`: notas adicionales.

**detalle_factura**  
Relaciona facturas con productos.  
- `id_detalle`: clave primaria.  
- `id_factura`, `id_producto`: llaves foráneas.  
- `cantidad`, `precio_unitario`, `descuento`, `subtotal`: detalle de cada línea de producto.

**compras**  
Registra adquisiciones a proveedores.  
- `id_compra`: clave primaria.  
- `numero_documento`: número único de compra.  
- `id_proveedor`: llave foránea.  
- `fecha_compra`: fecha de la compra.  
- `subtotal`, `iva`, `total`: valores económicos.  
- `estado`: estado de la compra (recibida o anulada).  
- `observaciones`: notas adicionales.

**detalle_compra**  
Relaciona compras con productos.  
- `id_detalle_compra`: clave primaria.  
- `id_compra`, `id_producto`: llaves foráneas.  
- `cantidad`, `costo_unitario`, `subtotal`: detalle de cada producto adquirido.

**movimientos_inventario**  
Controla entradas y salidas de stock.  
- `id_movimiento`: clave primaria.  
- `id_producto`, `id_tipo_movimiento`: llaves foráneas.  
- `cantidad`: unidades movidas.  
- `stock_anterior`, `stock_nuevo`: control de inventario.  
- `fecha_movimiento`: fecha del registro.  
- `referencia`, `observaciones`: información adicional.

**catálogos auxiliares**  
Incluyen tablas de referencia:  
- `categorias_producto`, `categorias_proveedor`: clasificación de productos y proveedores.  
- `tipos_cliente`: diferencia entre persona natural y empresa.  
- `tipos_movimiento_inventario`: define naturaleza de movimientos (entrada/salida).  
- `unidades_medida`: define UND, KG, L, POR.  
- `metodos_pago`: efectivo, transferencia, tarjeta, depósito.  
- `estados_factura`, `estados_proveedor`: controlan estados de facturas y proveedores.

**vistas**  
Consultas predefinidas para reportes:  
- `vw_facturas_detalladas`: muestra facturas con cliente, método de pago y estado.  
- `vw_productos_stock_bajo`: alerta productos con stock menor al mínimo.  
- `vw_ventas_por_producto`: resume ventas por producto.

---

# ¿Cómo recrear la base?

Para crear la base desde cero:

```bash
sqlite3 data/dulce_delicia.db < dulce_delicia.sql

