-- Conserva en cada venta y recibo los datos de cliente vigentes al emitirlo.
-- Idempotente: solo agrega campos ausentes; no modifica ni elimina registros.
BEGIN;

ALTER TABLE facturacion
    ADD COLUMN IF NOT EXISTS cliente_nombre_snapshot VARCHAR(150),
    ADD COLUMN IF NOT EXISTS cliente_apellido_snapshot VARCHAR(100),
    ADD COLUMN IF NOT EXISTS cliente_correo_snapshot VARCHAR(150),
    ADD COLUMN IF NOT EXISTS cliente_telefono_snapshot VARCHAR(20),
    ADD COLUMN IF NOT EXISTS cliente_direccion_snapshot VARCHAR(300),
    ADD COLUMN IF NOT EXISTS cliente_ciudad_snapshot VARCHAR(100);

ALTER TABLE comprobantes_pago
    ADD COLUMN IF NOT EXISTS cliente_nombre_snapshot VARCHAR(150),
    ADD COLUMN IF NOT EXISTS cliente_apellido_snapshot VARCHAR(100),
    ADD COLUMN IF NOT EXISTS cliente_correo_snapshot VARCHAR(150),
    ADD COLUMN IF NOT EXISTS cliente_telefono_snapshot VARCHAR(20),
    ADD COLUMN IF NOT EXISTS cliente_direccion_snapshot VARCHAR(300),
    ADD COLUMN IF NOT EXISTS cliente_ciudad_snapshot VARCHAR(100);

COMMIT;
