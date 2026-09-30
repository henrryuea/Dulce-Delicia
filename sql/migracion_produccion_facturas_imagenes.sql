-- Registra la hora de emisión, imágenes locales de catálogo y trazabilidad de lotes.
-- Las horas históricas quedan NULL: no se inventa información que nunca se guardó.

ALTER TABLE facturacion
    ADD COLUMN IF NOT EXISTS fecha_hora_emision TIMESTAMP;

ALTER TABLE productos DROP COLUMN IF EXISTS imagen;

CREATE INDEX IF NOT EXISTS idx_facturacion_fecha_hora
    ON facturacion (fecha_hora_emision);

CREATE TABLE IF NOT EXISTS imagenes_productos (
    producto_id INTEGER PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
    contenido BYTEA,
    url TEXT,
    tipo_contenido VARCHAR(30) NOT NULL DEFAULT 'image/jpeg',
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE imagenes_productos
    ADD COLUMN IF NOT EXISTS url TEXT;

ALTER TABLE imagenes_productos
    ALTER COLUMN contenido DROP NOT NULL;

CREATE TABLE IF NOT EXISTS lotes_produccion (
    id SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    movimiento_produccion_id INTEGER NOT NULL UNIQUE
        REFERENCES kardex_movimientos(id) ON DELETE RESTRICT,
    cantidad_producida INTEGER NOT NULL CHECK (cantidad_producida > 0),
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ventas_lote (
    id SERIAL PRIMARY KEY,
    lote_id INTEGER NOT NULL REFERENCES lotes_produccion(id) ON DELETE CASCADE,
    detalle_factura_id INTEGER NOT NULL
        REFERENCES detalle_factura(id) ON DELETE CASCADE,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    CONSTRAINT uq_venta_lote_detalle UNIQUE (lote_id, detalle_factura_id)
);

CREATE TABLE IF NOT EXISTS mermas_lote (
    id SERIAL PRIMARY KEY,
    lote_id INTEGER NOT NULL REFERENCES lotes_produccion(id) ON DELETE CASCADE,
    movimiento_merma_id INTEGER NOT NULL UNIQUE
        REFERENCES kardex_movimientos(id) ON DELETE RESTRICT,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    registrado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lotes_produccion_producto_fecha
    ON lotes_produccion (producto_id, creado_en, id);
CREATE INDEX IF NOT EXISTS idx_ventas_lote_detalle
    ON ventas_lote (detalle_factura_id);
CREATE INDEX IF NOT EXISTS idx_mermas_lote_lote
    ON mermas_lote (lote_id);
