-- =============================================================================
-- MIGRACION: INTEGRIDAD DE PAGOS, CUOTAS Y SOLICITUDES DE ACCESO
-- =============================================================================
-- Aplicar una vez a bases existentes despues de crear un respaldo.
--
-- * Registra aplicaciones pago-cuota como una relacion muchos-a-muchos.
-- * Impide enlazar pagos o cuotas de facturas distintas y valida el saldo
--   restante de cada cuota.
-- * Conserva solicitudes de acceso anteriores en vez de sobrescribirlas.
--
-- No se reconstruyen aplicaciones historicas desde cuotas_factura.pago_id:
-- esa columna solo conserva un pago por cuota y no contiene un importe fiable
-- cuando hubo varios abonos. Los enlaces antiguos se conservan intactos.
-- =============================================================================

BEGIN;

-- No ajustar saldos historicos automaticamente: primero informar y resolver
-- cualquier inconsistencia para preservar el historial contable.
DO $$
DECLARE
    cuotas_inconsistentes BIGINT;
BEGIN
    SELECT COUNT(*) INTO cuotas_inconsistentes
    FROM cuotas_factura
    WHERE valor_pago < 0
       OR monto_pagado < 0
       OR monto_pagado > valor_pago
       OR saldo_pago <> valor_pago - monto_pagado;

    IF cuotas_inconsistentes > 0 THEN
        RAISE EXCEPTION
            'Migracion cancelada: % cuotas tienen valores o saldos incompatibles. Corrija esos registros antes de reintentar.',
            cuotas_inconsistentes;
    END IF;
END $$;

ALTER TABLE cuotas_factura DROP CONSTRAINT IF EXISTS ck_cuota_importes;
ALTER TABLE cuotas_factura
    ADD CONSTRAINT ck_cuota_importes CHECK (
        valor_pago >= 0 AND monto_pagado >= 0
        AND monto_pagado <= valor_pago
        AND saldo_pago = valor_pago - monto_pagado
    );

ALTER TABLE pagos_factura
    ADD COLUMN IF NOT EXISTS exige_aplicacion BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE cuotas_factura
    ADD COLUMN IF NOT EXISTS exige_aplicacion BOOLEAN NOT NULL DEFAULT FALSE;

-- Claves candidatas requeridas para validar simultaneamente el pago/cuota y
-- su factura. Las claves primarias simples existentes permanecen intactas.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'pagos_factura'::regclass
          AND contype IN ('p', 'u')
          AND pg_get_constraintdef(oid) = 'UNIQUE (id, factura_numero)'
    ) THEN
        ALTER TABLE pagos_factura
            ADD CONSTRAINT uq_pago_id_factura UNIQUE (id, factura_numero);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cuotas_factura'::regclass
          AND contype IN ('p', 'u')
          AND pg_get_constraintdef(oid) = 'UNIQUE (id, factura_numero)'
    ) THEN
        ALTER TABLE cuotas_factura
            ADD CONSTRAINT uq_cuota_id_factura UNIQUE (id, factura_numero);
    END IF;
END $$;

-- Rechazar enlaces historicos ambiguos o cruzados en vez de descartarlos.
DO $$
DECLARE
    enlaces_invalidos BIGINT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'cuotas_factura'
          AND column_name = 'pago_id'
    ) THEN
        SELECT COUNT(*) INTO enlaces_invalidos
        FROM cuotas_factura c
        LEFT JOIN pagos_factura p ON p.id = c.pago_id
        WHERE c.pago_id IS NOT NULL
          AND (p.id IS NULL OR p.factura_numero IS DISTINCT FROM c.factura_numero);

        IF enlaces_invalidos > 0 THEN
            RAISE EXCEPTION
                'Migracion cancelada: % cuotas tienen un pago inexistente o de otra factura. Corrija esos enlaces antes de reintentar.',
                enlaces_invalidos;
        END IF;
    END IF;
END $$;

-- Elimina la FK antigua de una sola columna si existe; en las bases nuevas no
-- existe pago_id en cuotas_factura y toda la atribucion usa aplicaciones_pago.
DO $$
DECLARE
    restriccion RECORD;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'cuotas_factura'
          AND column_name = 'pago_id'
    ) THEN
        FOR restriccion IN
            SELECT c.conname
            FROM pg_constraint c
            WHERE c.conrelid = 'cuotas_factura'::regclass
              AND c.contype = 'f'
              AND c.confrelid = 'pagos_factura'::regclass
              AND c.conkey = ARRAY[
                  (SELECT a.attnum
                   FROM pg_attribute a
                   WHERE a.attrelid = 'cuotas_factura'::regclass
                     AND a.attname = 'pago_id')
              ]::smallint[]
        LOOP
            EXECUTE format('ALTER TABLE cuotas_factura DROP CONSTRAINT %I', restriccion.conname);
        END LOOP;

        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'cuotas_factura'::regclass
              AND conname = 'fk_cuotas_factura_pago_factura'
        ) THEN
            ALTER TABLE cuotas_factura
                ADD CONSTRAINT fk_cuotas_factura_pago_factura
                FOREIGN KEY (pago_id, factura_numero)
                REFERENCES pagos_factura(id, factura_numero)
                ON DELETE SET NULL (pago_id) ON UPDATE CASCADE;
        END IF;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS aplicaciones_pago (
    pago_id INTEGER NOT NULL,
    cuota_id INTEGER NOT NULL,
    factura_numero VARCHAR(30) NOT NULL,
    monto_aplicado NUMERIC(12,2) NOT NULL CHECK (monto_aplicado > 0),
    fecha_aplicacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pago_id, cuota_id),
    CONSTRAINT fk_aplicaciones_pago_pago_factura
        FOREIGN KEY (pago_id, factura_numero)
        REFERENCES pagos_factura(id, factura_numero) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_aplicaciones_pago_cuota_factura
        FOREIGN KEY (cuota_id, factura_numero)
        REFERENCES cuotas_factura(id, factura_numero) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_aplicaciones_pago_cuota
    ON aplicaciones_pago (factura_numero, cuota_id);

CREATE OR REPLACE FUNCTION fn_validar_integridad_aplicaciones() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    pago_ids INTEGER[] := ARRAY[]::INTEGER[];
    cuota_ids INTEGER[] := ARRAY[]::INTEGER[];
    id_actual INTEGER;
    monto_esperado NUMERIC(12,2);
    monto_aplicado_total NUMERIC(12,2);
    requiere_aplicacion BOOLEAN;
BEGIN
    IF TG_TABLE_NAME = 'aplicaciones_pago' THEN
        IF TG_OP <> 'INSERT' THEN
            pago_ids := array_append(pago_ids, OLD.pago_id);
            cuota_ids := array_append(cuota_ids, OLD.cuota_id);
        END IF;
        IF TG_OP <> 'DELETE' THEN
            pago_ids := array_append(pago_ids, NEW.pago_id);
            cuota_ids := array_append(cuota_ids, NEW.cuota_id);
        END IF;
    ELSIF TG_TABLE_NAME = 'pagos_factura' THEN
        IF TG_OP <> 'INSERT' THEN
            pago_ids := array_append(pago_ids, OLD.id);
        END IF;
        IF TG_OP <> 'DELETE' THEN
            pago_ids := array_append(pago_ids, NEW.id);
        END IF;
    ELSE
        IF TG_OP <> 'INSERT' THEN
            cuota_ids := array_append(cuota_ids, OLD.id);
        END IF;
        IF TG_OP <> 'DELETE' THEN
            cuota_ids := array_append(cuota_ids, NEW.id);
        END IF;
    END IF;

    FOREACH id_actual IN ARRAY pago_ids LOOP
        SELECT p.monto, p.exige_aplicacion
        INTO monto_esperado, requiere_aplicacion
        FROM pagos_factura p
        WHERE p.id = id_actual
        FOR UPDATE;

        IF FOUND THEN
            SELECT COALESCE(SUM(a.monto_aplicado), 0)
            INTO monto_aplicado_total
            FROM aplicaciones_pago a
            WHERE a.pago_id = id_actual;

            IF monto_aplicado_total > monto_esperado
               OR (requiere_aplicacion AND monto_aplicado_total <> monto_esperado) THEN
                RAISE EXCEPTION
                    'Aplicaciones del pago % suman %, pero el pago es %',
                    id_actual, monto_aplicado_total, monto_esperado
                    USING ERRCODE = '23514';
            END IF;
        END IF;
    END LOOP;

    FOREACH id_actual IN ARRAY cuota_ids LOOP
        SELECT c.monto_pagado, c.exige_aplicacion
        INTO monto_esperado, requiere_aplicacion
        FROM cuotas_factura c
        WHERE c.id = id_actual
        FOR UPDATE;

        IF FOUND THEN
            SELECT COALESCE(SUM(a.monto_aplicado), 0)
            INTO monto_aplicado_total
            FROM aplicaciones_pago a
            WHERE a.cuota_id = id_actual;

            IF monto_aplicado_total > monto_esperado
               OR (requiere_aplicacion AND monto_aplicado_total <> monto_esperado) THEN
                RAISE EXCEPTION
                    'Aplicaciones de la cuota % suman %, pero el monto pagado es %',
                    id_actual, monto_aplicado_total, monto_esperado
                    USING ERRCODE = '23514';
            END IF;
        END IF;
    END LOOP;

    RETURN NULL;
END; $$;

DROP TRIGGER IF EXISTS ct_aplicaciones_pago_integridad ON aplicaciones_pago;
CREATE CONSTRAINT TRIGGER ct_aplicaciones_pago_integridad
    AFTER INSERT OR UPDATE OR DELETE ON aplicaciones_pago
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_integridad_aplicaciones();

DROP TRIGGER IF EXISTS ct_pagos_factura_aplicaciones ON pagos_factura;
CREATE CONSTRAINT TRIGGER ct_pagos_factura_aplicaciones
    AFTER INSERT OR UPDATE OR DELETE ON pagos_factura
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_integridad_aplicaciones();

DROP TRIGGER IF EXISTS ct_cuotas_factura_aplicaciones ON cuotas_factura;
CREATE CONSTRAINT TRIGGER ct_cuotas_factura_aplicaciones
    AFTER INSERT OR UPDATE OR DELETE ON cuotas_factura
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validar_integridad_aplicaciones();

-- Solicitudes de acceso constituyen un historial: una nueva decision no debe
-- reemplazar la solicitud anterior de la misma cuenta y rol.
DO $$
DECLARE
    restriccion RECORD;
BEGIN
    FOR restriccion IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'solicitudes_acceso'::regclass
          AND contype = 'u'
          AND pg_get_constraintdef(oid) = 'UNIQUE (usuario_id, rol_id)'
    LOOP
        EXECUTE format('ALTER TABLE solicitudes_acceso DROP CONSTRAINT %I', restriccion.conname);
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_solicitudes_acceso_usuario_rol_fecha
    ON solicitudes_acceso (usuario_id, rol_id, fecha_solicitud DESC, id DESC);

CREATE OR REPLACE FUNCTION fn_registrar_solicitud_acceso() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.aprobado IS DISTINCT FROM NEW.aprobado THEN
        IF NEW.aprobado THEN
            UPDATE solicitudes_acceso
            SET estado = 'Aprobada', fecha_decision = CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id FROM solicitudes_acceso
                WHERE usuario_id = NEW.id AND rol_id = NEW.rol_id AND estado = 'Pendiente'
                ORDER BY fecha_solicitud DESC, id DESC
                LIMIT 1
            );

            IF NOT FOUND THEN
                INSERT INTO solicitudes_acceso (usuario_id, rol_id, estado, fecha_decision)
                VALUES (NEW.id, NEW.rol_id, 'Aprobada', CURRENT_TIMESTAMP);
            END IF;
        ELSE
            INSERT INTO solicitudes_acceso (usuario_id, rol_id, estado, fecha_decision)
            VALUES (NEW.id, NEW.rol_id, 'Rechazada', CURRENT_TIMESTAMP);
        END IF;
    END IF;
    RETURN NEW;
END; $$;

COMMIT;
