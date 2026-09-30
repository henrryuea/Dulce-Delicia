import unittest
import re
from unittest.mock import patch

import app as aplicacion
from models import User


class CursorSeguridadFalso:
    def __init__(self, password):
        self.password = password
        self.consultas = []
        self.consulta_actual = ''

    def execute(self, consulta, parametros=None):
        self.consultas.append((consulta, parametros))
        self.consulta_actual = consulta

    def fetchone(self):
        if 'dos_factores_activo' in self.consulta_actual:
            return {'dos_factores_activo': False, 'dos_factores_secreto_pendiente': None}
        return {'password': self.password}

    def close(self):
        pass


class ConexionSeguridadFalsa:
    def __init__(self, password):
        self.cursor_falso = CursorSeguridadFalso(password)
        self.confirmada = False
        self.revertida = False

    def cursor(self):
        return self.cursor_falso

    def commit(self):
        self.confirmada = True

    def rollback(self):
        self.revertida = True

    def close(self):
        pass


class CursorCargaSeguridadFalso:
    def execute(self, consulta, parametros=None):
        pass

    def fetchone(self):
        return {'dos_factores_activo': False, 'dos_factores_secreto_pendiente': None}

    def close(self):
        pass


class ConexionCargaSeguridadFalsa:
    def cursor(self):
        return CursorCargaSeguridadFalso()

    def close(self):
        pass


class SeguridadCuentaTests(unittest.TestCase):
    def setUp(self):
        self.password_original = 'ClaveAnterior123!'
        self.usuario = User(
            id=91,
            usuario='cliente_prueba',
            correo='cliente@example.test',
            password=User.hash_password(self.password_original),
            rol_id=1,
            rol_nombre='Cliente',
        )
        self.conexion = ConexionSeguridadFalsa(self.usuario.password)
        self.cliente = aplicacion.app.test_client()

    def enviar_cambio(self, password_nueva, confirmar=None, password_actual=None):
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': False}):
            with patch.object(aplicacion.login_manager, '_user_callback', return_value=self.usuario):
                with patch.object(aplicacion, 'get_db_connection', return_value=self.conexion):
                    with patch.object(aplicacion, 'registrar_log'):
                        with self.cliente.session_transaction() as sesion:
                            sesion['_user_id'] = str(self.usuario.id)
                            sesion['_fresh'] = True
                        return self.cliente.post(
                            '/cuenta/seguridad/2fa',
                            data={
                                'accion': 'cambiar_password',
                                'password_actual': password_actual or self.password_original,
                                'password_nueva': password_nueva,
                                'confirmar_password': confirmar if confirmar is not None else password_nueva,
                            },
                        )

    def test_actualiza_password_solo_con_clave_actual_y_nueva_segura(self):
        respuesta = self.enviar_cambio('ClaveNueva456!')

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.conexion.confirmada)
        self.assertTrue(self.usuario.check_password('ClaveNueva456!'))

    def test_rechaza_password_nueva_debil_sin_guardarla(self):
        respuesta = self.enviar_cambio('corta')

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(self.conexion.confirmada)
        self.assertTrue(self.conexion.revertida)
        self.assertTrue(self.usuario.check_password(self.password_original))

    def test_rechaza_confirmacion_distinta(self):
        respuesta = self.enviar_cambio('ClaveNueva456!', 'OtraClave456!')

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(self.conexion.confirmada)
        self.assertTrue(self.conexion.revertida)
        self.assertTrue(self.usuario.check_password(self.password_original))

    def test_rechaza_password_actual_incorrecta(self):
        respuesta = self.enviar_cambio('ClaveNueva456!', password_actual='NoEsLaClave123!')

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(self.conexion.confirmada)
        self.assertTrue(self.conexion.revertida)
        self.assertTrue(self.usuario.check_password(self.password_original))

    def test_pantalla_seguridad_carga_cambio_password_y_segundo_factor(self):
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': False, 'DEBUG': True}):
            with patch.object(aplicacion.login_manager, '_user_callback', return_value=self.usuario):
                with patch.object(
                    aplicacion,
                    'get_db_connection',
                    return_value=ConexionCargaSeguridadFalsa(),
                ):
                    with patch.object(aplicacion, 'registrar_log'):
                        with self.cliente.session_transaction() as sesion:
                            sesion['_user_id'] = str(self.usuario.id)
                            sesion['_fresh'] = True
                        respuesta = self.cliente.get('/cuenta/seguridad')

        contenido = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Cambiar contraseña', contenido)
        self.assertIn('name="password_actual"', contenido)
        self.assertIn('Añade un segundo factor', contenido)
        self.assertIn('name="csrf_token"', contenido)

    def test_cambio_password_desde_pantalla_con_token_csrf_valido(self):
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': True, 'DEBUG': True}):
            with patch.object(aplicacion.login_manager, '_user_callback', return_value=self.usuario):
                with patch.object(aplicacion, 'get_db_connection', return_value=self.conexion):
                    with patch.object(aplicacion, 'registrar_log'):
                        with self.cliente.session_transaction() as sesion:
                            sesion['_user_id'] = str(self.usuario.id)
                            sesion['_fresh'] = True
                        pantalla = self.cliente.get('/cuenta/seguridad')
                        token = re.search(
                            r'name="csrf_token" value="([^"]+)"',
                            pantalla.get_data(as_text=True),
                        )
                        self.assertIsNotNone(token)
                        respuesta = self.cliente.post(
                            '/cuenta/seguridad',
                            data={
                                'accion': 'cambiar_password',
                                'password_actual': self.password_original,
                                'password_nueva': 'ClaveNueva456!',
                                'confirmar_password': 'ClaveNueva456!',
                                'csrf_token': token.group(1),
                            },
                        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.conexion.confirmada)
        self.assertTrue(self.usuario.check_password('ClaveNueva456!'))


if __name__ == '__main__':
    unittest.main()
