import os
import time
from pathlib import Path

import psycopg2
from flask import g, has_app_context
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env')


def get_db_connection():
    """Obtiene una conexión activa - registra para el cierre automático."""
    if has_app_context():
        conexion_actual = getattr(g, 'dulce_delicia_db_connection', None)
        if conexion_actual is not None and not conexion_actual.closed:
            return conexion_actual

    db_url = (os.getenv('DATABASE_URL') or '').strip()
    parametros = {}
    application_name = 'dulce_delicia-web'

    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        parametros['dsn'] = db_url
    else:
        application_name = 'dulce_delicia-local'
        password = os.getenv('DB_PASSWORD', '')
        parametros = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'dbname': os.getenv('DB_NAME', 'dulce_delicia'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': password,
        }
        if not password:
            raise psycopg2.OperationalError(
                'Falta DB_PASSWORD o DATABASE_URL. Configura las credenciales '
                f'de PostgreSQL en {PROJECT_ROOT / ".env"}.'
            )

    ultimo_error = None
    for intento in range(3):
        try:
            conexion = psycopg2.connect(
                **parametros,
                cursor_factory=RealDictCursor,
                connect_timeout=10,
                application_name=application_name
            )
            if has_app_context():
                g.dulce_delicia_db_connection = conexion
            return conexion
        except psycopg2.OperationalError as error:
            ultimo_error = error
            if intento < 2:
                time.sleep(0.5 * (intento + 1))

    raise ultimo_error


def close_db_connection(exception=None):
    """Cierra la conexión de la solicitud al finalizar el contexto Flask."""
    conexion = getattr(g, 'dulce_delicia_db_connection', None)
    if conexion is not None and not conexion.closed:
        conexion.close()
    g.dulce_delicia_db_connection = None


def release_db_connection(conexion):
    """
    Libera una conexión obtenida con get_db_connection sin romper la solicitud.

    Dentro de un contexto Flask la conexión se comparte en `g` y se cierra
    automáticamente al terminar la petición (teardown). Cerrarla aquí dejaría
    el cursor inservible para el resto de la vista ("cursor already closed").
    Por eso solo se cierra de verdad cuando NO es la conexión compartida de la
    solicitud (p. ej. fuera de contexto Flask, como en scripts o pruebas).
    """
    if conexion is None:
        return
    if has_app_context():
        compartida = getattr(g, 'dulce_delicia_db_connection', None)
        if compartida is conexion:
            return
    if not conexion.closed:
        conexion.close()
