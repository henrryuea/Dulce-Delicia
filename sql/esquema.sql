-- ==============================================================================
-- PROYECTO: DULCE DELICIA - ESQUEMA DE LA BASE DE DATOS (PostgreSQL)
-- ==============================================================================
-- Inicializa una base vacía con el esquema operativo y datos de referencia.
-- Catalogo opcional: sql/datos_iniciales_catalogo.sql.
-- Para poblar pantallas con ventas/inventario ficticios (solo desarrollo):
-- primero aplica las migraciones vigentes y luego sql/datos_demostracion.sql.
-- Usa sql/verificar_datos_demostracion.sql para revisar cantidades y saldos.
--
-- Uso en pgAdmin:  crear la base 'dulce_delicia', abrir el Query Tool sobre ella,
--                  pegar este archivo y ejecutar (F5).
-- Uso en terminal: psql -U postgres -d dulce_delicia -f sql/esquema.sql
--
-- Todas las tablas tienen PRIMARY KEY y las relaciones se establecen con
-- FOREIGN KEY, garantizando la integridad referencial del modelo.
-- ==============================================================================

BEGIN;
 
-- ============================
-- CREACIÓN DE TABLAS
-- ============================
 
CREATE TABLE tipos_cliente (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);
 
CREATE TABLE clientes (
    id SERIAL UNIQUE,
    cedula VARCHAR(20) PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    telefono VARCHAR(20) NOT NULL,
    correo VARCHAR(150) NOT NULL,
    tipo_cliente_id INT REFERENCES tipos_cliente(id),
    ciudad VARCHAR(100) NOT NULL,
    apellido VARCHAR(100),
    direccion VARCHAR(300)
);
 
CREATE TABLE categorias_producto (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);
 
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    categoria_producto_id INT NOT NULL REFERENCES categorias_producto(id),
    nombre VARCHAR(150) NOT NULL,
    precio_base NUMERIC(12,2) NOT NULL CHECK (precio_base > 0),
    imagen TEXT,
    descripcion TEXT NOT NULL,
    disponible BOOLEAN NOT NULL DEFAULT TRUE,
    stock_actual INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 0,
    es_insumo BOOLEAN NOT NULL DEFAULT FALSE
);
 
CREATE TABLE estados_proveedor (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);
 
CREATE TABLE categorias_proveedor (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);
 
CREATE TABLE proveedores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    ruc VARCHAR(13),
    categoria_id INT NOT NULL REFERENCES categorias_proveedor(id),
    persona_contacto VARCHAR(150),
    telefono VARCHAR(30),
    correo VARCHAR(150),
    sitio_web VARCHAR(300),
    contacto VARCHAR(150) NOT NULL,
    estado_id INT NOT NULL REFERENCES estados_proveedor(id)
);
 
-- =============================================================================
-- =============================================================================

-- -----------------------------------------------------------------------------
-- CATÁLOGOS MAESTROS
-- -----------------------------------------------------------------------------

CREATE TABLE estados_documento (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE parametros (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    valor NUMERIC(7,4) NOT NULL CHECK (valor >= 0 AND valor <= 100),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    descripcion VARCHAR(300),
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO parametros (codigo, nombre, valor, descripcion)
VALUES ('iva', 'IVA', 15, 'Porcentaje tributario aplicado a las ventas');
 
CREATE TABLE facturacion (
    id SERIAL PRIMARY KEY,
    numero VARCHAR(30) UNIQUE NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    cliente_cedula VARCHAR(20) NOT NULL REFERENCES clientes(cedula) ON UPDATE CASCADE,
    fecha DATE NOT NULL,
    validez VARCHAR(50),
    subtotal NUMERIC(12,2),
    iva NUMERIC(12,2),
    impuestos_detalle JSONB NOT NULL DEFAULT '[]'::jsonb,
    monto NUMERIC(12,2) NOT NULL,
    anticipo NUMERIC(12,2) DEFAULT 0,
    saldo_pendiente NUMERIC(12,2) DEFAULT 0,
    estado_id INT NOT NULL REFERENCES estados_documento(id),
    notas TEXT,
    numero_factura VARCHAR(30) UNIQUE,
    forma_pago VARCHAR(100) DEFAULT 'Transferencia bancaria',
    tipo_pago VARCHAR(20) DEFAULT 'contado',
    plazo_meses INT DEFAULT 1,
    total_abonado NUMERIC(12,2) DEFAULT 0,
    cliente_nombre_snapshot VARCHAR(150),
    cliente_apellido_snapshot VARCHAR(100),
    cliente_correo_snapshot VARCHAR(150),
    cliente_telefono_snapshot VARCHAR(20),
    cliente_direccion_snapshot VARCHAR(300),
    cliente_ciudad_snapshot VARCHAR(100),
    fecha_entrega DATE,
    modalidad_entrega VARCHAR(20),
    ubicacion_entrega TEXT,
    CONSTRAINT ck_facturacion_modalidad_entrega
        CHECK (modalidad_entrega IS NULL OR modalidad_entrega IN ('domicilio', 'retiro_local')),
    proxima_pago_fecha DATE,
    proxima_pago_monto NUMERIC(12,2)
);

-- Clave candidata para validar en comprobantes la pareja factura/cliente.
ALTER TABLE facturacion ADD CONSTRAINT uq_facturacion_numero_cliente
    UNIQUE (numero, cliente_cedula);
 
CREATE TABLE detalle_factura (
    id SERIAL PRIMARY KEY,
    factura_numero VARCHAR(30) NOT NULL REFERENCES facturacion(numero) ON DELETE CASCADE ON UPDATE CASCADE,
    -- Un producto usado en una factura/cotización no puede eliminarse.
    producto_id INT REFERENCES productos(id) ON DELETE RESTRICT,
    nombre_producto VARCHAR(150) NOT NULL,
    cantidad NUMERIC(12,3) NOT NULL DEFAULT 1,
    precio_base NUMERIC(12,2) NOT NULL DEFAULT 0,
    ajuste NUMERIC(12,2) NOT NULL DEFAULT 0,
    total NUMERIC(12,2) NOT NULL,
    descripcion_linea TEXT,
    unidad_medida VARCHAR(30) NOT NULL DEFAULT 'unidad',
    es_adicional BOOLEAN NOT NULL DEFAULT FALSE
);

-- Pagos realmente recibidos. El calendario de vencimientos vive en
-- cuotas_factura y no comparte la numeración de estos movimientos.
CREATE TABLE pagos_factura (
    id SERIAL PRIMARY KEY,
    factura_numero VARCHAR(30) NOT NULL REFERENCES facturacion(numero) ON DELETE CASCADE ON UPDATE CASCADE,
    numero_pago INT NOT NULL,
    monto NUMERIC(12,2) NOT NULL CHECK (monto > 0),
    fecha DATE NOT NULL,
    metodo_pago VARCHAR(100) NOT NULL DEFAULT 'Transferencia bancaria',
    referencia VARCHAR(100),
    saldo_anterior NUMERIC(12,2) NOT NULL DEFAULT 0,
    saldo_posterior NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_acumulado NUMERIC(12,2) NOT NULL DEFAULT 0,
    registrado_por VARCHAR(100),
    notas TEXT,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_pago_id_factura UNIQUE (id, factura_numero)
);

CREATE SEQUENCE IF NOT EXISTS secuencia_comprobantes START WITH 1 INCREMENT BY 1;

CREATE TABLE comprobantes_pago (
    id SERIAL PRIMARY KEY,
    numero_comprobante VARCHAR(40) UNIQUE NOT NULL,
    pago_id INT NOT NULL,
    factura_numero VARCHAR(30) NOT NULL,
    cliente_cedula VARCHAR(20) NOT NULL,
    fecha DATE NOT NULL,
    monto_abonado NUMERIC(12,2) NOT NULL,
    total_deuda NUMERIC(12,2) NOT NULL,
    total_acumulado_pagado NUMERIC(12,2) NOT NULL,
    saldo_pendiente NUMERIC(12,2) NOT NULL,
    cliente_nombre_snapshot VARCHAR(150),
    cliente_apellido_snapshot VARCHAR(100),
    cliente_correo_snapshot VARCHAR(150),
    cliente_telefono_snapshot VARCHAR(20),
    cliente_direccion_snapshot VARCHAR(300),
    cliente_ciudad_snapshot VARCHAR(100),
    proxima_pago_num INT,
    proxima_pago_fecha DATE,
    proxima_pago_monto NUMERIC(12,2),
    observaciones TEXT,
    fecha_emision TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comprobante_pago_factura FOREIGN KEY (pago_id, factura_numero)
        REFERENCES pagos_factura(id, factura_numero) ON DELETE CASCADE,
    CONSTRAINT fk_comprobante_factura_cliente FOREIGN KEY (factura_numero, cliente_cedula)
        REFERENCES facturacion(numero, cliente_cedula) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE cuotas_factura (
    id SERIAL PRIMARY KEY,
    factura_numero VARCHAR(30) NOT NULL REFERENCES facturacion(numero) ON DELETE CASCADE ON UPDATE CASCADE,
    numero_pago INT NOT NULL CHECK (numero_pago > 0),
    valor_pago NUMERIC(12,2) NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    monto_pagado NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (monto_pagado >= 0),
    saldo_pago NUMERIC(12,2) NOT NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'Pendiente',
    fecha_pago DATE,
    CONSTRAINT uq_cuota_factura UNIQUE (factura_numero, numero_pago),
    CONSTRAINT ck_cuota_importes CHECK (valor_pago >= 0 AND monto_pagado <= valor_pago AND saldo_pago >= 0)
);

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) UNIQUE NOT NULL,
    descripcion TEXT
);

CREATE TABLE permisos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rol_permisos (
    rol_id INT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permiso_id INT NOT NULL REFERENCES permisos(id) ON DELETE CASCADE,
    PRIMARY KEY (rol_id, permiso_id)
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(50) UNIQUE NOT NULL,
    correo VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    rol_id INT NOT NULL REFERENCES roles(id),
    nombres VARCHAR(100),
    apellidos VARCHAR(100),
    telefono VARCHAR(30) UNIQUE,
    fecha_nacimiento DATE,
    es_mayor_edad BOOLEAN NOT NULL DEFAULT FALSE,
    acepta_terminos BOOLEAN NOT NULL DEFAULT FALSE,
    acepta_tratamiento_datos BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_consentimiento_datos TIMESTAMP,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    email_confirmado BOOLEAN NOT NULL DEFAULT FALSE,
    aprobado BOOLEAN NOT NULL DEFAULT TRUE,
    dos_factores_activo BOOLEAN NOT NULL DEFAULT FALSE,
    dos_factores_secreto TEXT,
    dos_factores_secreto_pendiente TEXT,
    dos_factores_intentos SMALLINT NOT NULL DEFAULT 0,
    dos_factores_bloqueo_hasta TIMESTAMP,
    dos_factores_ultimo_periodo BIGINT,
    foto_perfil VARCHAR(255),
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Cifrado de contraseñas insertadas directamente por SQL (texto plano).
-- Los hashes bcrypt o de Werkzeug generados por la aplicación se conservan.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION fn_cifrar_password()
RETURNS trigger
LANGUAGE plpgsql
AS $$
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
END;
$$;

DROP TRIGGER IF EXISTS usuarios_hash ON usuarios;
DROP TRIGGER IF EXISTS trg_cifrar_password ON usuarios;
CREATE TRIGGER trg_cifrar_password
    BEFORE INSERT OR UPDATE ON usuarios
    FOR EACH ROW
    EXECUTE FUNCTION fn_cifrar_password();

-- =============================================================================
-- NEXO DE USUARIOS Y SOLICITUDES DE ACCESO
-- `usuarios` es la tabla nexo: su id referencian clientes, facturas, pagos,
-- solicitudes, kardex y auditoría. Aquí se registra la decisión del
-- Administrador sobre cada solicitud de acceso.
-- =============================================================================

CREATE TABLE solicitudes_acceso (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rol_id INT NOT NULL REFERENCES roles(id),
    estado VARCHAR(20) NOT NULL DEFAULT 'Pendiente'
        CHECK (estado IN ('Pendiente', 'Aprobada', 'Rechazada')),
    motivo TEXT,
    fecha_solicitud TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_decision TIMESTAMP,
    decidido_por VARCHAR(150),
    UNIQUE (usuario_id, rol_id)
);

CREATE INDEX idx_solicitudes_acceso_estado
    ON solicitudes_acceso (estado, fecha_solicitud DESC);

CREATE OR REPLACE FUNCTION fn_registrar_solicitud_acceso() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.aprobado IS DISTINCT FROM NEW.aprobado THEN
        INSERT INTO solicitudes_acceso (usuario_id, rol_id, estado, fecha_decision)
        VALUES (NEW.id, NEW.rol_id, CASE WHEN NEW.aprobado THEN 'Aprobada' ELSE 'Pendiente' END,
                CASE WHEN NEW.aprobado THEN CURRENT_TIMESTAMP ELSE NULL END)
        ON CONFLICT (usuario_id, rol_id) DO UPDATE
            SET estado = EXCLUDED.estado,
                fecha_decision = EXCLUDED.fecha_decision,
                decidido_por = EXCLUDED.decidido_por;
    END IF;
    RETURN NEW;
END; $$;

CREATE TRIGGER trg_solicitud_acceso
    AFTER UPDATE OF aprobado ON usuarios
    FOR EACH ROW
    EXECUTE FUNCTION fn_registrar_solicitud_acceso();

CREATE TABLE kardex_movimientos (
    id SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('entrada', 'salida')),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    referencia VARCHAR(120),
    descripcion TEXT,
    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    automatico BOOLEAN NOT NULL DEFAULT FALSE,
    factura_numero VARCHAR(30) REFERENCES facturacion(numero) ON DELETE SET NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    costo_unitario NUMERIC(12,2)
);

CREATE TABLE logs_actividad (
    id SERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
    usuario_nombre VARCHAR(50),
    accion VARCHAR(100) NOT NULL,
    ip VARCHAR(50),
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    detalles TEXT
);

CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    correo VARCHAR(150) NOT NULL,
    telefono VARCHAR(30),
    tipo_producto VARCHAR(100),
    mensaje TEXT NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL DEFAULT 'Pendiente',
    responsable_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
    respuesta_cliente TEXT,
    pedido_entregado BOOLEAN NOT NULL DEFAULT FALSE,
    entregado_por_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
    fecha_entrega TIMESTAMP
);

-- ==============================================================================
-- SECUENCIAS Y TRIGGERS PARA AUTOGENERACIÓN SECUENCIAL ATÓMICA EN PRODUCCIÓN
-- ==============================================================================
CREATE SEQUENCE IF NOT EXISTS secuencia_facturas START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE IF NOT EXISTS secuencia_cotizaciones START WITH 1 INCREMENT BY 1;

CREATE OR REPLACE FUNCTION fn_autogenerar_numero_factura()
RETURNS TRIGGER AS $$
DECLARE
    nuevo_correlativo BIGINT;
    val_extraido BIGINT;
BEGIN
    -- Si el número no fue especificado o se envía vacío, autogenerarlo de forma secuencial y atómica
    IF NEW.numero IS NULL OR TRIM(NEW.numero) = '' THEN
        IF NEW.tipo = 'Cotizacion' THEN
            nuevo_correlativo := nextval('secuencia_cotizaciones');
            NEW.numero := 'COT-' || to_char(CURRENT_DATE, 'YYYY') || '-' || LPAD(nuevo_correlativo::TEXT, 4, '0');
        ELSE
            nuevo_correlativo := nextval('secuencia_facturas');
            NEW.numero := '001-001-' || LPAD(nuevo_correlativo::TEXT, 4, '0');
        END IF;
    ELSE
        -- Si se proporciona un número explícito, sincronizar la secuencia hacia adelante si aplica
        BEGIN
            IF NEW.tipo = 'Cotizacion' AND NEW.numero LIKE ('COT-' || to_char(CURRENT_DATE, 'YYYY') || '-%') THEN
                val_extraido := substring(NEW.numero from '[0-9]+$')::BIGINT;
                IF val_extraido >= (SELECT last_value FROM secuencia_cotizaciones) THEN
                    PERFORM setval('secuencia_cotizaciones', val_extraido, true);
                END IF;
            ELSIF NEW.tipo = 'Factura' AND NEW.numero LIKE '001-001-%' THEN
                val_extraido := substring(NEW.numero from '[0-9]+$')::BIGINT;
                IF val_extraido >= (SELECT last_value FROM secuencia_facturas) THEN
                    PERFORM setval('secuencia_facturas', val_extraido, true);
                END IF;
            END IF;
        END;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_autogenerar_numero ON facturacion;
CREATE TRIGGER trg_autogenerar_numero
BEFORE INSERT ON facturacion
FOR EACH ROW
EXECUTE FUNCTION fn_autogenerar_numero_factura();

 
-- DATOS DE REFERENCIA Y CONTROL DE ACCESO
-- No se insertan clientes, productos, proveedores ni cuentas de usuario.

INSERT INTO tipos_cliente (nombre) VALUES
    ('Persona natural'),
    ('Empresa')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO estados_proveedor (nombre) VALUES
    ('Activo'),
    ('Pendiente'),
    ('Inactivo')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO categorias_proveedor (nombre) VALUES
    ('Ingredientes'),
    ('Empaques'),
    ('Insumos de repostería'),
    ('Operación y logística')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO estados_documento (nombre) VALUES
    ('Pagada'),
    ('Pendiente'),
    ('Parcial'),
    ('Aprobada'),
    ('En revision'),
    ('Vencida')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO roles (nombre, descripcion) VALUES
    ('Administrador', 'Control total: usuarios y roles, aprobaciones, auditoría, catálogos, clientes, proveedores, pedidos, facturación e informes.'),
    ('Encargado', 'Gestiona productos, clientes, pedidos, ventas, pagos e informes; no administra usuarios ni permisos.'),
    ('Repostero', 'Consulta y actualiza productos, gestiona proveedores e insumos y atiende pedidos y entregas.'),
    ('Vendedor', 'Atiende clientes, consulta el catálogo y registra ventas y cotizaciones; no modifica roles ni catálogos.'),
    ('Cliente', 'Consulta el catálogo, sus propios pedidos y comprobantes, y sus estadísticas de compra.')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO permisos (codigo, descripcion) VALUES
    ('productos.ver', 'Consulta del catálogo de productos'),
    ('productos.crear', 'Registro de productos'),
    ('productos.editar', 'Edición de productos'),
    ('productos.eliminar', 'Eliminación de productos sin movimientos'),
    ('productos.futuros', 'Consulta de productos no disponibles'),
    ('clientes.ver', 'Consulta de clientes'),
    ('clientes.crear', 'Registro de clientes'),
    ('clientes.editar', 'Edición de clientes'),
    ('clientes.eliminar', 'Eliminación de clientes sin documentos'),
    ('clientes.sensible', 'Acceso a datos de contacto de clientes'),
    ('clientes.propio', 'Consulta del perfil propio del cliente'),
    ('facturas.ver', 'Consulta de ventas y cotizaciones'),
    ('facturas.crear', 'Registro de ventas y cotizaciones'),
    ('facturas.editar', 'Edición de ventas y cotizaciones'),
    ('facturas.eliminar', 'Anulación de ventas y cotizaciones'),
    ('facturas.ver_propias', 'Consulta de documentos propios del cliente'),
    ('proveedores.ver', 'Consulta de proveedores'),
    ('proveedores.crear', 'Registro de proveedores'),
    ('proveedores.editar', 'Edición de proveedores'),
    ('proveedores.eliminar', 'Eliminación de proveedores'),
    ('usuarios.ver', 'Consulta de cuentas de usuario'),
    ('usuarios.crear', 'Creación de cuentas de personal'),
    ('usuarios.editar', 'Edición de cuentas y roles'),
    ('usuarios.eliminar', 'Desactivación de cuentas de usuario'),
    ('usuarios.aprobar', 'Aprobación de solicitudes de acceso para perfiles del equipo'),
    ('reportes.ver', 'Consulta de informes operativos'),
    ('reportes.financiero', 'Consulta de informes financieros')
ON CONFLICT (codigo) DO UPDATE SET descripcion = EXCLUDED.descripcion;

INSERT INTO rol_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM (VALUES
    ('Administrador', 'productos.ver'), ('Administrador', 'productos.crear'), ('Administrador', 'productos.editar'), ('Administrador', 'productos.eliminar'), ('Administrador', 'productos.futuros'),
    ('Administrador', 'clientes.ver'), ('Administrador', 'clientes.crear'), ('Administrador', 'clientes.editar'), ('Administrador', 'clientes.eliminar'), ('Administrador', 'clientes.sensible'), ('Administrador', 'clientes.propio'),
    ('Administrador', 'facturas.ver'), ('Administrador', 'facturas.crear'), ('Administrador', 'facturas.editar'), ('Administrador', 'facturas.eliminar'), ('Administrador', 'facturas.ver_propias'),
    ('Administrador', 'proveedores.ver'), ('Administrador', 'proveedores.crear'), ('Administrador', 'proveedores.editar'), ('Administrador', 'proveedores.eliminar'),
    ('Administrador', 'usuarios.ver'), ('Administrador', 'usuarios.crear'), ('Administrador', 'usuarios.editar'), ('Administrador', 'usuarios.eliminar'), ('Administrador', 'usuarios.aprobar'),
    ('Administrador', 'reportes.ver'), ('Administrador', 'reportes.financiero'),
    ('Encargado', 'productos.ver'), ('Encargado', 'productos.crear'), ('Encargado', 'productos.editar'), ('Encargado', 'productos.futuros'),
    ('Encargado', 'clientes.ver'), ('Encargado', 'clientes.crear'), ('Encargado', 'clientes.editar'), ('Encargado', 'clientes.sensible'),
    ('Encargado', 'facturas.ver'), ('Encargado', 'facturas.crear'), ('Encargado', 'facturas.editar'), ('Encargado', 'facturas.eliminar'),
    ('Encargado', 'reportes.ver'), ('Encargado', 'reportes.financiero'),
    ('Repostero', 'productos.ver'), ('Repostero', 'productos.editar'), ('Repostero', 'productos.futuros'),
    ('Repostero', 'proveedores.ver'), ('Repostero', 'proveedores.crear'), ('Repostero', 'proveedores.editar'),
    ('Vendedor', 'productos.ver'), ('Vendedor', 'productos.futuros'),
    ('Vendedor', 'clientes.ver'), ('Vendedor', 'clientes.crear'), ('Vendedor', 'clientes.sensible'),
    ('Vendedor', 'facturas.ver'), ('Vendedor', 'facturas.crear'),
    ('Cliente', 'productos.ver'), ('Cliente', 'productos.futuros'), ('Cliente', 'clientes.propio'),
    ('Cliente', 'facturas.ver'), ('Cliente', 'facturas.ver_propias'), ('Cliente', 'reportes.ver')
) AS asignaciones(rol_nombre, permiso_codigo)
JOIN roles r ON r.nombre = asignaciones.rol_nombre
JOIN permisos p ON p.codigo = asignaciones.permiso_codigo
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_facturacion_cliente_fecha ON facturacion (cliente_cedula, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_detalle_factura_producto ON detalle_factura (producto_id);
CREATE INDEX IF NOT EXISTS idx_solicitudes_estado_fecha ON solicitudes (estado, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_solicitudes_responsable ON solicitudes (responsable_id);
CREATE INDEX IF NOT EXISTS idx_pagos_factura_fecha ON pagos_factura (factura_numero, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_cuotas_factura_vencimiento ON cuotas_factura (factura_numero, fecha_vencimiento);

-- =============================================================================
-- ENLACES NEXO: NADIE QUEDA FUERA DEL MODELO RELACIONAL
-- Se agrean al final porque dependen de tablas creadas más arriba
-- (`usuarios`, `roles`, `parametros`, `productos`, `proveedores`).
-- Equivalencias con el modelo de referencia: donde allí aparece `servicios` y
-- `tipos_servicio`, aquí el catálogo es `productos` y `categorias_producto`;
-- donde aparece `solicitudes.resuelto_por_id`, aquí es `entregado_por_id`.
-- =============================================================================

-- El usuario registrado se liga a su ficha de cliente (uno a uno).
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS usuario_id INT;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'clientes'::regclass AND conname = 'fk_clientes_usuario_id'
    ) THEN
        ALTER TABLE clientes ADD CONSTRAINT fk_clientes_usuario_id
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_usuario_unico
    ON clientes (usuario_id) WHERE usuario_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clientes_usuario ON clientes (usuario_id);

-- Quién emite el documento y con qué tasa de IVA se valuó.
ALTER TABLE facturacion ADD COLUMN IF NOT EXISTS usuario_id INT;
ALTER TABLE facturacion ADD COLUMN IF NOT EXISTS iva_id INT;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'facturacion'::regclass AND conname = 'fk_facturacion_usuario_id'
    ) THEN
        ALTER TABLE facturacion ADD CONSTRAINT fk_facturacion_usuario_id
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'facturacion'::regclass AND conname = 'fk_facturacion_iva_id'
    ) THEN
        ALTER TABLE facturacion ADD CONSTRAINT fk_facturacion_iva_id
            FOREIGN KEY (iva_id) REFERENCES parametros(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_facturacion_usuario ON facturacion (usuario_id);
CREATE INDEX IF NOT EXISTS idx_facturacion_iva ON facturacion (iva_id);

-- Cada línea conserva el IVA aplicado y el parámetro del que proviene.
ALTER TABLE detalle_factura ADD COLUMN IF NOT EXISTS iva_id INT;
ALTER TABLE detalle_factura ADD COLUMN IF NOT EXISTS iva_valor NUMERIC(7,4);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'detalle_factura'::regclass AND conname = 'fk_detalle_factura_iva_id'
    ) THEN
        ALTER TABLE detalle_factura ADD CONSTRAINT fk_detalle_factura_iva_id
            FOREIGN KEY (iva_id) REFERENCES parametros(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_detalle_iva ON detalle_factura (iva_id);

-- Quién registra el pago y qué pago abonó cada cuota.
ALTER TABLE pagos_factura ADD COLUMN IF NOT EXISTS usuario_id INT;
ALTER TABLE cuotas_factura ADD COLUMN IF NOT EXISTS pago_id INT;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'pagos_factura'::regclass AND conname = 'fk_pagos_factura_usuario_id'
    ) THEN
        ALTER TABLE pagos_factura ADD CONSTRAINT fk_pagos_factura_usuario_id
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'cuotas_factura'::regclass AND conname = 'fk_cuotas_factura_pago_id'
    ) THEN
        ALTER TABLE cuotas_factura ADD CONSTRAINT fk_cuotas_factura_pago_id
            FOREIGN KEY (pago_id) REFERENCES pagos_factura(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_pagos_usuario ON pagos_factura (usuario_id);
CREATE INDEX IF NOT EXISTS idx_cuotas_pago ON cuotas_factura (pago_id);

-- Quién solicita, a qué categoría pertenece y qué cuenta la respalda.
ALTER TABLE solicitudes ADD COLUMN IF NOT EXISTS usuario_id INT;
ALTER TABLE solicitudes ADD COLUMN IF NOT EXISTS categoria_producto_id INT;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'solicitudes'::regclass AND conname = 'fk_solicitudes_usuario_id'
    ) THEN
        ALTER TABLE solicitudes ADD CONSTRAINT fk_solicitudes_usuario_id
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'solicitudes'::regclass AND conname = 'fk_solicitudes_categoria_producto_id'
    ) THEN
        ALTER TABLE solicitudes ADD CONSTRAINT fk_solicitudes_categoria_producto_id
            FOREIGN KEY (categoria_producto_id) REFERENCES categorias_producto(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_solicitudes_usuario ON solicitudes (usuario_id);

-- Proveedor que suministra el insumo.
ALTER TABLE productos ADD COLUMN IF NOT EXISTS proveedor_id INT;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'productos'::regclass AND conname = 'fk_productos_proveedor_id'
    ) THEN
        ALTER TABLE productos ADD CONSTRAINT fk_productos_proveedor_id
            FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL;
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_productos_proveedor ON productos (proveedor_id);

-- Los estados de solicitud que la aplicación admite.
ALTER TABLE solicitudes DROP CONSTRAINT IF EXISTS chk_solicitudes_estado;
ALTER TABLE solicitudes ADD CONSTRAINT chk_solicitudes_estado CHECK (
    estado IN ('Pendiente', 'Confirmado', 'En preparación', 'Listo para retiro',
               'En reparto', 'Entregada', 'Cancelada')
);
ALTER TABLE detalle_factura DROP CONSTRAINT IF EXISTS chk_detalle_iva_valor;
ALTER TABLE detalle_factura ADD CONSTRAINT chk_detalle_iva_valor
    CHECK (iva_valor IS NULL OR (iva_valor >= 0 AND iva_valor <= 100));

-- =============================================================================
-- PERMISOS ACTIVABLES DESDE LA WEB Y DESDE POSTGRESQL
-- `permisos.activo` enciende o apaga el permiso para toda la aplicación, y las
-- funciones siguientes permiten conceder o revoke sin pasar por el panel.
-- =============================================================================

ALTER TABLE permisos ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE permisos ADD COLUMN IF NOT EXISTS actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

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
    UPDATE permisos
    SET activo = COALESCE(p_activo, TRUE), actualizado_en = CURRENT_TIMESTAMP
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
BEGIN
    SELECT id INTO id_rol FROM roles WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(p_rol));
    IF id_rol IS NULL THEN
        RAISE EXCEPTION 'El rol % no existe en la tabla roles', p_rol;
    END IF;

    SELECT id INTO id_permiso FROM permisos WHERE codigo = p_codigo;
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

COMMIT;
