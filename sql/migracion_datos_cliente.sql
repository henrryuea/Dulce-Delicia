-- Datos de contacto que utiliza el formulario actual de clientes y facturacion.
-- Idempotente y no destructiva: agrega campos opcionales sin cambiar filas previas.
BEGIN;

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS apellido VARCHAR(100),
    ADD COLUMN IF NOT EXISTS direccion VARCHAR(300);

COMMIT;
