-- Catalogo de demostracion para Dulce Delicia.
-- Los 10 productos disponibles son solo datos de prueba: precios referenciales,
-- no inventario comercial confirmado. Confirmar datos antes de vender.
-- Los otros 10 productos quedan como proximos lanzamientos.
-- Idempotente: puede ejecutarse mas de una vez sin duplicar categorias/productos.
BEGIN;

INSERT INTO categorias_producto (nombre) VALUES
    ('Pasteles y tartas'),
    ('Panes artesanales'),
    ('Postres individuales'),
    ('Galletas y bocaditos'),
    ('Cafés y bebidas'),
    ('Catering y mesas dulces')
ON CONFLICT (nombre) DO NOTHING;

CREATE TEMPORARY TABLE catalogo_inicial_pruebas (
    categoria TEXT NOT NULL,
    nombre TEXT NOT NULL,
    precio NUMERIC(12, 2) NOT NULL,
    descripcion TEXT NOT NULL,
    disponible BOOLEAN NOT NULL
) ON COMMIT DROP;

INSERT INTO catalogo_inicial_pruebas (categoria, nombre, precio, descripcion, disponible) VALUES
    ('Pasteles y tartas', 'Torta húmeda de chocolate', 24.00,
     'Torta de chocolate húmeda para compartir, presentación referencial de 12 porciones. Precio de muestra; confirmar tamaño y precio antes de ofrecer.', TRUE),
    ('Pasteles y tartas', 'Torta tres leches', 22.00,
     'Bizcocho suave bañado en tres leches y cubierto con crema, presentación referencial de 12 porciones. Precio de muestra; confirmar tamaño y precio antes de ofrecer.', FALSE),
    ('Pasteles y tartas', 'Cheesecake de maracuyá', 26.00,
     'Tarta cremosa de queso con cubierta de maracuyá, presentación referencial de 10 porciones. Precio de muestra; confirmar tamaño y precio antes de ofrecer.', TRUE),
    ('Pasteles y tartas', 'Torta red velvet', 28.00,
     'Bizcocho red velvet con relleno cremoso, presentación referencial de 12 porciones. Precio de muestra; confirmar tamaño y precio antes de ofrecer.', FALSE),
    ('Panes artesanales', 'Pan de yuca (6 unidades)', 3.50,
     'Seis panes de yuca horneados, ideales para compartir en desayunos o meriendas. Precio de muestra; confirmar receta y disponibilidad antes de ofrecer.', FALSE),
    ('Panes artesanales', 'Croissant de mantequilla', 1.75,
     'Croissant individual de masa hojaldrada y mantequilla. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', TRUE),
    ('Panes artesanales', 'Pan integral artesanal', 4.50,
     'Pan integral de elaboración artesanal, presentación referencial de 500 gramos. Precio de muestra; confirmar peso y precio antes de ofrecer.', TRUE),
    ('Panes artesanales', 'Pan de masa madre', 5.00,
     'Pan de fermentación lenta con corteza crujiente, presentación referencial de 500 gramos. Precio de muestra; confirmar peso y precio antes de ofrecer.', TRUE),
    ('Panes artesanales', 'Enrollado de queso', 1.50,
     'Enrollado individual de masa suave relleno de queso. Precio de muestra; confirmar receta y disponibilidad antes de ofrecer.', TRUE),
    ('Postres individuales', 'Mousse de chocolate', 4.25,
     'Porción individual de mousse de chocolate con textura aireada. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', TRUE),
    ('Postres individuales', 'Tiramisú de café', 4.75,
     'Postre individual con capas de bizcocho, crema y sabor a café. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', FALSE),
    ('Postres individuales', 'Flan de vainilla', 3.25,
     'Flan individual de vainilla con caramelo. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', FALSE),
    ('Postres individuales', 'Brownie con nueces', 3.00,
     'Brownie individual de chocolate con nueces. Precio de muestra; confirmar receta y disponibilidad antes de ofrecer.', FALSE),
    ('Postres individuales', 'Cheesecake individual de frutos rojos', 4.50,
     'Porción individual de cheesecake con frutos rojos. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', TRUE),
    ('Galletas y bocaditos', 'Galletas con chispas de chocolate (6 unidades)', 5.50,
     'Seis galletas horneadas con chispas de chocolate. Precio de muestra; confirmar tamaño y precio antes de ofrecer.', TRUE),
    ('Galletas y bocaditos', 'Alfajor artesanal', 1.75,
     'Alfajor individual relleno de dulce de leche. Precio de muestra; confirmar receta y disponibilidad antes de ofrecer.', FALSE),
    ('Cafés y bebidas', 'Café americano', 2.00,
     'Taza de café americano recién preparado. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', TRUE),
    ('Cafés y bebidas', 'Capuchino', 3.00,
     'Café espresso con leche vaporizada y espuma. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', FALSE),
    ('Cafés y bebidas', 'Chocolate caliente', 3.25,
     'Bebida caliente de chocolate preparada al momento. Precio de muestra; confirmar tamaño y disponibilidad antes de ofrecer.', FALSE),
    ('Catering y mesas dulces', 'Bocados salados para eventos (25 unidades)', 24.00,
     'Selección surtida de bocados salados para reuniones y eventos, presentación referencial de 25 unidades. Precio de muestra; confirmar menú, cantidad y precio antes de ofrecer.', FALSE);

INSERT INTO productos (
    categoria_producto_id, nombre, precio_base, imagen, descripcion, disponible
)
SELECT
    categoria.id,
    catalogo.nombre,
    catalogo.precio,
    NULL,
    catalogo.descripcion,
    catalogo.disponible
FROM catalogo_inicial_pruebas AS catalogo
JOIN categorias_producto AS categoria ON categoria.nombre = catalogo.categoria
WHERE NOT EXISTS (
    SELECT 1
    FROM productos AS existente
    WHERE existente.categoria_producto_id = categoria.id
      AND LOWER(TRIM(existente.nombre)) = LOWER(TRIM(catalogo.nombre))
);

UPDATE productos AS producto
SET disponible = catalogo.disponible
FROM catalogo_inicial_pruebas AS catalogo
JOIN categorias_producto AS categoria ON categoria.nombre = catalogo.categoria
WHERE producto.categoria_producto_id = categoria.id
  AND LOWER(TRIM(producto.nombre)) = LOWER(TRIM(catalogo.nombre));

COMMIT;
