BEGIN TRANSACTION;
CREATE TABLE categorias_producto (
            id_categoria_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        );
INSERT INTO "categorias_producto" VALUES(1,'TORTAS','Tortas y pasteles tradicionales y de autor',1);
INSERT INTO "categorias_producto" VALUES(2,'POSTRES','Postres individuales y dulces finos',1);
INSERT INTO "categorias_producto" VALUES(3,'PANADERIA','Productos de panadería artesanal y hojaldres',1);
INSERT INTO "categorias_producto" VALUES(4,'BEBIDAS','Bebidas frías y cafetería de especialidad',1);
INSERT INTO "categorias_producto" VALUES(5,'OTROS','Otros productos y complementos',1);
CREATE TABLE categorias_proveedor (
            id_categoria_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
INSERT INTO "categorias_proveedor" VALUES(1,'MATERIA PRIMA','Harina, azúcar, huevos, lácteos y otros insumos');
INSERT INTO "categorias_proveedor" VALUES(2,'EMPAQUES','Cajas, fundas, vasos y empaques ecológicos');
INSERT INTO "categorias_proveedor" VALUES(3,'BEBIDAS','Proveedores de granos de café y bebidas');
INSERT INTO "categorias_proveedor" VALUES(4,'OTROS','Otros proveedores de suministros');
CREATE TABLE clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            id_tipo_cliente INTEGER NOT NULL REFERENCES tipos_cliente(id_tipo_cliente),
            nombre TEXT NOT NULL,
            cedula_ruc TEXT UNIQUE,
            correo TEXT,
            telefono TEXT,
            direccion TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_registro TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
INSERT INTO "clientes" VALUES(1,1,'Consumidor Final','9999999999999','final@dulcedelicia.ec','0999999999','Quito - Ecuador',1,'2026-09-04 23:04:58');
INSERT INTO "clientes" VALUES(2,1,'Ana Torres Mendoza','1718293841','ana.torres@email.com','0991112233','Av. República y Eloy Alfaro N34-12, Quito',1,'2026-09-04 23:04:58');
CREATE TABLE compras (
            id_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_documento TEXT NOT NULL UNIQUE,
            id_proveedor INTEGER NOT NULL REFERENCES proveedores(id_proveedor),
            fecha_compra TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            subtotal REAL NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
            iva REAL NOT NULL DEFAULT 0 CHECK (iva >= 0),
            total REAL NOT NULL DEFAULT 0 CHECK (total >= 0),
            estado TEXT NOT NULL DEFAULT 'RECIBIDA' CHECK (estado IN ('RECIBIDA','ANULADA')),
            observaciones TEXT
        );
CREATE TABLE detalle_compra (
            id_detalle_compra INTEGER PRIMARY KEY AUTOINCREMENT,
            id_compra INTEGER NOT NULL REFERENCES compras(id_compra) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            costo_unitario REAL NOT NULL CHECK (costo_unitario >= 0),
            subtotal REAL NOT NULL
        );
CREATE TABLE detalle_factura (
            id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
            id_factura INTEGER NOT NULL REFERENCES facturas(id_factura) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
            descuento REAL NOT NULL DEFAULT 0 CHECK (descuento >= 0),
            subtotal REAL NOT NULL
        );
CREATE TABLE estados_factura (
            id_estado_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
INSERT INTO "estados_factura" VALUES(1,'EMITIDA','Factura válida y cobrada');
INSERT INTO "estados_factura" VALUES(2,'ANULADA','Factura anulada');
INSERT INTO "estados_factura" VALUES(3,'PENDIENTE','Factura pendiente de pago o confirmación');
CREATE TABLE estados_proveedor (
            id_estado_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
INSERT INTO "estados_proveedor" VALUES(1,'ACTIVO','Proveedor homologado y habilitado');
INSERT INTO "estados_proveedor" VALUES(2,'INACTIVO','Proveedor temporalmente no habilitado');
CREATE TABLE facturas (
            id_factura INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente),
            id_metodo_pago INTEGER NOT NULL REFERENCES metodos_pago(id_metodo_pago),
            id_estado_factura INTEGER NOT NULL REFERENCES estados_factura(id_estado_factura),
            fecha_emision TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            subtotal REAL NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
            iva REAL NOT NULL DEFAULT 0 CHECK (iva >= 0),
            total REAL NOT NULL DEFAULT 0 CHECK (total >= 0),
            observaciones TEXT
        );
INSERT INTO "facturas" VALUES(1,'FAC-001',2,2,1,'2026-08-20',32.17,4.83,37.0,'2x Torta de chocolate para evento familiar.');
INSERT INTO "facturas" VALUES(2,'FAC-002',1,1,1,'2026-08-22',23.48,3.52,27.0,'Cheesecake clásico y café americano.');
INSERT INTO "facturas" VALUES(3,'FAC-004',2,1,1,'2026-09-04',52.0,7.8,59.8,'Venta de postres artesanales.');
CREATE TABLE metodos_pago (
            id_metodo_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        );
INSERT INTO "metodos_pago" VALUES(1,'EFECTIVO',1);
INSERT INTO "metodos_pago" VALUES(2,'TRANSFERENCIA',1);
INSERT INTO "metodos_pago" VALUES(3,'TARJETA',1);
INSERT INTO "metodos_pago" VALUES(4,'DEPOSITO',1);
CREATE TABLE movimientos_inventario (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            id_tipo_movimiento INTEGER NOT NULL REFERENCES tipos_movimiento_inventario(id_tipo_movimiento),
            cantidad REAL NOT NULL CHECK (cantidad > 0),
            stock_anterior REAL NOT NULL CHECK (stock_anterior >= 0),
            stock_nuevo REAL NOT NULL CHECK (stock_nuevo >= 0),
            fecha_movimiento TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            referencia TEXT,
            observaciones TEXT
        );
CREATE TABLE productos (
            id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria_producto INTEGER NOT NULL REFERENCES categorias_producto(id_categoria_producto),
            id_unidad INTEGER NOT NULL REFERENCES unidades_medida(id_unidad),
            codigo TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio_venta REAL NOT NULL CHECK (precio_venta >= 0),
            costo_referencial REAL NOT NULL DEFAULT 0 CHECK (costo_referencial >= 0),
            stock_actual REAL NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
            stock_minimo REAL NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
            imagen TEXT DEFAULT 'img/CHEESCAKE.png',
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_registro TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
INSERT INTO "productos" VALUES(1,1,1,'TOR-001','Torta de chocolate fino','Torta de chocolate decorada con cacao fino de aroma y ganache artesanal.',18.0,10.0,10.0,3.0,'img/MOUSSE.png',1,'2026-09-04 23:04:58');
INSERT INTO "productos" VALUES(2,1,1,'TOR-002','Torta clásica de vainilla','Torta esponjosa de vainilla rellena con crema diplomática y fresas.',16.0,9.0,8.0,3.0,'img/TARTADEFRUTA.png',1,'2026-09-04 23:04:58');
INSERT INTO "productos" VALUES(3,2,4,'POS-001','Cheesecake clásico de frutos rojos','Porción cremosa de cheesecake horneado estilo New York con coulis artesanal.',3.5,1.8,20.0,5.0,'img/CHEESCAKE.png',1,'2026-09-04 23:04:58');
INSERT INTO "productos" VALUES(4,2,1,'POS-002','Cupcake artesanal decorado','Cupcake suave de autor decorado con crema chantilly y perlas comestibles.',2.0,0.9,25.0,8.0,'img/DULCEDELICIA.png',1,'2026-09-04 23:04:58');
INSERT INTO "productos" VALUES(5,3,1,'PAN-001','Croissant francés de mantequilla','Croissant hojaldrado con mantequilla pura importada de masa madre.',1.5,0.7,30.0,10.0,'img/CHEESCAKE.png',1,'2026-09-04 23:04:58');
INSERT INTO "productos" VALUES(6,4,1,'BEB-001','Café americano de especialidad','Café arábigo lojano de especialidad tostado artesanalmente.',1.5,0.5,50.0,10.0,'img/DULCEDELICIA.png',1,'2026-09-04 23:04:58');
CREATE TABLE proveedores (
            id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
            id_categoria_proveedor INTEGER REFERENCES categorias_proveedor(id_categoria_proveedor),
            id_estado_proveedor INTEGER NOT NULL REFERENCES estados_proveedor(id_estado_proveedor),
            razon_social TEXT NOT NULL,
            ruc TEXT UNIQUE,
            contacto TEXT,
            telefono TEXT,
            correo TEXT,
            direccion TEXT,
            fecha_registro TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
INSERT INTO "proveedores" VALUES(1,1,1,'Lácteos Andinos Cía. Ltda.','1791234567001','Ing. María León','0224588990','ventas@lacteosandinos.com','Parque Industrial Machachi, Pichincha','2026-09-04 23:04:58');
INSERT INTO "proveedores" VALUES(2,1,1,'Frutas del Valle Ecuador','1792345678001','Lic. Carlos Ruiz','0987654321','pedidos@frutasdelvalle.ec','Valle de los Chillos, Sangolquí','2026-09-04 23:04:58');
CREATE TABLE tipos_cliente (
            id_tipo_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT
        );
INSERT INTO "tipos_cliente" VALUES(1,'PERSONA NATURAL','Cliente consumidor final o persona natural');
INSERT INTO "tipos_cliente" VALUES(2,'EMPRESA','Cliente empresarial corporativo');
CREATE TABLE tipos_movimiento_inventario (
            id_tipo_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            naturaleza TEXT NOT NULL CHECK (naturaleza IN ('E','S')),
            descripcion TEXT
        );
INSERT INTO "tipos_movimiento_inventario" VALUES(1,'COMPRA','E','Ingreso por compra a proveedor');
INSERT INTO "tipos_movimiento_inventario" VALUES(2,'VENTA','S','Salida por venta a cliente');
INSERT INTO "tipos_movimiento_inventario" VALUES(3,'AJUSTE ENTRADA','E','Ajuste positivo de inventario');
INSERT INTO "tipos_movimiento_inventario" VALUES(4,'AJUSTE SALIDA','S','Ajuste negativo de inventario');
CREATE TABLE unidades_medida (
            id_unidad INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            abreviatura TEXT NOT NULL UNIQUE
        );
INSERT INTO "unidades_medida" VALUES(1,'UNIDAD','UND');
INSERT INTO "unidades_medida" VALUES(2,'KILOGRAMO','KG');
INSERT INTO "unidades_medida" VALUES(3,'LITRO','L');
INSERT INTO "unidades_medida" VALUES(4,'PORCION','POR');
CREATE VIEW vw_productos_stock_bajo AS
        SELECT
            p.id_producto,
            p.codigo,
            p.nombre,
            cp.nombre AS categoria,
            p.stock_actual,
            p.stock_minimo,
            u.abreviatura AS unidad
        FROM productos p
        JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
        JOIN unidades_medida u ON u.id_unidad = p.id_unidad
        WHERE p.activo = 1
          AND p.stock_actual <= p.stock_minimo;
CREATE VIEW vw_facturas_detalladas AS
        SELECT
            f.id_factura,
            f.numero,
            f.fecha_emision,
            c.nombre AS cliente,
            c.cedula_ruc,
            mp.nombre AS metodo_pago,
            ef.nombre AS estado,
            f.subtotal,
            f.iva,
            f.total,
            f.observaciones
        FROM facturas f
        JOIN clientes c ON c.id_cliente = f.id_cliente
        JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
        JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura;
CREATE VIEW vw_ventas_por_producto AS
        SELECT
            p.id_producto,
            p.codigo,
            p.nombre,
            cp.nombre AS categoria,
            COALESCE(SUM(df.cantidad), 0) AS unidades_vendidas,
            COALESCE(SUM(df.subtotal), 0) AS ventas
        FROM productos p
        JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
        LEFT JOIN detalle_factura df ON df.id_producto = p.id_producto
        LEFT JOIN facturas f ON f.id_factura = df.id_factura
        LEFT JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura AND ef.nombre = 'EMITIDA'
        GROUP BY p.id_producto, p.codigo, p.nombre, cp.nombre;
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('tipos_cliente',2);
INSERT INTO "sqlite_sequence" VALUES('categorias_producto',5);
INSERT INTO "sqlite_sequence" VALUES('unidades_medida',4);
INSERT INTO "sqlite_sequence" VALUES('categorias_proveedor',4);
INSERT INTO "sqlite_sequence" VALUES('estados_proveedor',2);
INSERT INTO "sqlite_sequence" VALUES('estados_factura',3);
INSERT INTO "sqlite_sequence" VALUES('metodos_pago',4);
INSERT INTO "sqlite_sequence" VALUES('tipos_movimiento_inventario',4);
INSERT INTO "sqlite_sequence" VALUES('productos',7);
INSERT INTO "sqlite_sequence" VALUES('clientes',2);
INSERT INTO "sqlite_sequence" VALUES('proveedores',2);
INSERT INTO "sqlite_sequence" VALUES('facturas',3);
COMMIT;
