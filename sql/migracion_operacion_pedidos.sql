-- Ejecutar una sola vez sobre la base existente antes de desplegar la aplicación.
-- La migración conserva la clasificación y las relaciones de clientes, elimina
-- los campos sin uso comercial y retira los códigos 2FA simulados anteriores.
BEGIN;

DO $$
BEGIN
    IF to_regclass('public.tipos_negocio') IS NOT NULL
       AND to_regclass('public.tipos_cliente') IS NULL THEN
        ALTER TABLE tipos_negocio RENAME TO tipos_cliente;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'clientes'
          AND column_name = 'tipo_negocio_id'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'clientes'
          AND column_name = 'tipo_cliente_id'
    ) THEN
        ALTER TABLE clientes RENAME COLUMN tipo_negocio_id TO tipo_cliente_id;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'solicitudes'
          AND column_name = 'trabajo_realizado'
    ) THEN
        ALTER TABLE solicitudes DROP COLUMN trabajo_realizado;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'solicitudes'
          AND column_name = 'evidencia_url'
    ) THEN
        ALTER TABLE solicitudes DROP COLUMN evidencia_url;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'solicitudes'
          AND column_name = 'resuelto_por_id'
    ) THEN
        ALTER TABLE solicitudes RENAME COLUMN resuelto_por_id TO entregado_por_id;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'solicitudes'
          AND column_name = 'fecha_resolucion'
    ) THEN
        ALTER TABLE solicitudes RENAME COLUMN fecha_resolucion TO fecha_entrega;
    END IF;
END $$;

ALTER TABLE facturacion
    ADD COLUMN IF NOT EXISTS fecha_entrega DATE,
    ADD COLUMN IF NOT EXISTS modalidad_entrega VARCHAR(20),
    ADD COLUMN IF NOT EXISTS ubicacion_entrega TEXT,
    DROP COLUMN IF EXISTS con_intereses,
    DROP COLUMN IF EXISTS tasa_interes,
    DROP COLUMN IF EXISTS monto_interes,
    DROP COLUMN IF EXISTS total_con_interes,
    DROP COLUMN IF EXISTS fecha_limite;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_facturacion_modalidad_entrega'
          AND conrelid = 'public.facturacion'::regclass
    ) THEN
        ALTER TABLE facturacion
            ADD CONSTRAINT ck_facturacion_modalidad_entrega
            CHECK (modalidad_entrega IS NULL OR modalidad_entrega IN ('domicilio', 'retiro_local'));
    END IF;
END $$;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS dos_factores_secreto TEXT,
    ADD COLUMN IF NOT EXISTS dos_factores_secreto_pendiente TEXT,
    ADD COLUMN IF NOT EXISTS dos_factores_intentos SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS dos_factores_bloqueo_hasta TIMESTAMP,
    ADD COLUMN IF NOT EXISTS dos_factores_ultimo_periodo BIGINT;

ALTER TABLE usuarios
    ALTER COLUMN dos_factores_activo SET DEFAULT FALSE,
    DROP COLUMN IF EXISTS dos_factores_codigo,
    DROP COLUMN IF EXISTS fecha_nacimiento,
    DROP COLUMN IF EXISTS es_mayor_edad;

ALTER TABLE solicitudes
    ADD COLUMN IF NOT EXISTS pedido_entregado BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE solicitudes
SET estado = CASE
    WHEN estado = 'Resuelta' THEN 'Pendiente'
    WHEN estado = 'Descartada' THEN 'Cancelada'
    WHEN estado = 'En revisión' THEN 'Confirmado'
    WHEN estado = 'Asignada' THEN 'Pendiente'
    WHEN estado = 'En proceso' THEN 'En preparación'
    ELSE estado
END,
pedido_entregado = FALSE,
entregado_por_id = NULL,
fecha_entrega = NULL;

ALTER TABLE solicitudes
    ALTER COLUMN estado SET DEFAULT 'Pendiente';

COMMIT;
