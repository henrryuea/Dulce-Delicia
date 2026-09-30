import unittest
from unittest.mock import Mock, patch

from models import User
from app import app


class CalificarProductoTests(unittest.TestCase):
    def cliente_autenticado(self):
        return User(
            id=41,
            usuario='0102030405',
            correo='clienta@example.test',
            password='irrelevante',
            rol_id=1,
            rol_nombre='Cliente',
        )

    def enviar_resena(self, usuario, cursor, datos):
        conn = Mock()
        conn.cursor.return_value = cursor
        cliente = app.test_client()
        with patch.dict(app.config, {'WTF_CSRF_ENABLED': False}):
            with patch('app.get_db_connection', return_value=conn):
                with patch.object(app.login_manager, '_user_callback', return_value=usuario):
                    with patch('app.registrar_log'):
                        with cliente.session_transaction() as sesion:
                            sesion['_user_id'] = str(usuario.id)
                            sesion['_fresh'] = True
                        respuesta = cliente.post(
                            f'/productos/6/resena', data=datos, follow_redirects=False
                        )
        return respuesta, conn

    def test_cliente_que_compro_el_producto_puede_calificarlo(self):
        usuario = self.cliente_autenticado()
        cursor = Mock()
        cursor.fetchone.side_effect = [
            {'cedula': '0102030405', 'nombre': 'Clienta'},  # obtener_cliente_actual
            {'existe': 1},  # compró el producto
        ]
        respuesta, conn = self.enviar_resena(
            usuario, cursor, {'calificacion': '5', 'comentario': 'Riquísimo, repetiré.'}
        )

        self.assertEqual(respuesta.status_code, 302)
        insercion = next(
            llamada for llamada in cursor.execute.call_args_list
            if 'INSERT INTO resenas_producto' in llamada.args[0]
        )
        self.assertEqual(insercion.args[1], (6, '0102030405', 5, 'Riquísimo, repetiré.'))
        conn.commit.assert_called()

    def test_cliente_que_no_compro_el_producto_no_puede_calificarlo(self):
        usuario = self.cliente_autenticado()
        cursor = Mock()
        cursor.fetchone.side_effect = [
            {'cedula': '0102030405', 'nombre': 'Clienta'},
            None,  # no hay compra relacionada
        ]
        respuesta, conn = self.enviar_resena(
            usuario, cursor, {'calificacion': '5', 'comentario': 'No debería poder.'}
        )

        self.assertEqual(respuesta.status_code, 302)
        for llamada in cursor.execute.call_args_list:
            self.assertNotIn('INSERT INTO resenas_producto', llamada.args[0])

    def test_calificacion_fuera_de_rango_se_rechaza(self):
        usuario = self.cliente_autenticado()
        cursor = Mock()
        cursor.fetchone.side_effect = [
            {'cedula': '0102030405', 'nombre': 'Clienta'},
            {'existe': 1},
        ]
        respuesta, conn = self.enviar_resena(usuario, cursor, {'calificacion': '9'})

        self.assertEqual(respuesta.status_code, 302)
        for llamada in cursor.execute.call_args_list:
            self.assertNotIn('INSERT INTO resenas_producto', llamada.args[0])

    def test_administrador_no_puede_calificar_productos(self):
        usuario = User(
            id=1,
            usuario='admin',
            correo='admin@example.test',
            password='irrelevante',
            rol_id=2,
            rol_nombre='Administrador',
        )
        cursor = Mock()
        respuesta, _ = self.enviar_resena(usuario, cursor, {'calificacion': '5'})

        self.assertEqual(respuesta.status_code, 302)
        cursor.execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
