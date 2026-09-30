BEGIN;

CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido BIGSERIAL PRIMARY KEY,
    numero TEXT NOT NULL UNIQUE,
    clave_idempotencia TEXT NOT NULL,
    id_cliente BIGINT NOT NULL REFERENCES clientes(id_cliente),
    fecha_pedido TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
    iva NUMERIC(12, 2) NOT NULL CHECK (iva >= 0),
    total NUMERIC(12, 2) NOT NULL CHECK (total > 0),
    monto_pagado NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (monto_pagado >= 0 AND monto_pagado <= total),
    estado TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE', 'PAGADO', 'ANULADO')),
    observaciones TEXT
);

CREATE TABLE IF NOT EXISTS detalle_pedido (
    id_detalle_pedido BIGSERIAL PRIMARY KEY,
    id_pedido BIGINT NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    id_producto BIGINT NOT NULL REFERENCES productos(id_producto),
    codigo_producto TEXT,
    nombre_producto TEXT,
    cantidad NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
    descuento NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0)
);

CREATE TABLE IF NOT EXISTS pagos_pedido (
    id_pago BIGSERIAL PRIMARY KEY,
    id_pedido BIGINT NOT NULL REFERENCES pedidos(id_pedido),
    numero_comprobante TEXT NOT NULL UNIQUE,
    clave_idempotencia TEXT NOT NULL,
    fecha_pago TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP::text,
    monto NUMERIC(12, 2) NOT NULL CHECK (monto > 0),
    id_metodo_pago BIGINT NOT NULL REFERENCES metodos_pago(id_metodo_pago),
    observaciones TEXT
);

ALTER TABLE facturas
    ADD COLUMN IF NOT EXISTS id_pedido BIGINT REFERENCES pedidos(id_pedido);
ALTER TABLE detalle_pedido
    ADD COLUMN IF NOT EXISTS codigo_producto TEXT;
ALTER TABLE detalle_pedido
    ADD COLUMN IF NOT EXISTS nombre_producto TEXT;
ALTER TABLE detalle_factura
    ADD COLUMN IF NOT EXISTS codigo_producto TEXT;
ALTER TABLE detalle_factura
    ADD COLUMN IF NOT EXISTS nombre_producto TEXT;
ALTER TABLE pedidos
    ADD COLUMN IF NOT EXISTS clave_idempotencia TEXT;
ALTER TABLE pagos_pedido
    ADD COLUMN IF NOT EXISTS clave_idempotencia TEXT;
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS correo TEXT,
    ADD COLUMN IF NOT EXISTS nombre TEXT,
    ADD COLUMN IF NOT EXISTS rol TEXT NOT NULL DEFAULT 'ADMIN',
    ADD COLUMN IF NOT EXISTS estado TEXT NOT NULL DEFAULT 'ACTIVO',
    ADD COLUMN IF NOT EXISTS id_cliente BIGINT REFERENCES clientes(id_cliente),
    ADD COLUMN IF NOT EXISTS revisado_por BIGINT REFERENCES usuarios(id_usuario),
    ADD COLUMN IF NOT EXISTS fecha_revision TEXT;
ALTER TABLE usuarios
    ALTER COLUMN rol SET DEFAULT 'CLIENTE',
    ALTER COLUMN estado SET DEFAULT 'PENDIENTE';

DROP VIEW IF EXISTS vw_ventas_por_producto;
DROP VIEW IF EXISTS vw_facturas_detalladas;
DROP VIEW IF EXISTS vw_productos_stock_bajo;

ALTER TABLE productos
    ALTER COLUMN precio_venta TYPE NUMERIC(12, 2) USING ROUND(precio_venta::numeric, 2),
    ALTER COLUMN costo_referencial TYPE NUMERIC(12, 2) USING ROUND(costo_referencial::numeric, 2),
    ALTER COLUMN stock_actual TYPE NUMERIC(12, 3) USING ROUND(stock_actual::numeric, 3),
    ALTER COLUMN stock_minimo TYPE NUMERIC(12, 3) USING ROUND(stock_minimo::numeric, 3);
ALTER TABLE facturas
    ALTER COLUMN subtotal TYPE NUMERIC(12, 2) USING ROUND(subtotal::numeric, 2),
    ALTER COLUMN iva TYPE NUMERIC(12, 2) USING ROUND(iva::numeric, 2),
    ALTER COLUMN total TYPE NUMERIC(12, 2) USING ROUND(total::numeric, 2);
ALTER TABLE detalle_factura
    ALTER COLUMN cantidad TYPE NUMERIC(12, 3) USING ROUND(cantidad::numeric, 3),
    ALTER COLUMN precio_unitario TYPE NUMERIC(12, 2) USING ROUND(precio_unitario::numeric, 2),
    ALTER COLUMN descuento TYPE NUMERIC(12, 2) USING ROUND(descuento::numeric, 2),
    ALTER COLUMN subtotal TYPE NUMERIC(12, 2) USING ROUND(subtotal::numeric, 2);

INSERT INTO tipos_movimiento_inventario (nombre, naturaleza, descripcion)
SELECT 'RESERVA PEDIDO', 'S', 'Stock reservado al crear un pedido pendiente'
WHERE NOT EXISTS (
    SELECT 1 FROM tipos_movimiento_inventario WHERE nombre = 'RESERVA PEDIDO'
);

UPDATE detalle_pedido dp
SET codigo_producto = p.codigo,
    nombre_producto = p.nombre
FROM productos p
WHERE p.id_producto = dp.id_producto
  AND (dp.codigo_producto IS NULL OR dp.nombre_producto IS NULL);

UPDATE detalle_factura df
SET codigo_producto = p.codigo,
    nombre_producto = p.nombre
FROM productos p
WHERE p.id_producto = df.id_producto
  AND (df.codigo_producto IS NULL OR df.nombre_producto IS NULL);

CREATE OR REPLACE VIEW vw_productos_stock_bajo AS
    SELECT p.id_producto, p.codigo, p.nombre, cp.nombre AS categoria,
           p.stock_actual, p.stock_minimo, u.abreviatura AS unidad
    FROM productos p
    JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
    JOIN unidades_medida u ON u.id_unidad = p.id_unidad
    WHERE p.activo = 1 AND p.stock_actual <= p.stock_minimo;

CREATE OR REPLACE VIEW vw_facturas_detalladas AS
    SELECT f.id_factura, f.numero, f.fecha_emision, c.nombre AS cliente,
           c.cedula_ruc, mp.nombre AS metodo_pago, ef.nombre AS estado,
           f.subtotal, f.iva, f.total, f.observaciones
    FROM facturas f
    JOIN clientes c ON c.id_cliente = f.id_cliente
    JOIN metodos_pago mp ON mp.id_metodo_pago = f.id_metodo_pago
    JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura;

CREATE OR REPLACE VIEW vw_ventas_por_producto AS
    SELECT p.id_producto, p.codigo, p.nombre, cp.nombre AS categoria,
           COALESCE(SUM(CASE WHEN ef.nombre = 'EMITIDA' THEN df.cantidad ELSE 0 END), 0) AS unidades_vendidas,
           COALESCE(SUM(CASE WHEN ef.nombre = 'EMITIDA' THEN df.subtotal ELSE 0 END), 0) AS ventas
    FROM productos p
    JOIN categorias_producto cp ON cp.id_categoria_producto = p.id_categoria_producto
    LEFT JOIN detalle_factura df ON df.id_producto = p.id_producto
    LEFT JOIN facturas f ON f.id_factura = df.id_factura
    LEFT JOIN estados_factura ef ON ef.id_estado_factura = f.id_estado_factura
    GROUP BY p.id_producto, p.codigo, p.nombre, cp.nombre;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pedidos_clave_idempotencia
    ON pedidos(clave_idempotencia);
CREATE UNIQUE INDEX IF NOT EXISTS idx_detalle_pedido_producto
    ON detalle_pedido(id_pedido, id_producto);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pagos_clave_idempotencia
    ON pagos_pedido(clave_idempotencia);
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_correo_unico
    ON usuarios(correo) WHERE correo IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_cliente_unico
    ON usuarios(id_cliente) WHERE id_cliente IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_facturas_pedido_unico
    ON facturas(id_pedido) WHERE id_pedido IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pedidos_estado_fecha
    ON pedidos(estado, fecha_pedido);
CREATE INDEX IF NOT EXISTS idx_pagos_pedido_fecha
    ON pagos_pedido(id_pedido, fecha_pago);
CREATE INDEX IF NOT EXISTS idx_usuarios_rol_estado
    ON usuarios(rol, estado);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'usuarios'::regclass AND conname = 'usuarios_rol_check'
    ) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT usuarios_rol_check
            CHECK (rol IN ('ADMIN', 'STAFF', 'CLIENTE'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'usuarios'::regclass AND conname = 'usuarios_estado_check'
    ) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT usuarios_estado_check
            CHECK (estado IN ('PENDIENTE', 'ACTIVO', 'RECHAZADO'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'usuarios'::regclass AND conname = 'usuarios_rol_cliente_check'
    ) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT usuarios_rol_cliente_check
            CHECK (
                (rol = 'CLIENTE' AND id_cliente IS NOT NULL)
                OR (rol IN ('ADMIN', 'STAFF') AND id_cliente IS NULL)
            );
    END IF;
END
$$;

COMMIT;
