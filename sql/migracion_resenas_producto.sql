-- Reseñas y calificaciones (1 a 5 estrellas) que los clientes dejan sobre
-- los productos comprados. Se relaciona con clientes y productos; un cliente
-- puede editar su propia reseña de un producto pero no duplicarla.
-- El backend también autoaplica esta tabla al vuelo (asegurar_resenas en
-- app.py), pero este archivo documenta el cambio para bases nuevas.

CREATE TABLE IF NOT EXISTS resenas_producto (
    id SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    cliente_cedula VARCHAR(20) NOT NULL
        REFERENCES clientes(cedula) ON UPDATE CASCADE ON DELETE CASCADE,
    calificacion SMALLINT NOT NULL CHECK (calificacion BETWEEN 1 AND 5),
    comentario TEXT,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resena_producto_cliente UNIQUE (producto_id, cliente_cedula)
);

CREATE INDEX IF NOT EXISTS idx_resenas_producto_producto
    ON resenas_producto (producto_id);
