import unittest

from flask import Flask, g

from conexion.conexion import release_db_connection


class FakeConnection:
    """Simula una conexión psycopg2 con estado de cierre observable."""

    def __init__(self):
        self.closed = 0
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        self.closed = 1


class ReleaseDbConnectionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_no_cierra_la_conexion_compartida_de_la_solicitud(self):
        """Dentro del contexto, la conexión de `g` NO debe cerrarse (bug cursor already closed)."""
        compartida = FakeConnection()
        with self.app.app_context():
            g.dulce_delicia_db_connection = compartida
            release_db_connection(compartida)
        self.assertEqual(compartida.close_calls, 0)
        self.assertEqual(compartida.closed, 0)

    def test_cierra_una_conexion_que_no_es_la_compartida(self):
        """Una conexión ajena a `g` sí se cierra, incluso dentro del contexto."""
        compartida = FakeConnection()
        ajena = FakeConnection()
        with self.app.app_context():
            g.dulce_delicia_db_connection = compartida
            release_db_connection(ajena)
        self.assertEqual(ajena.close_calls, 1)
        self.assertEqual(compartida.close_calls, 0)

    def test_fuera_de_contexto_cierra_la_conexion(self):
        """Sin contexto Flask (scripts/pruebas) la conexión se cierra con normalidad."""
        conn = FakeConnection()
        release_db_connection(conn)
        self.assertEqual(conn.close_calls, 1)

    def test_no_cierra_dos_veces_una_conexion_ya_cerrada(self):
        conn = FakeConnection()
        conn.closed = 1
        release_db_connection(conn)
        self.assertEqual(conn.close_calls, 0)

    def test_ignora_none(self):
        release_db_connection(None)


if __name__ == '__main__':
    unittest.main()
