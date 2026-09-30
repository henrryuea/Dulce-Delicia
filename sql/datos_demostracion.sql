-- Datos ficticios para probar las pantallas y relaciones de Dulce Delicia.
-- Base nueva: ejecutar despues de esquema.sql y datos_iniciales_catalogo.sql.
-- Base existente: aplicar primero migracion_datos_cliente.sql,
-- migracion_snapshots_documentos.sql y las migraciones pendientes de la app.
-- No crea usuarios ni contrasenas y no modifica filas existentes.
-- Reejecutable: las claves DEMO y las referencias [DEMO-DULCE] evitan duplicados.
-- IMPORTANTE: usar solo en desarrollo/pruebas; crea ventas y movimientos visibles.
-- psql: psql -v ON_ERROR_STOP=1 -d dulce_delicia -f sql/datos_demostracion.sql

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.clientes') IS NULL
       OR to_regclass('public.proveedores') IS NULL
       OR to_regclass('public.productos') IS NULL
       OR to_regclass('public.facturacion') IS NULL
       OR to_regclass('public.detalle_factura') IS NULL
       OR to_regclass('public.pagos_factura') IS NULL
       OR to_regclass('public.comprobantes_pago') IS NULL
       OR to_regclass('public.pagos_factura') IS NULL
       OR to_regclass('public.kardex_movimientos') IS NULL
       OR to_regclass('public.solicitudes') IS NULL
       OR to_regclass('public.logs_actividad') IS NULL THEN
        RAISE EXCEPTION
            'Faltan tablas de la aplicacion; aplica primero esquema.sql y las migraciones.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM parametros WHERE codigo = 'iva' AND activo = TRUE
    ) THEN
        RAISE EXCEPTION
            'No existe un parametro IVA activo; configura los parametros fiscales antes de cargar demostraciones.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM clientes
        WHERE cedula IN ('0000000000', '0000000001', '0000000002', '0000000003')
          AND COALESCE(correo, '') NOT LIKE '%@example.invalid'
    ) THEN
        RAISE EXCEPTION
            'Una identificacion reservada para DEMO ya pertenece a otro cliente; no se insertaron registros.';
    END IF;
END;
$$;

INSERT INTO categorias_producto (nombre)
VALUES ('Muestras de demostracion')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO clientes (
    cedula, nombre, apellido, telefono, correo, tipo_cliente_id, ciudad, direccion
)
SELECT demo.cedula, demo.nombre, demo.apellido, demo.telefono, demo.correo, tipo.id,
       demo.ciudad, demo.direccion
FROM (VALUES
    ('0000000000', 'Cliente Demo', 'Mostrador', '0990000000', 'cliente.demo.01@example.invalid', 'Quito', 'Direccion ficticia 1'),
    ('0000000001', 'Andrea Demo', 'Pasteleria', '0990000001', 'cliente.demo.02@example.invalid', 'Quito', 'Direccion ficticia 2'),
    ('0000000002', 'Mateo Demo', 'Eventos', '0990000002', 'cliente.demo.03@example.invalid', 'Cayambe', 'Direccion ficticia 3'),
    ('0000000003', 'Empresa Demo', 'Muestra', '0990000003', 'empresa.demo@example.invalid', 'Quito', 'Direccion ficticia 4')
) AS demo(cedula, nombre, apellido, telefono, correo, ciudad, direccion)
CROSS JOIN LATERAL (
    SELECT id FROM tipos_cliente
    WHERE nombre = CASE WHEN demo.cedula = '0000000003' THEN 'Empresa' ELSE 'Persona natural' END
    ORDER BY id LIMIT 1
) AS tipo
WHERE NOT EXISTS (SELECT 1 FROM clientes c WHERE c.cedula = demo.cedula);

INSERT INTO proveedores (
    nombre, ruc, categoria_id, persona_contacto, telefono, correo, sitio_web, contacto, estado_id
)
SELECT demo.nombre, NULL, categoria.id, demo.contacto, demo.telefono, demo.correo,
       NULL, demo.contacto, estado.id
FROM (VALUES
    ('DEMO - Insumos de cacao', 'Ingredientes', 'Contacto de muestra cacao', '0991000001', 'cacao.demo@example.invalid', 'Activo'),
    ('DEMO - Empaques artesanales', 'Empaques', 'Contacto de muestra empaques', '0991000002', 'empaques.demo@example.invalid', 'Pendiente'),
    ('DEMO - Materia prima panaderia', 'Insumos de repostería', 'Contacto de muestra panaderia', '0991000003', 'panaderia.demo@example.invalid', 'Activo')
) AS demo(nombre, categoria_nombre, contacto, telefono, correo, estado_nombre)
JOIN categorias_proveedor categoria ON LOWER(categoria.nombre) = LOWER(demo.categoria_nombre)
JOIN estados_proveedor estado ON LOWER(estado.nombre) = LOWER(demo.estado_nombre)
WHERE NOT EXISTS (SELECT 1 FROM proveedores p WHERE p.nombre = demo.nombre);

INSERT INTO productos (
    categoria_producto_id, nombre, precio_base, descripcion, disponible, stock_actual, stock_minimo
)
SELECT categoria.id, demo.nombre, demo.precio, demo.descripcion, TRUE, 0, demo.stock_minimo
FROM (VALUES
    ('DEMO - Torta de chocolate', 24.00::numeric, 'Producto ficticio para pruebas de ventas y reportes.', 3),
    ('DEMO - Cheesecake de maracuya', 26.00::numeric, 'Producto ficticio para pruebas de ventas y reportes.', 2),
    ('DEMO - Caja de galletas', 5.50::numeric, 'Producto ficticio para pruebas de ventas y reportes.', 5),
    ('DEMO - Croissant artesanal', 1.75::numeric, 'Producto ficticio para pruebas de ventas y reportes.', 5)
) AS demo(nombre, precio, descripcion, stock_minimo)
JOIN categorias_producto categoria ON categoria.nombre = 'Muestras de demostracion'
WHERE NOT EXISTS (
    SELECT 1 FROM productos p
    WHERE p.categoria_producto_id = categoria.id AND p.nombre = demo.nombre
);

-- Ingresos iniciales vinculados al Kardex: solo para productos DEMO nuevos.
WITH nuevas_entradas AS (
    INSERT INTO kardex_movimientos (
        producto_id, tipo, cantidad, referencia, descripcion, automatico
    )
    SELECT p.id, 'entrada', datos.cantidad, 'DEMO-INICIAL',
           '[DEMO-DULCE] Existencia inicial ficticia', FALSE
    FROM productos p
    JOIN (VALUES
        ('DEMO - Torta de chocolate', 12),
        ('DEMO - Cheesecake de maracuya', 10),
        ('DEMO - Caja de galletas', 30),
        ('DEMO - Croissant artesanal', 40)
    ) AS datos(nombre, cantidad) ON datos.nombre = p.nombre
    WHERE NOT EXISTS (
        SELECT 1 FROM kardex_movimientos k
        WHERE k.producto_id = p.id AND k.referencia = 'DEMO-INICIAL'
    )
    RETURNING producto_id, cantidad
)
UPDATE productos p
SET stock_actual = p.stock_actual + nuevas_entradas.cantidad
FROM nuevas_entradas
WHERE p.id = nuevas_entradas.producto_id;

INSERT INTO facturacion (
    numero, tipo, cliente_cedula, fecha, validez, subtotal, iva,
    monto, anticipo, saldo_pendiente, estado_id, notas, numero_factura,
    forma_pago, tipo_pago, plazo_meses, total_abonado,
    fecha_entrega, modalidad_entrega, ubicacion_entrega,
    cliente_nombre_snapshot, cliente_apellido_snapshot, cliente_correo_snapshot,
    cliente_telefono_snapshot, cliente_direccion_snapshot, cliente_ciudad_snapshot
)
SELECT venta.numero, venta.tipo, cliente.cedula, CURRENT_DATE - venta.dias_atras,
       CASE WHEN venta.tipo = 'Cotizacion' THEN '15 dias' ELSE '30 dias' END,
       venta.subtotal, calculo.impuesto,
       calculo.total,
       CASE WHEN venta.estado_nombre = 'Pagada' THEN calculo.total ELSE venta.anticipo END,
       CASE WHEN venta.estado_nombre = 'Pagada' THEN 0
            WHEN venta.numero = 'DEMO-FAC-PARCIAL-01' THEN calculo.total - 30
            ELSE calculo.total - venta.anticipo END,
       estado.id, '[DEMO-DULCE] Documento ficticio de demostracion.',
       CASE WHEN venta.estado_nombre = 'Pagada' THEN venta.numero ELSE NULL END,
       venta.metodo_pago, venta.tipo_pago, venta.plazo_meses,
       CASE WHEN venta.estado_nombre = 'Pagada' THEN calculo.total
            WHEN venta.numero = 'DEMO-FAC-PARCIAL-01' THEN 30 ELSE 0 END,
       CURRENT_DATE + venta.dias_entrega, venta.modalidad, venta.ubicacion,
       cliente.nombre, cliente.apellido, cliente.correo, cliente.telefono, cliente.direccion, cliente.ciudad
FROM (VALUES
    ('DEMO-FAC-PAGADA-01', 'Factura', '0000000000', 55.25::numeric, 0.00::numeric, 'Pagada', 'Efectivo', 'contado', 1, 12, 2, 'retiro_local', 'Retiro en local'),
    ('DEMO-FAC-PARCIAL-01', 'Factura', '0000000001', 48.00::numeric, 20.00::numeric, 'Parcial', 'Transferencia bancaria', 'plazos', 2, 5, 3, 'domicilio', 'Entrega de demostracion'),
    ('DEMO-FAC-PAGADA-02', 'Factura', '0000000002', 31.50::numeric, 0.00::numeric, 'Pagada', 'Tarjeta de credito', 'contado', 1, 3, 1, 'retiro_local', 'Retiro en local'),
    ('DEMO-COTIZACION-01', 'Cotizacion', '0000000003', 70.00::numeric, 0.00::numeric, 'En revision', 'Transferencia bancaria', 'contado', 1, 1, 7, 'domicilio', 'Direccion de evento de muestra')
) AS venta(numero, tipo, cedula, subtotal, anticipo, estado_nombre, metodo_pago, tipo_pago,
           plazo_meses, dias_atras, dias_entrega, modalidad, ubicacion)
JOIN clientes cliente ON cliente.cedula = venta.cedula
JOIN estados_documento estado ON LOWER(estado.nombre) = LOWER(venta.estado_nombre)
CROSS JOIN LATERAL (
    SELECT codigo, nombre, valor, descripcion FROM parametros
    WHERE activo = TRUE AND LOWER(codigo) = 'iva'
    ORDER BY id LIMIT 1
) tasa
CROSS JOIN LATERAL (
    SELECT ROUND(venta.subtotal * tasa.valor / 100, 2) AS impuesto,
           venta.subtotal + ROUND(venta.subtotal * tasa.valor / 100, 2) AS total
) calculo
WHERE NOT EXISTS (
    SELECT 1 FROM facturacion f WHERE f.numero = venta.numero
);

INSERT INTO impuestos_factura (
    factura_numero, orden, parametro_id, codigo, nombre, descripcion, porcentaje, monto
)
SELECT venta.numero, 1, tasa.id, tasa.codigo, tasa.nombre, tasa.descripcion,
       tasa.valor, ROUND(venta.subtotal * tasa.valor / 100, 2)
FROM facturacion venta
CROSS JOIN LATERAL (
    SELECT id, codigo, nombre, valor, descripcion FROM parametros
    WHERE activo = TRUE AND LOWER(codigo) = 'iva'
    ORDER BY id LIMIT 1
) tasa
WHERE venta.numero LIKE 'DEMO-%'
ON CONFLICT (factura_numero, orden) DO NOTHING;

INSERT INTO detalle_factura (
    factura_numero, producto_id, nombre_producto, cantidad, precio_base, ajuste, total,
    descripcion_linea, unidad_medida, es_adicional
)
SELECT venta.numero, p.id, p.nombre, linea.cantidad, p.precio_base, 0,
       ROUND(p.precio_base * linea.cantidad, 2), linea.descripcion, 'unidad', FALSE
FROM (VALUES
    ('DEMO-FAC-PAGADA-01', 'DEMO - Torta de chocolate', 2.000::numeric, 'Decoracion de muestra'),
    ('DEMO-FAC-PAGADA-01', 'DEMO - Caja de galletas', 1.000::numeric, 'Presentacion de muestra'),
    ('DEMO-FAC-PAGADA-01', 'DEMO - Croissant artesanal', 1.000::numeric, 'Complemento de muestra'),
    ('DEMO-FAC-PARCIAL-01', 'DEMO - Cheesecake de maracuya', 1.000::numeric, 'Pedido personalizado de muestra'),
    ('DEMO-FAC-PARCIAL-01', 'DEMO - Caja de galletas', 4.000::numeric, 'Empaque de muestra'),
    ('DEMO-FAC-PAGADA-02', 'DEMO - Croissant artesanal', 18.000::numeric, 'Bandeja de muestra'),
    ('DEMO-COTIZACION-01', 'DEMO - Torta de chocolate', 2.000::numeric, 'Cotizacion ficticia'),
    ('DEMO-COTIZACION-01', 'DEMO - Caja de galletas', 4.000::numeric, 'Cotizacion ficticia')
) AS linea(numero, producto_nombre, cantidad, descripcion)
JOIN facturacion venta ON venta.numero = linea.numero
JOIN productos p ON p.nombre = linea.producto_nombre
WHERE NOT EXISTS (
    SELECT 1 FROM detalle_factura d
    WHERE d.factura_numero = venta.numero AND d.producto_id = p.id
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM productos p
        JOIN (
            SELECT d.producto_id, SUM(d.cantidad)::integer AS cantidad
            FROM detalle_factura d
            JOIN facturacion f ON f.numero = d.factura_numero
            WHERE f.tipo = 'Factura'
              AND f.numero LIKE 'DEMO-FAC-%'
              AND d.es_adicional = FALSE
              AND d.cantidad = TRUNC(d.cantidad)
              AND NOT EXISTS (
                  SELECT 1 FROM kardex_movimientos k
                  WHERE k.producto_id = d.producto_id
                    AND k.factura_numero = d.factura_numero
                    AND k.tipo = 'salida' AND k.automatico = TRUE
              )
            GROUP BY d.producto_id
        ) pendiente ON pendiente.producto_id = p.id
        WHERE p.stock_actual < pendiente.cantidad
    ) THEN
        RAISE EXCEPTION
            'Stock insuficiente para crear las salidas Kardex de demostracion; no se aplicaron cambios.';
    END IF;
END;
$$;

-- Crear pagos parciales y liquidaciones con saldo coherente.
WITH pago_datos AS (
    SELECT f.numero, f.monto, f.fecha, f.forma_pago,
           CASE WHEN f.numero = 'DEMO-FAC-PARCIAL-01' THEN 20.00::numeric ELSE f.monto END AS primer_pago
    FROM facturacion f
    WHERE f.numero IN ('DEMO-FAC-PAGADA-01', 'DEMO-FAC-PARCIAL-01', 'DEMO-FAC-PAGADA-02')
), orden_pagos AS (
    SELECT numero, fecha, forma_pago, monto, 1 AS numero_pago,
           primer_pago AS pago, monto AS saldo_anterior,
           monto - primer_pago AS saldo_posterior, primer_pago AS acumulado
    FROM pago_datos
    UNION ALL
    SELECT numero, fecha, forma_pago, monto, 2,
           10.00::numeric, monto - primer_pago,
           monto - primer_pago - 10.00, primer_pago + 10.00
    FROM pago_datos WHERE numero = 'DEMO-FAC-PARCIAL-01'
), inserciones AS (
    INSERT INTO pagos_factura (
        factura_numero, numero_pago, monto, fecha, metodo_pago, referencia,
        saldo_anterior, saldo_posterior, total_acumulado, registrado_por, notas
    )
    SELECT orden.numero, orden.numero_pago, orden.pago, orden.fecha,
           orden.forma_pago, '[DEMO-DULCE] Pago de demostracion',
           orden.saldo_anterior, orden.saldo_posterior, orden.acumulado,
           'DEMO', '[DEMO-DULCE] Registro ficticio'
    FROM orden_pagos orden
    WHERE NOT EXISTS (
        SELECT 1 FROM pagos_factura p
        WHERE p.factura_numero = orden.numero AND p.numero_pago = orden.numero_pago
    )
    RETURNING id, factura_numero, monto, fecha, saldo_posterior, total_acumulado
)
INSERT INTO comprobantes_pago (
    numero_comprobante, pago_id, factura_numero, cliente_cedula, fecha,
    monto_abonado, total_deuda, total_acumulado_pagado, saldo_pendiente,
    cliente_nombre_snapshot, cliente_apellido_snapshot, cliente_correo_snapshot,
    cliente_telefono_snapshot, cliente_direccion_snapshot, cliente_ciudad_snapshot,
    observaciones
)
SELECT 'DEMO-' || LPAD(inserciones.id::text, 8, '0'), inserciones.id, inserciones.factura_numero,
       f.cliente_cedula, inserciones.fecha, inserciones.monto, f.monto,
       inserciones.total_acumulado, inserciones.saldo_posterior,
       f.cliente_nombre_snapshot, f.cliente_apellido_snapshot, f.cliente_correo_snapshot,
       f.cliente_telefono_snapshot, f.cliente_direccion_snapshot, f.cliente_ciudad_snapshot,
       '[DEMO-DULCE] Recibo ficticio; no valido como comprobante tributario.'
FROM inserciones
JOIN facturacion f ON f.numero = inserciones.factura_numero
WHERE NOT EXISTS (
    SELECT 1 FROM comprobantes_pago c WHERE c.pago_id = inserciones.id
);

-- Las salidas Kardex solo se agregan a las ventas de ejemplo (no a cotizaciones).
WITH salidas AS (
    INSERT INTO kardex_movimientos (
        producto_id, tipo, cantidad, referencia, descripcion, automatico, factura_numero
    )
    SELECT p.id, 'salida', detalle.cantidad::integer, '[DEMO-DULCE] Venta de demostracion',
           '[DEMO-DULCE] Salida de inventario ligada a la venta ficticia.',
           TRUE, detalle.factura_numero
    FROM detalle_factura detalle
    JOIN facturacion f ON f.numero = detalle.factura_numero AND f.tipo = 'Factura'
    JOIN productos p ON p.id = detalle.producto_id
    WHERE detalle.factura_numero LIKE 'DEMO-FAC-%'
      AND detalle.es_adicional = FALSE
      AND detalle.cantidad = TRUNC(detalle.cantidad)
      AND NOT EXISTS (
          SELECT 1 FROM kardex_movimientos k
          WHERE k.producto_id = p.id AND k.factura_numero = detalle.factura_numero
            AND k.tipo = 'salida' AND k.automatico = TRUE
      )
    RETURNING producto_id, cantidad
)
UPDATE productos p
SET stock_actual = p.stock_actual - salidas.cantidad
FROM salidas
WHERE p.id = salidas.producto_id
  AND p.stock_actual >= salidas.cantidad;

INSERT INTO cuotas_factura (
    factura_numero, numero_pago, valor_pago, fecha_vencimiento,
    monto_pagado, saldo_pago, estado
)
SELECT f.numero, pago.numero, valor_pago.valor,
       (f.fecha + (pago.numero || ' month')::interval)::date,
       0, valor_pago.valor, 'Pendiente'
FROM facturacion f
CROSS JOIN (VALUES (1), (2)) AS pago(numero)
 CROSS JOIN LATERAL (
     SELECT CASE WHEN pago.numero = 1 THEN ROUND(f.saldo_pendiente / 2, 2)
                 ELSE f.saldo_pendiente - ROUND(f.saldo_pendiente / 2, 2) END AS valor
 ) valor_pago
WHERE f.numero = 'DEMO-FAC-PARCIAL-01'
  AND NOT EXISTS (
      SELECT 1 FROM cuotas_factura c
      WHERE c.factura_numero = f.numero AND c.numero_pago = pago.numero
  );

INSERT INTO solicitudes (nombre, correo, telefono, tipo_producto, mensaje, fecha, estado, respuesta_cliente)
SELECT demo.nombre, demo.correo, demo.telefono, demo.tipo_producto, demo.mensaje,
       CURRENT_TIMESTAMP - demo.dias_atras * INTERVAL '1 day', demo.estado, demo.respuesta
FROM (VALUES
    ('Solicitud Demo Uno', 'solicitud.demo.01@example.invalid', '0992000001', 'Torta personalizada', 'Consulta ficticia para revisar el flujo de solicitudes.', 1, 'Pendiente', NULL::text),
    ('Solicitud Demo Dos', 'solicitud.demo.02@example.invalid', '0992000002', 'Mesa dulce', 'Pedido ficticio para un evento de demostracion.', 2, 'Confirmado', 'Estamos preparando la propuesta de muestra.'),
    ('Solicitud Demo Tres', 'solicitud.demo.03@example.invalid', '0992000003', 'Caja de postres', 'Solicitud ficticia para completar el tablero.', 3, 'En preparación', 'Pedido de demostracion en preparacion; no contactar.')
) AS demo(nombre, correo, telefono, tipo_producto, mensaje, dias_atras, estado, respuesta)
WHERE NOT EXISTS (
    SELECT 1 FROM solicitudes s WHERE s.correo = demo.correo
);

INSERT INTO logs_actividad (usuario_id, usuario_nombre, accion, ip, detalles)
SELECT NULL, 'DEMO', demo.accion, '127.0.0.1', demo.detalles
FROM (VALUES
    ('DEMO_CARGA', '[DEMO-DULCE] Se cargaron registros ficticios de muestra.'),
    ('DEMO_INVENTARIO', '[DEMO-DULCE] Se registraron entradas iniciales de inventario.'),
    ('DEMO_VENTAS', '[DEMO-DULCE] Se registraron ventas, pagos y cotizacion ficticios.')
) AS demo(accion, detalles)
WHERE NOT EXISTS (
    SELECT 1 FROM logs_actividad l
    WHERE l.usuario_nombre = 'DEMO' AND l.accion = demo.accion
      AND l.detalles = demo.detalles
);

DO $$
BEGIN
    IF (
        SELECT COUNT(*) FROM facturacion
        WHERE numero IN (
            'DEMO-FAC-PAGADA-01', 'DEMO-FAC-PARCIAL-01',
            'DEMO-FAC-PAGADA-02', 'DEMO-COTIZACION-01'
        )
    ) <> 4 THEN
        RAISE EXCEPTION 'No se crearon los cuatro documentos demostrativos esperados.';
    END IF;

    IF EXISTS (
        SELECT f.numero
        FROM facturacion f
        LEFT JOIN detalle_factura d ON d.factura_numero = f.numero
        WHERE f.numero LIKE 'DEMO-%'
        GROUP BY f.numero, f.subtotal
        HAVING ROUND(COALESCE(SUM(d.total), 0), 2) <> f.subtotal
    ) THEN
        RAISE EXCEPTION 'El subtotal de algun documento DEMO no coincide con sus lineas.';
    END IF;

    IF EXISTS (
        SELECT f.numero
        FROM facturacion f
        LEFT JOIN pagos_factura p ON p.factura_numero = f.numero
        WHERE f.numero LIKE 'DEMO-FAC-%'
        GROUP BY f.numero, f.total_abonado
        HAVING ROUND(COALESCE(SUM(p.monto), 0), 2) <> f.total_abonado
    ) THEN
        RAISE EXCEPTION 'Los pagos registrados no coinciden con el total abonado del documento.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM productos WHERE nombre LIKE 'DEMO - %' AND stock_actual < 0
    ) THEN
        RAISE EXCEPTION 'El inventario demostrativo no puede quedar negativo.';
    END IF;
END;
$$;

COMMIT;
