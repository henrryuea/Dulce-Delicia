-- ==============================================================================
-- MIGRACIÓN: KARDEX VALORIZADO E INSUMOS
-- ==============================================================================
-- Permite registrar el costo unitario de las entradas de inventario y marcar
-- productos como insumos (materias primas que no se venden, solo se consumen).
-- Es idempotente: puede ejecutarse varias veces sin efecto secundario.
-- La aplicación también la aplica automáticamente al arrancar.

ALTER TABLE kardex_movimientos
    ADD COLUMN IF NOT EXISTS costo_unitario NUMERIC(12,2);

ALTER TABLE productos
    ADD COLUMN IF NOT EXISTS es_insumo BOOLEAN NOT NULL DEFAULT FALSE;
