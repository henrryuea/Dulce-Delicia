-- =============================================================================
-- MIGRACIÓN: ALINEAR CUOTAS Y PAGOS CON EL ESQUEMA CANÓNICO
-- =============================================================================
-- Problema que resuelve:
--   La base de datos quedó con los nombres antiguos `*_cuota`
--   (numero_cuota, valor_cuota, saldo_cuota, proxima_cuota_*), mientras que la
--   aplicación, las plantillas y `esquema.sql` usan `*_pago`
--   (numero_pago, valor_pago, saldo_pago, proxima_pago_*). Con la base
--   desalineada, el listado de facturación fallaba con
--   `column "numero_pago" does not exist`.
--
--   PostgreSQL no permite tener las dos columnas a la vez con el mismo
--   contenido, por eso se RENAME COLUMN: los datos se conservan intactos y las
--   claves foráneas y restricciones siguen apuntando al mismo sitio.
--
-- Es idempotente: puede ejecutarse varias veces sin efectos adversos.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Plan de pagos: cuota -> pago
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    cambio TEXT;
    origen TEXT;
    tabla TEXT;
    columna TEXT;
    nueva TEXT;
BEGIN
    FOREACH cambio IN ARRAY ARRAY[
        'cuotas_factura.numero_cuota|numero_pago',
        'cuotas_factura.valor_cuota|valor_pago',
        'cuotas_factura.saldo_cuota|saldo_pago',
        'facturacion.proxima_cuota_fecha|proxima_pago_fecha',
        'facturacion.proxima_cuota_monto|proxima_pago_monto',
        'comprobantes_pago.proxima_cuota_num|proxima_pago_num',
        'comprobantes_pago.proxima_cuota_fecha|proxima_pago_fecha',
        'comprobantes_pago.proxima_cuota_monto|proxima_pago_monto'
    ] LOOP
        -- 'cuotas_factura.numero_cuota|numero_pago' -> tabla, columna, nueva
        origen := split_part(cambio, '|', 1);
        nueva := split_part(cambio, '|', 2);
        tabla := split_part(origen, '.', 1);
        columna := split_part(origen, '.', 2);

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = tabla AND column_name = columna
        ) AND NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = tabla AND column_name = nueva
        ) THEN
            EXECUTE format('ALTER TABLE %I RENAME COLUMN %I TO %I', tabla, columna, nueva);
        END IF;
    END LOOP;
END $$;

-- -----------------------------------------------------------------------------
-- 2. Restricciones canónicas de la tabla de cuotas
-- -----------------------------------------------------------------------------
ALTER TABLE cuotas_factura DROP CONSTRAINT IF EXISTS uq_cuota_factura;
ALTER TABLE cuotas_factura ADD CONSTRAINT uq_cuota_factura
    UNIQUE (factura_numero, numero_pago);

ALTER TABLE cuotas_factura DROP CONSTRAINT IF EXISTS ck_cuota_importes;
ALTER TABLE cuotas_factura ADD CONSTRAINT ck_cuota_importes
    CHECK (valor_pago >= 0 AND monto_pagado <= valor_pago AND saldo_pago >= 0);

-- -----------------------------------------------------------------------------
-- 3. Verificación
-- -----------------------------------------------------------------------------
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name IN ('cuotas_factura', 'facturacion', 'comprobantes_pago')
--     AND column_name LIKE '%cuota%';
--   -- no debe devolver ninguna fila
