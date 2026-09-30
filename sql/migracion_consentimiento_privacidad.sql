-- Aplicar antes de desplegar el formulario de registro actualizado.
BEGIN;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS acepta_tratamiento_datos BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fecha_consentimiento_datos TIMESTAMP;

COMMIT;
