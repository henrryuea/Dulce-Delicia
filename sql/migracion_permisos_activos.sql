-- =============================================================================
-- MIGRACIÓN: PERMISOS ACTIVABLES DESDE POSTGRESQL
-- =============================================================================
-- Hasta ahora un permiso solo podía consultarse desde la web: la tabla
-- `permisos` no tenía forma de activar o desactivar un permiso, y `rol_permisos`
-- solo se leía. Esta migración permite administrar los permisos tanto desde el
-- panel web como directamente desde PostgreSQL (pgAdmin, psql, cualquier
-- cliente), y ambos caminos escriben en las mismas tablas.
--
--   * `permisos.activo`  -> enciende o apaga el permiso para toda la aplicación.
--   * Vista `v_permisos_rol` -> matriz rol × permiso, lista para consultar.
--   * `activar_permiso(codigo, activo)`  -> enciende/apaga un permiso.
--   * `asignar_permiso(rol, codigo)`     -> concede el permiso a un rol.
--   * `revocar_permiso(rol, codigo)`      -> lo retira del rol.
--
-- La aplicación no cachea permisos: cualquier cambio hecho aquí se aplica en la
-- siguiente petición.
--
-- Ejemplos desde pgAdmin / psql:
--   SELECT * FROM activar_permiso('usuarios.aprobar', TRUE);
--   SELECT * FROM asignar_permiso('Encargado', 'usuarios.aprobar');
--   SELECT * FROM revocar_permiso('Cliente', 'facturas.ver_propias');
--   SELECT * FROM v_permisos_rol WHERE asignado;
--
-- Es idempotente: puede ejecutarse varias veces sin efectos adversos.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Bandera de activación
-- -----------------------------------------------------------------------------
ALTER TABLE permisos ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE permisos ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP;
ALTER TABLE permisos ALTER COLUMN actualizado_en SET DEFAULT CURRENT_TIMESTAMP;

-- Cualquier permiso que ya estuviera asignado a algún rol queda activo.
UPDATE permisos SET activo = TRUE WHERE activo IS NULL;

-- -----------------------------------------------------------------------------
-- 2. Vista con la matriz completa rol x permiso
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_permisos_rol AS
SELECT r.id AS rol_id,
       r.nombre AS rol_nombre,
       p.id AS permiso_id,
       p.codigo AS permiso_codigo,
       p.descripcion,
       p.activo AS permiso_activo,
       (rp.rol_id IS NOT NULL) AS asignado
FROM roles r
CROSS JOIN permisos p
LEFT JOIN rol_permisos rp ON rp.rol_id = r.id AND rp.permiso_id = p.id;

COMMENT ON VIEW v_permisos_rol IS
    'Matriz rol x permiso. Un permiso solo concede acceso si esta activo = TRUE.';

-- -----------------------------------------------------------------------------
-- 3. Funciones de administración desde PostgreSQL
-- -----------------------------------------------------------------------------
-- Se reemplazan explícitamente porque PostgreSQL no admite cambiar el tipo de
-- retorno de una función existente con CREATE OR REPLACE.
DROP FUNCTION IF EXISTS activar_permiso(VARCHAR, BOOLEAN);
DROP FUNCTION IF EXISTS asignar_permiso(VARCHAR, VARCHAR);
DROP FUNCTION IF EXISTS revocar_permiso(VARCHAR, VARCHAR);

CREATE OR REPLACE FUNCTION activar_permiso(p_codigo VARCHAR, p_activo BOOLEAN DEFAULT TRUE)
RETURNS TABLE (codigo VARCHAR, descripcion TEXT, activo BOOLEAN)
LANGUAGE plpgsql AS $$
DECLARE
    resultado RECORD;
BEGIN
    -- Se califica la columna porque `codigo` también es una variable de salida.
    UPDATE permisos
    SET activo = COALESCE(p_activo, TRUE),
        actualizado_en = CURRENT_TIMESTAMP
    WHERE permisos.codigo = p_codigo
    RETURNING * INTO resultado;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El permiso % no existe en la tabla permisos', p_codigo;
    END IF;

    RETURN QUERY SELECT resultado.codigo, resultado.descripcion, resultado.activo;
END; $$;

CREATE OR REPLACE FUNCTION asignar_permiso(p_rol VARCHAR, p_codigo VARCHAR)
RETURNS TABLE (rol_nombre VARCHAR, permiso_codigo VARCHAR, permiso_activo BOOLEAN, asignado BOOLEAN)
LANGUAGE plpgsql AS $$
DECLARE
    id_rol INTEGER;
    id_permiso INTEGER;
    estado BOOLEAN;
BEGIN
    SELECT id INTO id_rol FROM roles WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(p_rol));
    IF id_rol IS NULL THEN
        RAISE EXCEPTION 'El rol % no existe en la tabla roles', p_rol;
    END IF;

    SELECT id, activo INTO id_permiso, estado FROM permisos WHERE codigo = p_codigo;
    IF id_permiso IS NULL THEN
        RAISE EXCEPTION 'El permiso % no existe en la tabla permisos', p_codigo;
    END IF;

    INSERT INTO rol_permisos (rol_id, permiso_id)
    VALUES (id_rol, id_permiso)
    ON CONFLICT (rol_id, permiso_id) DO NOTHING;

    RETURN QUERY SELECT r.nombre, p.codigo, p.activo, TRUE
    FROM roles r, permisos p
    WHERE r.id = id_rol AND p.id = id_permiso;
END; $$;

CREATE OR REPLACE FUNCTION revocar_permiso(p_rol VARCHAR, p_codigo VARCHAR)
RETURNS TABLE (rol_nombre VARCHAR, permiso_codigo VARCHAR, permiso_activo BOOLEAN, asignado BOOLEAN)
LANGUAGE plpgsql AS $$
DECLARE
    id_rol INTEGER;
    id_permiso INTEGER;
BEGIN
    SELECT id INTO id_rol FROM roles WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(p_rol));
    SELECT id INTO id_permiso FROM permisos WHERE codigo = p_codigo;

    IF id_rol IS NULL OR id_permiso IS NULL THEN
        RAISE EXCEPTION 'El rol o el permiso indicado no existen';
    END IF;

    DELETE FROM rol_permisos WHERE rol_id = id_rol AND permiso_id = id_permiso;

    RETURN QUERY SELECT r.nombre, p.codigo, p.activo, FALSE
    FROM roles r, permisos p
    WHERE r.id = id_rol AND p.id = id_permiso;
END; $$;

-- -----------------------------------------------------------------------------
-- 4. Resumen para diagnosing desde la consola
-- -----------------------------------------------------------------------------
--   SELECT rol_nombre, count(*) FILTER (WHERE asignado AND permiso_activo) AS efectivos
--   FROM v_permisos_rol GROUP BY rol_nombre ORDER BY rol_nombre;
--
--   SELECT codigo, activo FROM permisos WHERE NOT activo;
