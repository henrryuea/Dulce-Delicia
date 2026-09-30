-- =============================================================================
-- MIGRACIÓN: NEXO DE USUARIOS + SOLICITUDES DE ACCESO
-- =============================================================================
-- `usuarios` es la tabla nexo del proyecto: su `id` ya referencian clientes,
-- productos, proveedores, facturas, kardex, solicitudes y logs de auditoría.
-- Esta migración completa sus datos de identidad y crea el historial de
-- solicitudes de acceso para que el Administrador apruebe o rechace cada
-- cuenta con respaldo y trazabilidad.
--
-- Es idempotente: puede ejecutarse varias veces sin efectos adversos.
-- =============================================================================

-- 1. Datos de identidad que exige la ficha de la cuenta
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS es_mayor_edad BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Historial de solicitudes de acceso (aprobaciones y rechazos)
CREATE TABLE IF NOT EXISTS solicitudes_acceso (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rol_id INTEGER NOT NULL REFERENCES roles(id),
    estado VARCHAR(20) NOT NULL DEFAULT 'Pendiente'
        CHECK (estado IN ('Pendiente', 'Aprobada', 'Rechazada')),
    motivo TEXT,
    fecha_solicitud TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_decision TIMESTAMP,
    decidido_por VARCHAR(150)
);

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

CREATE INDEX IF NOT EXISTS idx_solicitudes_acceso_estado
    ON solicitudes_acceso (estado, fecha_solicitud DESC);

-- 3. Registro automático de la decisión cuando cambia `usuarios.aprobado`
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

DROP TRIGGER IF EXISTS trg_solicitud_acceso ON usuarios;
CREATE TRIGGER trg_solicitud_acceso
    AFTER UPDATE OF aprobado ON usuarios
    FOR EACH ROW
    EXECUTE FUNCTION fn_registrar_solicitud_acceso();

-- 4. Carga inicial: una solicitud por cada cuenta existente
INSERT INTO solicitudes_acceso (usuario_id, rol_id, estado, fecha_solicitud, fecha_decision)
SELECT u.id, u.rol_id,
       CASE WHEN u.aprobado THEN 'Aprobada' ELSE 'Pendiente' END,
       u.fecha_registro,
       CASE WHEN u.aprobado THEN u.fecha_registro ELSE NULL END
FROM usuarios u
WHERE NOT EXISTS (
    SELECT 1
    FROM solicitudes_acceso s
    WHERE s.usuario_id = u.id AND s.rol_id = u.rol_id
);
