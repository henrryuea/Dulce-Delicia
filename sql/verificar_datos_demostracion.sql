-- Ejecutar despues de datos_demostracion.sql para revisar el conjunto ficticio.

SELECT 'Clientes de demostracion' AS seccion, COUNT(*) AS registros
FROM clientes
WHERE correo LIKE '%@example.invalid'
UNION ALL
SELECT 'Proveedores de demostracion', COUNT(*)
FROM proveedores
WHERE nombre LIKE 'DEMO - %'
UNION ALL
SELECT 'Productos de demostracion', COUNT(*)
FROM productos
WHERE nombre LIKE 'DEMO - %'
UNION ALL
SELECT 'Documentos de venta y cotizacion', COUNT(*)
FROM facturacion
WHERE numero LIKE 'DEMO-%'
UNION ALL
SELECT 'Lineas de documento', COUNT(*)
FROM detalle_factura
WHERE factura_numero LIKE 'DEMO-%'
UNION ALL
SELECT 'Pagos de demostracion', COUNT(*)
FROM pagos_factura
WHERE factura_numero LIKE 'DEMO-FAC-%'
UNION ALL
SELECT 'Recibos de demostracion', COUNT(*)
FROM comprobantes_pago
WHERE observaciones LIKE '[DEMO-DULCE]%'
UNION ALL
SELECT 'Cuotas de demostracion', COUNT(*)
FROM cuotas_factura
WHERE factura_numero = 'DEMO-FAC-PARCIAL-01'
UNION ALL
SELECT 'Movimientos Kardex de demostracion', COUNT(*)
FROM kardex_movimientos
WHERE referencia LIKE '%DEMO%' OR descripcion LIKE '%[DEMO-DULCE]%'
UNION ALL
SELECT 'Solicitudes de demostracion', COUNT(*)
FROM solicitudes
WHERE correo LIKE '%@example.invalid'
UNION ALL
SELECT 'Eventos de auditoria de demostracion', COUNT(*)
FROM logs_actividad
WHERE usuario_nombre = 'DEMO' AND detalles LIKE '[DEMO-DULCE]%';

WITH detalle_totales AS (
    SELECT factura_numero, SUM(total) AS suma_detalles
    FROM detalle_factura
    WHERE factura_numero LIKE 'DEMO-%'
    GROUP BY factura_numero
), pago_totales AS (
    SELECT factura_numero, SUM(monto) AS suma_pagos
    FROM pagos_factura
    WHERE factura_numero LIKE 'DEMO-FAC-%'
    GROUP BY factura_numero
)
SELECT f.numero, f.tipo, e.nombre AS estado, f.subtotal, f.iva, f.monto,
       f.total_abonado, f.saldo_pendiente,
       COALESCE(d.suma_detalles, 0) AS suma_detalles,
       COALESCE(p.suma_pagos, 0) AS suma_pagos
FROM facturacion f
JOIN estados_documento e ON e.id = f.estado_id
LEFT JOIN detalle_totales d ON d.factura_numero = f.numero
LEFT JOIN pago_totales p ON p.factura_numero = f.numero
WHERE f.numero LIKE 'DEMO-%'
ORDER BY f.fecha, f.numero;

SELECT p.nombre, p.stock_actual, p.stock_minimo,
       COALESCE(SUM(k.cantidad) FILTER (WHERE k.tipo = 'entrada'), 0) AS entradas_kardex,
       COALESCE(SUM(k.cantidad) FILTER (WHERE k.tipo = 'salida'), 0) AS salidas_kardex
FROM productos p
LEFT JOIN kardex_movimientos k ON k.producto_id = p.id
WHERE p.nombre LIKE 'DEMO - %'
GROUP BY p.id, p.nombre, p.stock_actual, p.stock_minimo
ORDER BY p.nombre;
