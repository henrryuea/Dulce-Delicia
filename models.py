# ==============================================================================
# PROYECTO: DULCE DELICIA - MODELOS DE BASE DE DATOS Y AUTENTICACIÓN (RBAC)
# ==============================================================================
# Este archivo define la estructura de datos ORM (SQLAlchemy) y la clase de
# usuario para Flask-Login con soporte integral para:
# 1. Roles definidos: Administrador, Encargado, Repostero,
#    Vendedor y Cliente.
# 2. Permisos granulares y control de acceso.
# 3. Verificación de contraseñas con Bcrypt (con compatibilidad retroactiva).
# 4. Estado de aprobación para Administradores y confirmación de correo.
# 5. Registro y auditoría de actividad (logs_actividad).
# ==============================================================================

import unicodedata

import bcrypt
from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash as werkzeug_check_hash

# Instancia central de SQLAlchemy para la aplicación Flask
db = SQLAlchemy()


def clave_comparacion(valor):
    """
    Normaliza un identificador para compararlo sin distinguir mayúsculas,
    tildes ni espacios sobrantes. Permite que "Pérez", "perez" y "PÉREZ " sean
    la misma clave al iniciar sesión.
    """
    texto = unicodedata.normalize('NFKD', (valor or '').strip().lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))


def es_hash_contrasena(valor):
    """
    Indica si un valor YA es un hash de contraseña (bcrypt o Werkzeug) en lugar
    de texto plano. Permite que el cifrado sea idempotente: una contraseña se
    cifra exactamente una vez, sin importar cuántas veces pase por la
    aplicación o por los triggers de PostgreSQL.
    """
    texto = (valor or '').strip()
    return texto.startswith(('$2a$', '$2b$', '$2y$', 'scrypt:', 'pbkdf2:'))


def normalizar_nombre_rol(nombre):
    """Mantiene un único nombre visible y funcional para el rol administrador."""
    nombre_limpio = (nombre or '').strip()
    if nombre_limpio.casefold() in {'admin', 'administrador'}:
        return 'Administrador'
    return nombre_limpio


# ==============================================================================
# MODELO: ROLES DEL SISTEMA
# ==============================================================================
class Role(db.Model):
    """
    Representa un rol dentro del sistema de control de acceso RBAC.
    """
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    # Relación inversa con usuarios
    usuarios = db.relationship('User', backref='rol_obj', lazy=True)

    @staticmethod
    def get_all():
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *
            FROM roles
            ORDER BY
                CASE
                    WHEN LOWER(TRIM(nombre)) = 'administrador' THEN 0
                    WHEN LOWER(TRIM(nombre)) = 'admin' THEN 1
                    ELSE 2
                END,
                id
        ''')
        roles = []
        nombres_vistos = set()
        for fila in cursor.fetchall():
            rol = dict(fila)
            rol['nombre'] = normalizar_nombre_rol(rol.get('nombre'))
            clave = rol['nombre'].casefold()
            if clave not in nombres_vistos:
                roles.append(rol)
                nombres_vistos.add(clave)
        cursor.close()
        release_db_connection(conn)
        return roles

    @staticmethod
    def get_by_id(rol_id):
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM roles WHERE id = %s', (rol_id,))
        rol = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        if rol:
            rol = dict(rol)
            rol['nombre'] = normalizar_nombre_rol(rol.get('nombre'))
        return rol


# ==============================================================================
# MODELO: PERMISOS DEL SISTEMA
# ==============================================================================
class Permission(db.Model):
    """
    Define permisos específicos para acciones granulares en el sistema.
    """
    __tablename__ = 'permisos'

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)


# ==============================================================================
# MODELO: LOGS DE AUDITORÍA Y ACTIVIDAD
# ==============================================================================
class ActivityLog(db.Model):
    """
    Registro histórico de auditoría de acciones realizadas en el sistema.
    """
    __tablename__ = 'logs_actividad'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    usuario_nombre = db.Column(db.String(50), nullable=True)
    accion = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(50), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    detalles = db.Column(db.Text, nullable=True)

    @staticmethod
    def registrar(usuario_id, usuario_nombre, accion, ip=None, detalles=None):
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO logs_actividad (usuario_id, usuario_nombre, accion, ip, detalles)
            VALUES (%s, %s, %s, %s, %s)
        ''', (usuario_id, usuario_nombre, accion, ip, detalles))
        conn.commit()
        cursor.close()
        release_db_connection(conn)

    @staticmethod
    def get_recientes(limit=50):
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.*, r.nombre AS rol_nombre
            FROM logs_actividad l
            LEFT JOIN usuarios u ON l.usuario_id = u.id
            LEFT JOIN roles r ON u.rol_id = r.id
            ORDER BY l.fecha DESC
            LIMIT %s
        ''', (limit,))
        logs = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)
        return logs

    @staticmethod
    def buscar(fecha_desde=None, fecha_hasta=None, hora_desde=None,
               hora_hasta=None, persona=None, accion=None, ip=None,
               detalles=None, limit=500):
        """Busca auditoría con filtros aplicados en PostgreSQL."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        condiciones = []
        parametros = []
        if fecha_desde:
            condiciones.append('l.fecha >= %s::date')
            parametros.append(fecha_desde)
        if fecha_hasta:
            condiciones.append("l.fecha < (%s::date + INTERVAL '1 day')")
            parametros.append(fecha_hasta)
        if hora_desde:
            condiciones.append('l.fecha::time >= %s::time')
            parametros.append(hora_desde)
        if hora_hasta:
            condiciones.append('l.fecha::time <= %s::time')
            parametros.append(hora_hasta)
        for columna, valor in (
            ('l.usuario_nombre', persona),
            ('l.ip', ip),
            ('l.detalles', detalles),
        ):
            if valor:
                condiciones.append(f'COALESCE({columna}, \'\') ILIKE %s')
                parametros.append(f'%{valor}%')
        if accion:
            condiciones.append('l.accion = %s')
            parametros.append(accion)

        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ''
        parametros.append(limit)
        cursor.execute(f'''
            SELECT l.*, r.nombre AS rol_nombre
            FROM logs_actividad l
            LEFT JOIN usuarios u ON l.usuario_id = u.id
            LEFT JOIN roles r ON u.rol_id = r.id
            {where}
            ORDER BY l.fecha DESC, l.id DESC
            LIMIT %s
        ''', parametros)
        logs = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)
        return logs

    @staticmethod
    def acciones_disponibles():
        """Obtiene las acciones existentes para el selector de auditoría."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT accion
            FROM logs_actividad
            WHERE accion IS NOT NULL AND TRIM(accion) <> ''
            ORDER BY accion
        ''')
        acciones = [row['accion'] for row in cursor.fetchall()]
        cursor.close()
        release_db_connection(conn)
        return acciones


# ==============================================================================
# MODELO Y CLASE DE USUARIO (UserMixin para Flask-Login)
# ==============================================================================
class User(UserMixin, db.Model):
    """
    Representa un usuario del sistema en la base de datos PostgreSQL.
    Incluye campos de auditoría, control de roles (RBAC), verificación
    de correo, aprobación administrativa y 2FA.
    """
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    rol_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    email_confirmado = db.Column(db.Boolean, default=False, nullable=False)
    aprobado = db.Column(db.Boolean, default=True, nullable=False)
    dos_factores_activo = db.Column(db.Boolean, default=False, nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    foto_perfil = db.Column(db.String(255))

    def __init__(self, id, usuario, correo, password, rol_id, rol_nombre=None,
                 activo=True, email_confirmado=False, aprobado=True,
                 dos_factores_activo=False, foto_perfil=None):
        self.id = id
        self.usuario = usuario
        self.correo = correo
        self.password = password
        self.rol_id = rol_id
        self.rol_nombre = rol_nombre or 'Cliente'
        self.activo = activo
        self.email_confirmado = email_confirmado
        self.aprobado = aprobado
        self.dos_factores_activo = dos_factores_activo
        self.foto_perfil = foto_perfil

    @property
    def is_active(self):
        """Retorna si el usuario está activo y habilitado para autenticarse."""
        return self.activo

    def has_role(self, *role_names):
        """Verifica si el usuario posee alguno de los roles solicitados."""
        return self.rol_nombre in role_names

    def is_admin(self):
        """Atajo para comprobar si el usuario es Administrador."""
        return self.rol_nombre == 'Administrador'

    def is_approved(self):
        """Indica si la cuenta ya fue autorizada para iniciar sesión."""
        return self.aprobado

    def has_permission(self, codigo_permiso):
        """
        Verifica en la tabla relacional `rol_permisos` si el rol del usuario posee
        un permiso específico. Solo concede acceso si el permiso está ACTIVO, de
        modo que encenderlo o apagarlo desde la web o desde PostgreSQL surte
        efecto en la siguiente petición.
        """
        if self.is_admin():
            return True
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT 1 FROM rol_permisos rp
            JOIN permisos p ON rp.permiso_id = p.id
            WHERE rp.rol_id = %s AND p.codigo = %s AND p.activo
        ''', (self.rol_id, codigo_permiso))
        tiene = cur.fetchone() is not None
        cur.close()
        release_db_connection(conn)
        return tiene

    def get_permissions(self):
        """Retorna la lista de permisos activos asignados al rol del usuario."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT p.codigo, p.descripcion
            FROM rol_permisos rp
            JOIN permisos p ON rp.permiso_id = p.id
            WHERE rp.rol_id = %s AND p.activo
            ORDER BY p.codigo
        ''', (self.rol_id,))
        permisos = cur.fetchall()
        cur.close()
        release_db_connection(conn)
        return permisos

    @staticmethod
    def matriz_permisos():
        """
        Matriz completa rol x permiso leída de `v_permisos_rol`, la misma vista
        que se puede consultar desde PostgreSQL. Informa qué permisos están
        activos y cuáles tiene asignados cada rol.
        """
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT rol_id, rol_nombre, permiso_id, permiso_codigo, descripcion,
                   permiso_activo, asignado
            FROM v_permisos_rol
            ORDER BY rol_nombre, permiso_codigo
        ''')
        matriz = [dict(fila) for fila in cur.fetchall()]
        cur.close()
        release_db_connection(conn)
        return matriz

    @staticmethod
    def definir_permiso(permiso_codigo, rol_nombre=None, activo=None, asignado=None):
        """
        Activa o desactiva un permiso y/o lo concede o revoca a un rol.
        Es la misma operación que las funciones `activar_permiso`,
        `asignar_permiso` y `revocar_permiso` de PostgreSQL.
        """
        from conexion.conexion import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT id, activo FROM permisos WHERE codigo = %s FOR UPDATE', (permiso_codigo,))
            permiso = cur.fetchone()
            if not permiso:
                raise ValueError(f'El permiso "{permiso_codigo}" no existe.')
            nuevo_activo = permiso['activo'] if activo is None else bool(activo)
            if activo is not None and nuevo_activo != permiso['activo']:
                cur.execute(
                    'UPDATE permisos SET activo = %s, actualizado_en = CURRENT_TIMESTAMP WHERE codigo = %s',
                    (nuevo_activo, permiso_codigo)
                )

            if rol_nombre is not None and asignado is not None:
                cur.execute('SELECT id FROM roles WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(%s))', (rol_nombre,))
                rol = cur.fetchone()
                if not rol:
                    raise ValueError(f'El rol "{rol_nombre}" no existe.')
                if asignado:
                    cur.execute(
                        '''INSERT INTO rol_permisos (rol_id, permiso_id) VALUES (%s, %s)
                           ON CONFLICT (rol_id, permiso_id) DO NOTHING''',
                        (rol['id'], permiso['id'])
                    )
                else:
                    cur.execute(
                        'DELETE FROM rol_permisos WHERE rol_id = %s AND permiso_id = %s',
                        (rol['id'], permiso['id'])
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            cur.close()
            conn.close()
            raise
        cur.close()
        conn.close()


    def check_password(self, plain_password):
        """
        Verifica la contraseña ingresada contra el hash almacenado.
        Soporta tanto Bcrypt ($2a$/$2b$/$2y$) como hashes de Werkzeug
        (scrypt/pbkdf2) para garantizar retrocompatibilidad total.
        """
        stored_hash = (self.password or '').strip()
        if not stored_hash or plain_password is None:
            return False
        try:
            if stored_hash.startswith(('$2a$', '$2b$', '$2y$')):
                # bcrypt usa el mismo formato para $2a$, $2b$ y $2y$.
                # La librería Python acepta $2a$/$2b$, por eso se normaliza
                # solo el prefijo compatible sin cambiar la contraseña.
                if stored_hash.startswith('$2y$'):
                    stored_hash = '$2b$' + stored_hash[4:]
                return bcrypt.checkpw(
                    plain_password.encode('utf-8'),
                    stored_hash.encode('utf-8')
                )
            return werkzeug_check_hash(stored_hash, plain_password)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def hash_password(plain_password):
        """
        Genera un hash seguro utilizando Bcrypt.

        Es IDEMPOTENTE: si el valor recibido ya es un hash (bcrypt o Werkzeug)
        se devuelve intacto en lugar de cifrarlo otra vez. Así la contraseña
        original se cifra una sola vez y se mantiene válida al iniciar sesión,
        aunque el valor pase varias veces por la aplicación o por los triggers
        de cifrado de PostgreSQL.
        """
        if es_hash_contrasena(plain_password):
            return plain_password.strip()
        if not plain_password:
            raise ValueError('La contraseña no puede estar vacía.')
        datos = plain_password.encode('utf-8')
        if len(datos) > 72:
            raise ValueError('La contraseña no puede superar los 72 bytes de bcrypt.')
        return bcrypt.hashpw(datos, bcrypt.gensalt()).decode('utf-8')

    @classmethod
    def _from_row(cls, row):
        """Crea una instancia de User a partir de un diccionario de PostgreSQL."""
        if not row:
            return None
        return cls(
            id=row['id'],
            usuario=row['usuario'],
            correo=row.get('correo', f"{row['usuario']}@example.invalid"),
            password=row['password'],
            rol_id=row.get('rol_id', 1),
            rol_nombre=normalizar_nombre_rol(row.get('rol_nombre', 'Administrador')),
            activo=row.get('activo', True),
            email_confirmado=row.get('email_confirmado', True),
            aprobado=row.get('aprobado', True),
            dos_factores_activo=row.get('dos_factores_activo', False),
            foto_perfil=row.get('foto_perfil')
        )

    @staticmethod
    def get_by_id(user_id):
        """Recupera un usuario por su identificador primario (ID) con JOIN a roles."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, r.nombre AS rol_nombre
            FROM usuarios u
            LEFT JOIN roles r ON u.rol_id = r.id
            WHERE u.id = %s
        ''', (user_id,))
        row = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return User._from_row(row)

    @staticmethod
    def get_by_usuario(username):
        """Recupera un usuario por su nombre de usuario."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, r.nombre AS rol_nombre
            FROM usuarios u
            LEFT JOIN roles r ON u.rol_id = r.id
            WHERE LOWER(TRIM(u.usuario)) = LOWER(TRIM(%s))
        ''', (username,))
        row = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return User._from_row(row)

    @staticmethod
    def get_by_correo(email):
        """Recupera un usuario por su dirección de correo electrónico."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, r.nombre AS rol_nombre
            FROM usuarios u
            LEFT JOIN roles r ON u.rol_id = r.id
            WHERE LOWER(TRIM(u.correo)) = LOWER(TRIM(%s))
        ''', (email,))
        row = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return User._from_row(row)

    @staticmethod
    def get_by_identificador(identificador):
        """
        Localiza la cuenta para el inicio de sesión.

        Primero exige coincidencia EXACTA por usuario o correo. Solo si no hay
        resultado, acepta que el identificador sea el inicio del usuario, del
        nombre o del apellido, para que nadie quede fuera por escribir su
        identificador de forma ligeramente distinta. Si el prefijo coincide con
        más de una cuenta no se elige ninguna y el acceso se rechaza.
        """
        exacto = User.get_by_usuario_o_correo(identificador)
        if exacto:
            return exacto

        from conexion.conexion import get_db_connection, release_db_connection
        patron = clave_comparacion(identificador)
        if not patron:
            return None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.*, r.nombre AS rol_nombre
                FROM usuarios u
                LEFT JOIN roles r ON u.rol_id = r.id
                ORDER BY u.id
                LIMIT 200
            ''')
            filas = cursor.fetchall()
            cursor.close()
            release_db_connection(conn)
        except Exception:
            return None

        coincidencias = []
        for fila in filas:
            candidatos = (
                fila.get('usuario'), fila.get('correo'),
                fila.get('nombres'), fila.get('apellidos'),
                f"{fila.get('nombres') or ''} {fila.get('apellidos') or ''}".strip(),
            )
            for candidato in candidatos:
                clave = clave_comparacion(candidato)
                if clave and (clave == patron or clave.startswith(patron)):
                    coincidencias.append(fila)
                    break
        return User._from_row(coincidencias[0]) if len(coincidencias) == 1 else None

    @staticmethod
    def get_by_usuario_o_correo(identificador):
        """Busca indistintamente por nombre de usuario o por correo electrónico."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.*, r.nombre AS rol_nombre
            FROM usuarios u
            LEFT JOIN roles r ON u.rol_id = r.id
            WHERE LOWER(TRIM(u.usuario)) = LOWER(TRIM(%s))
               OR LOWER(TRIM(u.correo)) = LOWER(TRIM(%s))
        ''', (identificador, identificador))
        row = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
        return User._from_row(row)

    @staticmethod
    def get_all():
        """Obtiene la lista completa de usuarios con su rol y datos de identidad."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.usuario, u.correo, u.rol_id, r.nombre AS rol_nombre,
                   u.nombres, u.apellidos, u.telefono,
                   u.fecha_nacimiento, u.es_mayor_edad,
                   u.activo, u.email_confirmado, u.aprobado,
                   u.acepta_terminos, u.dos_factores_activo, u.fecha_registro
            FROM usuarios u
            LEFT JOIN roles r ON u.rol_id = r.id
            ORDER BY u.aprobado ASC, u.fecha_registro DESC, u.id ASC
        ''')
        rows = []
        for fila in cursor.fetchall():
            usuario = dict(fila)
            usuario['rol_nombre'] = normalizar_nombre_rol(usuario.get('rol_nombre'))
            rows.append(usuario)
        cursor.close()
        release_db_connection(conn)
        return rows

    @staticmethod
    def get_solicitudes_acceso(limite=50):
        """Historial de solicitudes de acceso con la decisión del Administrador."""
        from conexion.conexion import get_db_connection, release_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.estado, s.motivo, s.fecha_solicitud, s.fecha_decision,
                   s.decidido_por, u.id AS usuario_id, u.usuario, u.correo,
                   u.nombres, u.apellidos, u.telefono,
                   u.fecha_nacimiento, u.es_mayor_edad,
                   r.nombre AS rol_nombre
            FROM solicitudes_acceso s
            JOIN usuarios u ON u.id = s.usuario_id
            JOIN roles r ON r.id = s.rol_id
            ORDER BY s.estado = 'Pendiente' DESC, s.fecha_solicitud DESC
            LIMIT %s
        ''', (limite,))
        filas = [dict(f) for f in cursor.fetchall()]
        cursor.close()
        release_db_connection(conn)
        return filas


# Alias para mantener compatibilidad total con código previo que importe Usuario
Usuario = User
