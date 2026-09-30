-- =============================================================================
-- MIGRACION: NORMALIZAR EL DESGLOSE DE IMPUESTOS DE CADA DOCUMENTO
-- =============================================================================
-- Aplicar despues de crear un respaldo. Conserva cada tasa y monto emitidos
-- como filas relacionadas antes de retirar la columna JSONB.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS impuestos_factura (
    id SERIAL PRIMARY KEY,
    factura_numero VARCHAR(30) NOT NULL
        REFERENCES facturacion(numero) ON DELETE CASCADE ON UPDATE CASCADE,
    orden SMALLINT NOT NULL CHECK (orden > 0),
    parametro_id INT REFERENCES parametros(id) ON DELETE SET NULL,
    codigo VARCHAR(50) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    descripcion VARCHAR(300),
    porcentaje NUMERIC(7,4) NOT NULL CHECK (porcentaje >= 0 AND porcentaje <= 100),
    monto NUMERIC(12,2) NOT NULL CHECK (monto >= 0),
    CONSTRAINT uq_impuesto_factura_orden UNIQUE (factura_numero, orden)
);

DO $$
DECLARE
    documentos_invalidos BIGINT;
    impuestos_invalidos BIGINT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'facturacion'
          AND column_name = 'impuestos_detalle'
    ) THEN
        SELECT COUNT(*) INTO documentos_invalidos
        FROM facturacion
        WHERE impuestos_detalle IS NULL
           OR jsonb_typeof(impuestos_detalle) <> 'array';

        IF documentos_invalidos > 0 THEN
            RAISE EXCEPTION
                'Migracion cancelada: % documentos tienen un desglose de impuestos que no es un arreglo JSON.',
                documentos_invalidos;
        END IF;

        SELECT COUNT(*) INTO impuestos_invalidos
        FROM facturacion f
        CROSS JOIN LATERAL jsonb_array_elements(f.impuestos_detalle) impuesto
        WHERE jsonb_typeof(impuesto) <> 'object'
           OR NULLIF(BTRIM(impuesto->>'nombre'), '') IS NULL
           OR LENGTH(impuesto->>'nombre') > 100
           OR LENGTH(impuesto->>'descripcion') > 300
           OR LENGTH(impuesto->>'codigo') > 50
           OR COALESCE(impuesto->>'porcentaje', '') !~ '^-?[0-9]+(\.[0-9]+)?$'
           OR COALESCE(impuesto->>'monto', '') !~ '^-?[0-9]+(\.[0-9]+)?$';

        IF impuestos_invalidos > 0 THEN
            RAISE EXCEPTION
                'Migracion cancelada: % entradas de impuesto tienen datos incompletos o importes no numericos.',
                impuestos_invalidos;
        END IF;

        INSERT INTO impuestos_factura (
            factura_numero, orden, parametro_id, codigo, nombre, descripcion, porcentaje, monto
        )
        SELECT f.numero,
               item.ordinalidad::SMALLINT,
               pa.id,
               COALESCE(NULLIF(BTRIM(impuesto->>'codigo'), ''), 'legacy-' || item.ordinalidad::text),
               BTRIM(impuesto->>'nombre'),
               NULLIF(BTRIM(impuesto->>'descripcion'), ''),
               (impuesto->>'porcentaje')::NUMERIC(7,4),
               (impuesto->>'monto')::NUMERIC(12,2)
        FROM facturacion f
        CROSS JOIN LATERAL jsonb_array_elements(f.impuestos_detalle)
            WITH ORDINALITY AS item(impuesto, ordinalidad)
        LEFT JOIN parametros pa
            ON LOWER(pa.codigo) = LOWER(COALESCE(NULLIF(BTRIM(impuesto->>'codigo'), ''), ''))
        ON CONFLICT (factura_numero, orden) DO NOTHING;

        SELECT COUNT(*) INTO impuestos_invalidos
        FROM facturacion f
        CROSS JOIN LATERAL jsonb_array_elements(f.impuestos_detalle)
            WITH ORDINALITY AS item(impuesto, ordinalidad)
        LEFT JOIN impuestos_factura i
            ON i.factura_numero = f.numero
           AND i.orden = item.ordinalidad
           AND i.codigo = LEFT(
                COALESCE(NULLIF(BTRIM(item.impuesto->>'codigo'), ''),
                         'legacy-' || item.ordinalidad::text), 50
           )
           AND i.nombre = BTRIM(item.impuesto->>'nombre')
           AND i.porcentaje = (item.impuesto->>'porcentaje')::NUMERIC(7,4)
           AND i.monto = (item.impuesto->>'monto')::NUMERIC(12,2)
        WHERE i.id IS NULL;

        IF impuestos_invalidos > 0 THEN
            RAISE EXCEPTION
                'Migracion cancelada: no se pudo preservar el desglose de % impuestos.',
                impuestos_invalidos;
        END IF;

        ALTER TABLE facturacion DROP COLUMN impuestos_detalle;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_impuestos_factura_parametro
    ON impuestos_factura (parametro_id);

COMMIT;
