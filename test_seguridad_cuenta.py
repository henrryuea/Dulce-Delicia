import unittest
import re
import os
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


class CursorTotpPendienteIlegibleFalso:
    def __init__(self):
        self.consulta = ''
        self.parametros = None
        self.rowcount = 0

    def execute(self, consulta, parametros=None):
        self.consulta = consulta
        self.parametros = parametros
        if 'UPDATE usuarios' in consulta:
            self.rowcount = 1

    def fetchone(self):
        return {
            'dos_factores_activo': False,
            'dos_factores_secreto_pendiente': 'token-cifrado-con-una-clave-anterior',
        }

    def close(self):
        pass


class ConexionTotpPendienteIlegibleFalsa:
    def __init__(self):
        self.cursor_falso = CursorTotpPendienteIlegibleFalso()
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


class CursorEsquemaSeguridadFalso:
    def __init__(self, falla=False):
        self.consulta = ''
        self.falla = falla
        self.cerrado = False

    def execute(self, consulta, parametros=None):
        self.consulta = consulta
        if self.falla:
            raise aplicacion.psycopg2.OperationalError('fallo de prueba')

    def close(self):
        self.cerrado = True


class ConexionEsquemaSeguridadFalsa:
    def __init__(self, falla=False):
        self.cursor_falso = CursorEsquemaSeguridadFalso(falla)
        self.confirmada = False
        self.revertida = False
        self.cerrada = False

    def cursor(self):
        return self.cursor_falso

    def commit(self):
        self.confirmada = True

    def rollback(self):
        self.revertida = True

    def close(self):
        self.cerrada = True


class PreparacionEsquemaSeguridadTests(unittest.TestCase):
    def test_agrega_columnas_totp_sin_reiniciar_datos_existentes(self):
        conexion = ConexionEsquemaSeguridadFalsa()
        with patch.object(aplicacion, 'get_db_connection', return_value=conexion):
            aplicacion.asegurar_campos_seguridad_cuenta()

        consulta = conexion.cursor_falso.consulta
        self.assertIn('ADD COLUMN IF NOT EXISTS dos_factores_secreto TEXT', consulta)
        self.assertIn('ADD COLUMN IF NOT EXISTS dos_factores_ultimo_periodo BIGINT', consulta)
        self.assertNotIn('UPDATE usuarios', consulta)
        self.assertTrue(conexion.confirmada)
        self.assertTrue(conexion.cursor_falso.cerrado)
        self.assertTrue(conexion.cerrada)

    def test_revierte_la_transaccion_si_falla_la_migracion(self):
        conexion = ConexionEsquemaSeguridadFalsa(falla=True)
        with patch.object(aplicacion, 'get_db_connection', return_value=conexion):
            with self.assertRaises(aplicacion.psycopg2.OperationalError):
                aplicacion.asegurar_campos_seguridad_cuenta()

        self.assertTrue(conexion.revertida)
        self.assertTrue(conexion.cursor_falso.cerrado)
        self.assertTrue(conexion.cerrada)


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
        self.esquema_patch = patch.object(aplicacion, 'asegurar_campos_seguridad_cuenta')
        self.esquema_patch.start()
        self.addCleanup(self.esquema_patch.stop)

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

    def test_inicia_configuracion_2fa_si_no_hay_clave_especifica(self):
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': False}):
            with patch.dict(os.environ, {'TOTP_ENCRYPTION_KEY': '', 'SECRET_KEY': ''}):
                with patch.object(aplicacion.login_manager, '_user_callback', return_value=self.usuario):
                    with patch.object(aplicacion, 'get_db_connection', return_value=self.conexion):
                        with self.cliente.session_transaction() as sesion:
                            sesion['_user_id'] = str(self.usuario.id)
                            sesion['_fresh'] = True
                        respuesta = self.cliente.post(
                            '/cuenta/seguridad',
                            data={'accion': 'iniciar'},
                            follow_redirects=True,
                        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('Falta configurar TOTP_ENCRYPTION_KEY', respuesta.get_data(as_text=True))
        self.assertTrue(self.conexion.confirmada)
        self.assertTrue(any(
            'dos_factores_secreto_pendiente' in consulta
            for consulta, _ in self.conexion.cursor_falso.consultas
        ))

    def test_reinicia_configuracion_pendiente_cifrada_con_clave_anterior(self):
        conexion = ConexionTotpPendienteIlegibleFalsa()
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': False}):
            with patch.dict(os.environ, {'TOTP_ENCRYPTION_KEY': ''}):
                with patch.object(aplicacion.login_manager, '_user_callback', return_value=self.usuario):
                    with patch.object(aplicacion, 'get_db_connection', return_value=conexion):
                        with self.cliente.session_transaction() as sesion:
                            sesion['_user_id'] = str(self.usuario.id)
                            sesion['_fresh'] = True
                        respuesta = self.cliente.get('/cuenta/seguridad')

        contenido = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Puedes iniciar una nueva configuración', contenido)
        self.assertIn('Configurar aplicación autenticadora', contenido)
        self.assertTrue(conexion.confirmada)
        self.assertIn('dos_factores_secreto_pendiente = NULL', conexion.cursor_falso.consulta)
        self.assertIn('dos_factores_activo = FALSE', conexion.cursor_falso.consulta)

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
