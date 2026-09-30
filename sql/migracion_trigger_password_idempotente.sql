-- =============================================================================
-- MIGRACIÓN: TRIGGERS DE CIFRADO DE CONTRASEÑA IDEMPOTENTES
-- =============================================================================
-- Problema que resuelve:
--   La tabla `usuarios` llegó a tener DOS triggers de cifrado. El legado
--   (`usuarios_hash` -> hash_password()) solo respetaba el prefijo '$2a$', por
--   lo que volvía a cifrar con pgcrypto los hashes bcrypt '$2b$' generados por
--   la aplicación. El resultado era un "hash del hash" ($2a$06$...) y el inicio
--   de sesión nunca coincidía con la contraseña real.
--
--   Esta migración hace que AMBAS funciones dejen intacto cualquier hash ya
--   generado (bcrypt $2a$/$2b$/$2y$ y Werkzeug scrypt:/pbkdf2:) y cifren ÚNICAMENTE
--   texto plano. Así las dos formas de ingreso quedan correctas:
--     * Registro web  -> la app inserta su bcrypt y se guarda tal cual.
--     * INSERT en SQL -> el texto plano se cifra una sola vez con pgcrypto.
--
-- Es idempotente: puede ejecutarse varias veces sin efectos adversos.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Función principal usada por trg_cifrar_password (definida en esquema.sql).
CREATE OR REPLACE FUNCTION fn_cifrar_password() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.password IS NOT NULL THEN
        IF NEW.password NOT LIKE '$2a$%'
           AND NEW.password NOT LIKE '$2b$%'
           AND NEW.password NOT LIKE '$2y$%'
           AND NEW.password NOT LIKE 'scrypt:%'
           AND NEW.password NOT LIKE 'pbkdf2:%' THEN
            NEW.password := crypt(NEW.password::text, gen_salt('bf'));
        END IF;
    END IF;
    RETURN NEW;
END; $$;

-- Función legada usada por el trigger `usuarios_hash`, si existe en el entorno.
-- Se alinea con la lista segura para que nunca re-cifre un hash existente.
CREATE OR REPLACE FUNCTION hash_password() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.password IS NOT NULL
       AND LEFT(NEW.password, 4) <> '$2a$'
       AND LEFT(NEW.password, 4) <> '$2b$'
       AND LEFT(NEW.password, 4) <> '$2y$'
       AND LEFT(NEW.password, 7) <> 'scrypt:'
       AND LEFT(NEW.password, 7) <> 'pbkdf2:' THEN
        NEW.password := crypt(NEW.password, gen_salt('bf'));
    END IF;
    RETURN NEW;
END; $$;
