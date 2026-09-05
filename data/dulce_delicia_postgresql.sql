-- ============================================================
-- BASE DE DATOS: DULCE DELICIA
-- Gestor: PostgreSQL
-- Proyecto: Sistema de ventas, compras, inventario y clientes
-- Modelo Relacional Normalizado (Tercera Forma Normal - 3FN)
-- Asignatura: Desarrollo de Aplicaciones Web - UEA
-- ============================================================

DROP SCHEMA IF EXISTS dulce_delicia CASCADE;
CREATE SCHEMA dulce_delicia;
SET search_path TO dulce_delicia, public;

-- ============================================================
-- 1. CATÁLOGOS BASE
-- ============================================================

CREATE TABLE tipos_cliente (
    id_tipo_cliente SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(150)
);

CREATE TABLE categorias_producto (
    id_categoria_producto SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(60) NOT NULL UNIQUE,
    descripcion VARCHAR(200),
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE unidades_medida (
    id_unidad SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    abreviatura VARCHAR(10) NOT NULL UNIQUE
);

CREATE TABLE categorias_proveedor (
    id_categoria_proveedor SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(60) NOT NULL UNIQUE,
    descripcion VARCHAR(200)
);

CREATE TABLE estados_proveedor (
    id_estado_proveedor SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(150)
);

CREATE TABLE estados_factura (
    id_estado_factura SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(150)
);

CREATE TABLE metodos_pago (
    id_metodo_pago SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(40) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE tipos_movimiento_inventario (
    id_tipo_movimiento SMALLSERIAL PRIMARY KEY,
    nombre VARCHAR(40) NOT NULL UNIQUE,
    naturaleza CHAR(1) NOT NULL CHECK (naturaleza IN ('E','S')),
    descripcion VARCHAR(150)
);

-- ============================================================
-- 2. CLIENTES
-- ============================================================

CREATE TABLE clientes (
    id_cliente BIGSERIAL PRIMARY KEY,
    id_tipo_cliente SMALLINT NOT NULL REFERENCES tipos_cliente(id_tipo_cliente),
    nombre VARCHAR(120) NOT NULL,
    cedula_ruc VARCHAR(20) UNIQUE,
    correo VARCHAR(120),
    telefono VARCHAR(20),
    direccion VARCHAR(200),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_cliente_identificacion CHECK (length(trim(nombre)) >= 2),
    CONSTRAINT ck_cliente_correo CHECK (
        correo IS NULL OR correo ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'
    )
);

-- ============================================================
-- 3. PROVEEDORES
-- ============================================================

CREATE TABLE proveedores (
    id_proveedor BIGSERIAL PRIMARY KEY,
    id_categoria_proveedor SMALLINT REFERENCES categorias_proveedor(id_categoria_proveedor),
    id_estado_proveedor SMALLINT NOT NULL REFERENCES estados_proveedor(id_estado_proveedor),
    razon_social VARCHAR(150) NOT NULL,
    ruc VARCHAR(20) UNIQUE,
    contacto VARCHAR(120),
    telefono VARCHAR(20),
    correo VARCHAR(120),
    direccion VARCHAR(200),
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_proveedor_nombre CHECK (length(trim(razon_social)) >= 2),
    CONSTRAINT ck_proveedor_correo CHECK (
        correo IS NULL OR correo ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'
    )
);

-- ============================================================
-- 4. PRODUCTOS
-- ============================================================

CREATE TABLE productos (
    id_producto BIGSERIAL PRIMARY KEY,
    id_categoria_producto SMALLINT NOT NULL
        REFERENCES categorias_producto(id_categoria_producto),
    id_unidad SMALLINT NOT NULL REFERENCES unidades_medida(id_unidad),
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(250),
    precio_venta NUMERIC(12,2) NOT NULL CHECK (precio_venta >= 0),
    costo_referencial NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (costo_referencial >= 0),
    stock_actual NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_minimo NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    imagen VARCHAR(100) DEFAULT 'img/CHEESCAKE.png',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 5. FACTURACIÓN / VENTAS
-- ============================================================

CREATE TABLE facturas (
    id_factura BIGSERIAL PRIMARY KEY,
    numero VARCHAR(30) NOT NULL UNIQUE,
    id_cliente BIGINT NOT NULL REFERENCES clientes(id_cliente),
    id_metodo_pago SMALLINT NOT NULL REFERENCES metodos_pago(id_metodo_pago),
    id_estado_factura SMALLINT NOT NULL REFERENCES estados_factura(id_estado_factura),
    fecha_emision TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    iva NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (iva >= 0),
    total NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    observaciones VARCHAR(300),
    CONSTRAINT ck_factura_total CHECK (total = subtotal + iva)
);

CREATE TABLE detalle_factura (
    id_detalle BIGSERIAL PRIMARY KEY,
    id_factura BIGINT NOT NULL REFERENCES facturas(id_factura) ON DELETE CASCADE,
    id_producto BIGINT NOT NULL REFERENCES productos(id_producto),
    cantidad NUMERIC(12,3) NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(12,2) NOT NULL CHECK (precio_unitario >= 0),
    descuento NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    subtotal NUMERIC(12,2) GENERATED ALWAYS AS
        (ROUND((cantidad * precio_unitario) - descuento, 2)) STORED,
    CONSTRAINT ck_detalle_descuento CHECK (descuento <= cantidad * precio_unitario)
);

-- ============================================================
-- 6. COMPRAS A PROVEEDORES
-- ============================================================

CREATE TABLE compras (
    id_compra BIGSERIAL PRIMARY KEY,
    numero_documento VARCHAR(40) NOT NULL UNIQUE,
    id_proveedor BIGINT NOT NULL REFERENCES proveedores(id_proveedor),
    fecha_compra TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    iva NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (iva >= 0),
    total NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    estado VARCHAR(20) NOT NULL DEFAULT 'RECIBIDA'
        CHECK (estado IN ('RECIBIDA','ANULADA')),
    observaciones VARCHAR(300),
    CONSTRAINT ck_compra_total CHECK (total = subtotal + iva)
);

CREATE TABLE detalle_compra (
    id_detalle_compra BIGSERIAL PRIMARY KEY,
    id_compra BIGINT NOT NULL REFERENCES compras(id_compra) ON DELETE CASCADE,
    id_producto BIGINT NOT NULL REFERENCES productos(id_producto),
    cantidad NUMERIC(12,3) NOT NULL CHECK (cantidad > 0),
    costo_unitario NUMERIC(12,2) NOT NULL CHECK (costo_unitario >= 0),
    subtotal NUMERIC(12,2) GENERATED ALWAYS AS
        (ROUND(cantidad * costo_unitario, 2)) STORED
);

-- ============================================================
-- 7. INVENTARIO / TRAZABILIDAD
-- ============================================================

CREATE TABLE movimientos_inventario (
    id_movimiento BIGSERIAL PRIMARY KEY,
    id_producto BIGINT NOT NULL REFERENCES productos(id_producto),
    id_tipo_movimiento SMALLINT NOT NULL REFERENCES tipos_movimiento_inventario(id_tipo_movimiento),
    cantidad NUMERIC(12,3) NOT NULL CHECK (cantidad > 0),
    stock_anterior NUMERIC(12,3) NOT NULL CHECK (stock_anterior >= 0),
    stock_nuevo NUMERIC(12,3) NOT NULL CHECK (stock_nuevo >= 0),
    fecha_movimiento TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    referencia VARCHAR(50),
    observaciones VARCHAR(250)
);

-- ============================================================
-- 8. FUNCIONES
-- ============================================================

CREATE OR REPLACE FUNCTION fn_recalcular_factura(p_id_factura BIGINT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_subtotal NUMERIC(12,2);
    v_iva NUMERIC(12,2);
BEGIN
    SELECT COALESCE(SUM(subtotal),0)
    INTO v_subtotal
    FROM detalle_factura
    WHERE id_factura = p_id_factura;

    -- IVA configurable para Ecuador (15%)
    v_iva := ROUND(v_subtotal * 0.15, 2);

    UPDATE facturas
    SET subtotal = v_subtotal,
        iva = v_iva,
        total = v_subtotal + v_iva
    WHERE id_factura = p_id_factura;
END;
$$;

CREATE OR REPLACE FUNCTION fn_actualizar_stock(
    p_id_producto BIGINT,
    p_tipo_movimiento SMALLINT,
    p_cantidad NUMERIC,
    p_referencia VARCHAR
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_stock NUMERIC(12,3);
    v_naturaleza CHAR(1);
    v_nuevo_stock NUMERIC(12,3);
BEGIN
    SELECT stock_actual
    INTO v_stock
    FROM productos
    WHERE id_producto = p_id_producto
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Producto % no existe', p_id_producto;
    END IF;

    SELECT naturaleza
    INTO v_naturaleza
    FROM tipos_movimiento_inventario
    WHERE id_tipo_movimiento = p_tipo_movimiento;

    IF v_naturaleza = 'E' THEN
        v_nuevo_stock := v_stock + p_cantidad;
    ELSE
        v_nuevo_stock := v_stock - p_cantidad;
    END IF;

    IF v_nuevo_stock < 0 THEN
        RAISE EXCEPTION 'Stock insuficiente para el producto %. Stock disponible: %, cantidad solicitada: %',
            p_id_producto, v_stock, p_cantidad;
    END IF;

    UPDATE productos
    SET stock_actual = v_nuevo_stock
    WHERE id_producto = p_id_producto;

    INSERT INTO movimientos_inventario
        (id_producto, id_tipo_movimiento, cantidad, stock_anterior, stock_nuevo, referencia)
    VALUES
        (p_id_producto, p_tipo_movimiento, p_cantidad, v_stock, v_nuevo_stock, p_referencia);
END;
$$;

-- ============================================================
-- 9. TRIGGERS
-- ============================================================

CREATE OR REPLACE FUNCTION trg_detalle_factura_stock()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_estado VARCHAR(30);
BEGIN
    SELECT ef.nombre
    INTO v_estado
    FROM facturas f
    JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
    WHERE f.id_factura = NEW.id_factura;

    IF v_estado = 'EMITIDA' THEN
        PERFORM fn_actualizar_stock(
            NEW.id_producto,
            (SELECT id_tipo_movimiento FROM tipos_movimiento_inventario WHERE nombre = 'VENTA'),
            NEW.cantidad,
            NEW.id_factura::VARCHAR
        );
    END IF;

    PERFORM fn_recalcular_factura(NEW.id_factura);
    RETURN NEW;
END;
$$;

CREATE TRIGGER after_detalle_factura
AFTER INSERT ON detalle_factura
FOR EACH ROW
EXECUTE FUNCTION trg_detalle_factura_stock();

CREATE OR REPLACE FUNCTION trg_detalle_compra_stock()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM fn_actualizar_stock(
        NEW.id_producto,
        (SELECT id_tipo_movimiento FROM tipos_movimiento_inventario WHERE nombre = 'COMPRA'),
        NEW.cantidad,
        NEW.id_compra::VARCHAR
    );

    UPDATE productos
    SET costo_referencial = NEW.costo_unitario
    WHERE id_producto = NEW.id_producto;

    UPDATE compras c
    SET subtotal = x.subtotal,
        iva = ROUND(x.subtotal * 0.15, 2),
        total = x.subtotal + ROUND(x.subtotal * 0.15, 2)
    FROM (
        SELECT id_compra, COALESCE(SUM(subtotal),0) AS subtotal
        FROM detalle_compra
        WHERE id_compra = NEW.id_compra
        GROUP BY id_compra
    ) x
    WHERE c.id_compra = x.id_compra;

    RETURN NEW;
END;
$$;

CREATE TRIGGER after_detalle_compra
AFTER INSERT ON detalle_compra
FOR EACH ROW
EXECUTE FUNCTION trg_detalle_compra_stock();

-- ============================================================
-- 10. VISTAS
-- ============================================================

CREATE OR REPLACE VIEW vw_productos_stock_bajo AS
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
WHERE p.activo = TRUE
  AND p.stock_actual <= p.stock_minimo;

CREATE OR REPLACE VIEW vw_facturas_detalladas AS
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
    f.total
FROM facturas f
JOIN clientes c ON c.id_cliente = f.id_cliente
JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura;

CREATE OR REPLACE VIEW vw_ventas_por_producto AS
SELECT
    p.id_producto,
    p.codigo,
    p.nombre,
    cp.nombre AS categoria,
    COALESCE(SUM(df.cantidad),0) AS unidades_vendidas,
    COALESCE(SUM(df.subtotal),0) AS ventas
FROM productos p
JOIN categorias_producto cp
    ON cp.id_categoria_producto = p.id_categoria_producto
LEFT JOIN detalle_factura df
    ON df.id_producto = p.id_producto
LEFT JOIN facturas f
    ON f.id_factura = df.id_factura
LEFT JOIN estados_factura ef
    ON ef.id_estado_factura = f.id_estado_factura
   AND ef.nombre = 'EMITIDA'
GROUP BY p.id_producto, p.codigo, p.nombre, cp.nombre;

-- ============================================================
-- 11. ÍNDICES
-- ============================================================

CREATE INDEX idx_clientes_nombre ON clientes(nombre);
CREATE INDEX idx_productos_categoria ON productos(id_categoria_producto);
CREATE INDEX idx_productos_nombre ON productos(nombre);
CREATE INDEX idx_proveedores_categoria ON proveedores(id_categoria_proveedor);
CREATE INDEX idx_facturas_cliente ON facturas(id_cliente);
CREATE INDEX idx_facturas_fecha ON facturas(fecha_emision);
CREATE INDEX idx_detalle_factura_factura ON detalle_factura(id_factura);
CREATE INDEX idx_detalle_factura_producto ON detalle_factura(id_producto);
CREATE INDEX idx_compras_proveedor ON compras(id_proveedor);
CREATE INDEX idx_compras_fecha ON compras(fecha_compra);
CREATE INDEX idx_detalle_compra_producto ON detalle_compra(id_producto);
CREATE INDEX idx_movimientos_producto_fecha
    ON movimientos_inventario(id_producto, fecha_movimiento);

-- ============================================================
-- 12. DATOS INICIALES
-- ============================================================

INSERT INTO tipos_cliente (nombre, descripcion) VALUES
('PERSONA NATURAL', 'Cliente consumidor final o persona natural'),
('EMPRESA', 'Cliente empresarial');

INSERT INTO categorias_producto (nombre, descripcion) VALUES
('TORTAS', 'Tortas y pasteles'),
('POSTRES', 'Postres y dulces'),
('PANADERIA', 'Productos de panadería'),
('BEBIDAS', 'Bebidas frías y calientes'),
('OTROS', 'Otros productos comercializados');

INSERT INTO unidades_medida (nombre, abreviatura) VALUES
('UNIDAD', 'UND'),
('KILOGRAMO', 'KG'),
('LITRO', 'L'),
('PORCION', 'POR');

INSERT INTO categorias_proveedor (nombre, descripcion) VALUES
('MATERIA PRIMA', 'Harina, azúcar, huevos, lácteos y otros insumos'),
('EMPAQUES', 'Cajas, fundas, vasos y empaques'),
('BEBIDAS', 'Proveedores de bebidas'),
('OTROS', 'Otros proveedores');

INSERT INTO estados_proveedor (nombre, descripcion) VALUES
('ACTIVO', 'Proveedor habilitado'),
('INACTIVO', 'Proveedor no habilitado');

INSERT INTO estados_factura (nombre, descripcion) VALUES
('EMITIDA', 'Factura válida y registrada'),
('ANULADA', 'Factura anulada'),
('PENDIENTE', 'Factura pendiente de confirmación');

INSERT INTO metodos_pago (nombre) VALUES
('EFECTIVO'),
('TRANSFERENCIA'),
('TARJETA'),
('DEPOSITO');

INSERT INTO tipos_movimiento_inventario (nombre, naturaleza, descripcion) VALUES
('COMPRA', 'E', 'Ingreso por compra a proveedor'),
('VENTA', 'S', 'Salida por venta'),
('AJUSTE ENTRADA', 'E', 'Ajuste positivo de inventario'),
('AJUSTE SALIDA', 'S', 'Ajuste negativo de inventario');

-- ============================================================
-- 13. PRODUCTOS DE EJEMPLO
-- ============================================================

INSERT INTO productos
(id_categoria_producto, id_unidad, codigo, nombre, descripcion,
 precio_venta, costo_referencial, stock_actual, stock_minimo, imagen)
VALUES
((SELECT id_categoria_producto FROM categorias_producto WHERE nombre='TORTAS'),
 (SELECT id_unidad FROM unidades_medida WHERE nombre='UNIDAD'),
 'TOR-001', 'Torta de chocolate', 'Torta de chocolate decorada con cacao fino de aroma',
 18.00, 10.00, 10, 3, 'img/MOUSSE.png'),

((SELECT id_categoria_producto FROM categorias_producto WHERE nombre='TORTAS'),
 (SELECT id_unidad FROM unidades_medida WHERE nombre='UNIDAD'),
 'TOR-002', 'Torta de vainilla', 'Torta de vainilla decorada tradicional',
 16.00, 9.00, 8, 3, 'img/TARTADEFRUTA.png'),

((SELECT id_categoria_producto FROM categorias_producto WHERE nombre='POSTRES'),
 (SELECT id_unidad FROM unidades_medida WHERE nombre='PORCION'),
 'POS-001', 'Cheesecake clásico', 'Porción de cheesecake artesanal estilo New York con frutos rojos',
 3.50, 1.80, 20, 5, 'img/CHEESCAKE.png'),

((SELECT id_categoria_producto FROM categorias_producto WHERE nombre='POSTRES'),
 (SELECT id_unidad FROM unidades_medida WHERE nombre='UNIDAD'),
 'POS-002', 'Cupcake artesanal', 'Cupcake artesanal decorado con crema de autor',
 2.00, 0.90, 25, 8, 'img/DULCEDELICIA.png'),

((SELECT id_categoria_producto FROM categorias_producto WHERE nombre='PANADERIA'),
 (SELECT id_unidad FROM unidades_medida WHERE nombre='UNIDAD'),
 'PAN-001', 'Croissant de mantequilla', 'Croissant hojaldrado horneado con mantequilla pura',
 1.50, 0.70, 30, 10, 'img/CHEESCAKE.png'),

((SELECT id_categoria_producto FROM categorias_producto WHERE nombre='BEBIDAS'),
 (SELECT id_unidad FROM unidades_medida WHERE nombre='UNIDAD'),
 'BEB-001', 'Café americano de altura', 'Café lojano pasado de especialidad',
 1.50, 0.50, 50, 10, 'img/DULCEDELICIA.png');

-- ============================================================
-- 14. CLIENTES Y PROVEEDORES DE EJEMPLO
-- ============================================================

INSERT INTO clientes
(id_tipo_cliente, nombre, cedula_ruc, correo, telefono, direccion)
VALUES
((SELECT id_tipo_cliente FROM tipos_cliente WHERE nombre='PERSONA NATURAL'),
 'Consumidor Final', '9999999999999', 'final@dulcedelicia.ec', '0999999999', 'Quito - Ecuador'),
((SELECT id_tipo_cliente FROM tipos_cliente WHERE nombre='PERSONA NATURAL'),
 'Ana Torres Mendoza', '1718293841', 'ana.torres@email.com', '0991112233', 'Av. República y Eloy Alfaro, Quito');

INSERT INTO proveedores
(id_categoria_proveedor, id_estado_proveedor, razon_social, ruc, contacto, telefono, correo, direccion)
VALUES
((SELECT id_categoria_proveedor FROM categorias_proveedor WHERE nombre='MATERIA PRIMA'),
 (SELECT id_estado_proveedor FROM estados_proveedor WHERE nombre='ACTIVO'),
 'Lácteos Andinos Cía. Ltda.', '1791234567001', 'Ing. María León',
 '0224588990', 'ventas@lacteosandinos.com', 'Parque Industrial Machachi, Pichincha');

-- ============================================================
-- 15. PROCEDIMIENTO PARA REGISTRAR UNA VENTA
-- ============================================================

CREATE OR REPLACE PROCEDURE sp_registrar_venta(
    p_numero VARCHAR,
    p_id_cliente BIGINT,
    p_id_metodo_pago SMALLINT,
    p_id_producto BIGINT,
    p_cantidad NUMERIC,
    p_observaciones VARCHAR DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_factura BIGINT;
    v_precio NUMERIC(12,2);
    v_estado SMALLINT;
BEGIN
    SELECT precio_venta INTO v_precio
    FROM productos
    WHERE id_producto = p_id_producto
      AND activo = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Producto no encontrado o inactivo';
    END IF;

    SELECT id_estado_factura INTO v_estado
    FROM estados_factura
    WHERE nombre = 'EMITIDA';

    INSERT INTO facturas
        (numero, id_cliente, id_metodo_pago, id_estado_factura, observaciones)
    VALUES
        (p_numero, p_id_cliente, p_id_metodo_pago, v_estado, p_observaciones)
    RETURNING id_factura INTO v_factura;

    INSERT INTO detalle_factura
        (id_factura, id_producto, cantidad, precio_unitario)
    VALUES
        (v_factura, p_id_producto, p_cantidad, v_precio);

    RAISE NOTICE 'Venta registrada. Factura ID: %', v_factura;
END;
$$;
