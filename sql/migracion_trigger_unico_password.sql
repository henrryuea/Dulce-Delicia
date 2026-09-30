-- =============================================================================
-- MIGRACIÓN: UN SOLO TRIGGER DE CIFRADO DE CONTRASEÑA
-- =============================================================================
-- Problema que resuelve:
--   La tabla `usuarios` tiene DOS triggers BEFORE INSERT OR UPDATE de cifrado
--   (`trg_cifrar_password` y el legado `usuarios_hash`). Con dos funciones de
--   cifrado activas existe el riesgo de que una contraseña se cifre dos veces
--   ("hash del hash") y que el inicio de sesión deje de coincidir con la
--   contraseña real.
--
--   Esta migración deja UNA sola función y UN solo trigger, ambos idempotentes:
--   cifran únicamente texto plano y respetan intactos los hashes ya generados
--   (bcrypt $2a$/$2b$/$2y$ y Werkzeug scrypt:/pbkdf2:).
--
-- Resultado esperado:
--   * Registro web        -> la app inserta su bcrypt y se guarda tal cual.
--   * INSERT en SQL       -> el texto plano se cifra una sola vez con pgcrypto.
--   * Cambio de clave     -> se cifra una sola vez.
--
-- Es idempotente: puede ejecutarse varias veces sin efectos adversos.
-- Verificación:
--   SELECT tgname FROM pg_trigger
--   WHERE tgrelid = 'usuarios'::regclass AND NOT tgisinternal;
--   -- debe devolver únicamente: trg_cifrar_password
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Función única de cifrado, idempotente por prefijo de algoritmo.
CREATE OR REPLACE FUNCTION fn_cifrar_password() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.password IS NOT NULL
       AND LEFT(NEW.password, 4) <> '$2a$'
       AND LEFT(NEW.password, 4) <> '$2b$'
       AND LEFT(NEW.password, 4) <> '$2y$'
       AND LEFT(NEW.password, 7) <> 'scrypt:'
       AND LEFT(NEW.password, 7) <> 'pbkdf2:' THEN
        NEW.password := crypt(NEW.password::text, gen_salt('bf'));
    END IF;
    RETURN NEW;
END; $$;

-- Trigger único, recreado desde cero para descartar cualquier configuración previa.
DROP TRIGGER IF EXISTS usuarios_hash ON usuarios;
DROP TRIGGER IF EXISTS trg_cifrar_password ON usuarios;

CREATE TRIGGER trg_cifrar_password
    BEFORE INSERT OR UPDATE ON usuarios
    FOR EACH ROW
    EXECUTE FUNCTION fn_cifrar_password();

-- Se elimina la función legada para que no pueda volver a activarse por error.
DROP FUNCTION IF EXISTS hash_password();
