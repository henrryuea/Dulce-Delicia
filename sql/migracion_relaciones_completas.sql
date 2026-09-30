-- =============================================================================
-- MIGRACIÓN: MODELO RELACIONAL COMPLETO (Nexo de Dulce Delicia)
-- =============================================================================
-- `usuarios`, `productos`, `clientes`, `proveedores` y `facturacion` son las
-- tablas nexo. Esta migración cierra las relaciones que quedaban sueltas para
-- que NINGUNA tabla quede fuera del modelo:
--
--   usuarios ──< roles / permisos / clientes / facturacion / pagos_factura
--           ──< solicitudes / solicitudes_acceso / logs_actividad
--           ──< kardex_movimientos
--   parametros ──< facturacion.iva_id , detalle_factura.iva_id
--   categorias_producto ──< productos ──< detalle_factura
--                    └──< solicitudes.categoria_producto_id
--   proveedores ──< productos (proveedor del insumo)
--   facturacion ──< detalle_factura / pagos_factura / cuotas_factura
--              ──< comprobantes_pago / kardex_movimientos
--   pagos_factura ──< comprobantes_pago / aplicaciones_pago
--
-- Equivalencias con el modelo de referencia: donde allí aparecen `servicios`
-- y `tipos_servicio`, aquí el catálogo es `productos` y `categorias_producto`.
-- Donde aparece `solicitudes.resuelto_por_id`, aquí es `entregado_por_id`.
--
-- Es idempotente: puede ejecutarse varias veces sin efectos adversos.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Columnas que enlazan cada tabla con su tabla nexo
-- -----------------------------------------------------------------------------

-- El usuario registrado (rol Cliente) queda ligado a su ficha de clientes.
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS usuario_id INTEGER;

-- Quién emite el documento y quién registra cada pago.
ALTER TABLE facturacion ADD COLUMN IF NOT EXISTS usuario_id INTEGER;
ALTER TABLE pagos_factura ADD COLUMN IF NOT EXISTS usuario_id INTEGER;

-- Tasa de IVA aplicada, relacionada con el parámetro que la define.
ALTER TABLE facturacion ADD COLUMN IF NOT EXISTS iva_id INTEGER;
ALTER TABLE detalle_factura ADD COLUMN IF NOT EXISTS iva_id INTEGER;
ALTER TABLE detalle_factura ADD COLUMN IF NOT EXISTS iva_valor NUMERIC(7,4);

-- Quién realizó la solicitud y a qué categoría de producto corresponde.
ALTER TABLE solicitudes ADD COLUMN IF NOT EXISTS usuario_id INTEGER;
ALTER TABLE solicitudes ADD COLUMN IF NOT EXISTS categoria_producto_id INTEGER;

-- Proveedor que suministra el insumo.
ALTER TABLE productos ADD COLUMN IF NOT EXISTS proveedor_id INTEGER;

-- -----------------------------------------------------------------------------
-- 2. Carga de los enlaces que sí se pueden deducir de los datos existentes
-- -----------------------------------------------------------------------------

-- Cliente registrado: se une por correo, que es la única clave común.
UPDATE clientes c
SET usuario_id = u.id
FROM usuarios u
WHERE c.usuario_id IS NULL
  AND u.correo IS NOT NULL
  AND LOWER(TRIM(u.correo)) = LOWER(TRIM(c.correo));

-- Pago registrado: se une por el nombre de usuario guardado en la auditoría.
UPDATE pagos_factura p
SET usuario_id = u.id
FROM usuarios u
WHERE p.usuario_id IS NULL
  AND p.registrado_por IS NOT NULL
  AND LOWER(TRIM(u.usuario)) = LOWER(TRIM(p.registrado_por));

-- IVA: el documento y sus líneas quedan ligados al parámetro vigente.
UPDATE facturacion f
SET iva_id = pa.id
FROM parametros pa
WHERE f.iva_id IS NULL AND pa.codigo = 'iva';

UPDATE detalle_factura d
SET iva_id = pa.id,
    iva_valor = COALESCE(d.iva_valor, pa.valor)
FROM parametros pa, facturacion f
WHERE d.iva_id IS NULL
  AND pa.codigo = 'iva'
  AND f.numero = d.factura_numero;

-- Solicitud dentro del sistema: se une por correo del solicitante.
UPDATE solicitudes s
SET usuario_id = u.id
FROM usuarios u
WHERE s.usuario_id IS NULL
  AND s.correo IS NOT NULL
  AND LOWER(TRIM(u.correo)) = LOWER(TRIM(s.correo));

-- Categoría del producto solicitado: se resuelve por el texto ya capturado.
UPDATE solicitudes s
SET categoria_producto_id = cp.id
FROM categorias_producto cp
WHERE s.categoria_producto_id IS NULL
  AND s.tipo_producto IS NOT NULL
  AND LOWER(TRIM(cp.nombre)) = LOWER(TRIM(s.tipo_producto));

-- -----------------------------------------------------------------------------
-- 3. Claves foráneas: cada tabla queda relacionada con su nexo
-- -----------------------------------------------------------------------------

DO $$
DECLARE
    vinculo TEXT;
    tabla TEXT;
    columna TEXT;
    tabla_ref TEXT;
    columna_ref TEXT;
    regla TEXT;
    nombre TEXT;
BEGIN
    FOREACH vinculo IN ARRAY ARRAY[
        'clientes.usuario_id|usuarios.id|SET NULL',
        'facturacion.usuario_id|usuarios.id|SET NULL',
        'facturacion.iva_id|parametros.id|SET NULL',
        'pagos_factura.usuario_id|usuarios.id|SET NULL',
        'detalle_factura.iva_id|parametros.id|SET NULL',
        'solicitudes.usuario_id|usuarios.id|SET NULL',
        'solicitudes.categoria_producto_id|categorias_producto.id|SET NULL',
        'productos.proveedor_id|proveedores.id|SET NULL'
    ] LOOP
        tabla := split_part(split_part(vinculo, '|', 1), '.', 1);
        columna := split_part(split_part(vinculo, '|', 1), '.', 2);
        tabla_ref := split_part(split_part(vinculo, '|', 2), '.', 1);
        columna_ref := split_part(split_part(vinculo, '|', 2), '.', 2);
        regla := split_part(vinculo, '|', 3);
        nombre := 'fk_' || tabla || '_' || columna;

        -- Solo se crea la clave si todavía no existe: la migración es reejecutable.
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = tabla::regclass AND conname = nombre
        ) THEN
            CONTINUE;
        END IF;

        EXECUTE format(
            'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES %I(%I) ON DELETE %s',
            tabla, nombre, columna, tabla_ref, columna_ref, regla
        );
    END LOOP;
END $$;

-- -----------------------------------------------------------------------------
-- 4. Índices de apoyo para que las relaciones sean rápidas
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_clientes_usuario ON clientes (usuario_id);
CREATE INDEX IF NOT EXISTS idx_facturacion_usuario ON facturacion (usuario_id);
CREATE INDEX IF NOT EXISTS idx_facturacion_cliente ON facturacion (cliente_cedula);
CREATE INDEX IF NOT EXISTS idx_pagos_usuario ON pagos_factura (usuario_id);
CREATE INDEX IF NOT EXISTS idx_detalle_producto ON detalle_factura (producto_id);
CREATE INDEX IF NOT EXISTS idx_detalle_iva ON detalle_factura (iva_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_usuario ON solicitudes (usuario_id);
CREATE INDEX IF NOT EXISTS idx_productos_proveedor ON productos (proveedor_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_usuario_unico
    ON clientes (usuario_id) WHERE usuario_id IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 5. Reglas de integridad que el código de la aplicación ya respeta
-- -----------------------------------------------------------------------------

-- Un usuario solo puede tener una ficha de cliente.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM clientes WHERE usuario_id IS NOT NULL
        GROUP BY usuario_id HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Hay fichas de cliente duplicadas para el mismo usuario';
    END IF;
END $$;

-- Los estados que la aplicación admite para una solicitud.
ALTER TABLE solicitudes DROP CONSTRAINT IF EXISTS chk_solicitudes_estado;
ALTER TABLE solicitudes ADD CONSTRAINT chk_solicitudes_estado CHECK (
    estado IN ('Pendiente', 'Confirmado', 'En preparación', 'Listo para retiro',
               'En reparto', 'Entregada', 'Cancelada')
);

-- El IVA se guarda como porcentaje válido.
ALTER TABLE detalle_factura DROP CONSTRAINT IF EXISTS chk_detalle_iva_valor;
ALTER TABLE detalle_factura ADD CONSTRAINT chk_detalle_iva_valor
    CHECK (iva_valor IS NULL OR (iva_valor >= 0 AND iva_valor <= 100));
