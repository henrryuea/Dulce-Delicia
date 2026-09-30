import unittest
from decimal import Decimal
import re
from unittest.mock import patch

import app as aplicacion
from models import User


class CursorParametrosFiscalesFalso:
    def __init__(self):
        self.consultas = []
        self.rowcount = 1

    def execute(self, consulta, parametros=None):
        self.consultas.append((consulta, parametros))

    def fetchone(self):
        return {
            'id': 1,
            'codigo': 'iva',
            'nombre': 'IVA',
            'valor': Decimal('15.0000'),
            'activo': True,
            'descripcion': 'IVA aplicado a ventas',
            'actualizado_en': None,
        }

    def close(self):
        pass


class ConexionParametrosFiscalesFalsa:
    def __init__(self):
        self.cursor_falso = CursorParametrosFiscalesFalso()
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


class ParametrosFiscalesTests(unittest.TestCase):
    def setUp(self):
        self.usuario = User(
            id=12,
            usuario='admin_prueba',
            correo='admin@example.test',
            password='unused',
            rol_id=1,
            rol_nombre='Administrador',
        )
        self.conexion = ConexionParametrosFiscalesFalsa()
        self.cliente = aplicacion.app.test_client()
        self.patches = [
            patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': False, 'DEBUG': True}),
            patch.object(aplicacion.login_manager, '_user_callback', return_value=self.usuario),
            patch.object(aplicacion, 'asegurar_parametros_fiscales'),
            patch.object(aplicacion, 'get_db_connection', return_value=self.conexion),
            patch.object(aplicacion, 'registrar_log'),
        ]
        for contexto in self.patches:
            contexto.start()
            self.addCleanup(contexto.stop)
        with self.cliente.session_transaction() as sesion:
            sesion['_user_id'] = str(self.usuario.id)
            sesion['_fresh'] = True

    def test_pantalla_muestra_configuracion_de_iva_y_no_impuestos_sueltos(self):
        respuesta = self.cliente.get('/parametros-fiscales')
        contenido = respuesta.get_data(as_text=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('IVA de facturación', contenido)
        self.assertIn('name="accion" value="actualizar_iva"', contenido)
        self.assertIn('name="csrf_token"', contenido)
        self.assertNotIn('Añadir otro concepto tributario', contenido)

    def test_guarda_iva_por_codigo_y_no_depende_de_identificadores_del_formulario(self):
        respuesta = self.cliente.post(
            '/parametros-fiscales',
            data={'accion': 'actualizar_iva', 'valor': '12.5', 'id': '999'},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.conexion.confirmada)
        consulta, parametros = self.conexion.cursor_falso.consultas[-1]
        self.assertIn("WHERE codigo = 'iva'", consulta)
        self.assertEqual(parametros, (12.5,))

    def test_rechaza_tasas_fuera_de_rango_sin_guardarlas(self):
        respuesta = self.cliente.post(
            '/parametros-fiscales',
            data={'accion': 'actualizar_iva', 'valor': '150'},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(self.conexion.confirmada)
        self.assertEqual(len(self.conexion.cursor_falso.consultas), 0)

    def test_protege_el_cambio_de_iva_con_token_csrf(self):
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': True, 'DEBUG': False}):
            respuesta = self.cliente.post(
                '/parametros-fiscales',
                data={'accion': 'actualizar_iva', 'valor': '12.5'},
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(self.conexion.confirmada)

    def test_actualiza_iva_desde_el_formulario_con_token_csrf_valido(self):
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': True, 'DEBUG': True}):
            pantalla = self.cliente.get('/parametros-fiscales')
            token = re.search(r'name="csrf_token" value="([^"]+)"', pantalla.get_data(as_text=True))
            self.assertIsNotNone(token)
            respuesta = self.cliente.post(
                '/parametros-fiscales',
                data={
                    'accion': 'actualizar_iva',
                    'valor': '13',
                    'csrf_token': token.group(1),
                },
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.conexion.confirmada)

    def test_acepta_porcentaje_iva_con_coma_decimal(self):
        respuesta = self.cliente.post(
            '/parametros-fiscales',
            data={'accion': 'actualizar_iva', 'valor': '15,00'},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.conexion.confirmada)
        self.assertEqual(self.conexion.cursor_falso.consultas[-1][1], (15.0,))

    def test_rechaza_tasa_con_mas_de_dos_decimales(self):
        respuesta = self.cliente.post(
            '/parametros-fiscales',
            data={'accion': 'actualizar_iva', 'valor': '15,125'},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(self.conexion.confirmada)
        self.assertEqual(self.conexion.cursor_falso.consultas, [])


if __name__ == '__main__':
    unittest.main()
