import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import app as aplicacion
from models import User


class CursorAnalisisFalso:
    def __init__(self, listas, filas):
        self.listas = iter(listas)
        self.filas = iter(filas)
        self.consultas = []

    def execute(self, consulta, parametros=None):
        self.consultas.append((consulta, parametros))

    def fetchall(self):
        return next(self.listas)

    def fetchone(self):
        return next(self.filas)

    def close(self):
        pass


class ConexionAnalisisFalsa:
    def __init__(self, cursor):
        self.cursor_falso = cursor

    def cursor(self):
        return self.cursor_falso

    def close(self):
        pass


class AnalisisPasteleriaTests(unittest.TestCase):
    def preparar_cliente(self, rol_nombre, usuario):
        self.usuario = User(
            id=32,
            usuario=usuario,
            correo='persona@example.test',
            password='unused',
            rol_id=1 if rol_nombre == 'Cliente' else 2,
            rol_nombre=rol_nombre,
        )
        self.cursor = CursorAnalisisFalso(
            listas=[
                [{
                    'producto_id': 6,
                    'producto': 'Torta de chocolate',
                    'imagen': None,
                    'categoria': 'Pasteles',
                    'unidades': Decimal('8'),
                    'ingresos': Decimal('120.00'),
                }],
                [{
                    'numero': 'FAC-18',
                    'fecha_entrega': date.today() + timedelta(days=2),
                    'monto': Decimal('45.00'),
                    'cliente': 'Cliente de prueba',
                    'productos': 'Torta de chocolate',
                }],
                [{
                    'id': 6,
                    'producto': 'Torta de chocolate',
                    'stock_actual': 2,
                    'stock_minimo': 5,
                    'categoria': 'Pasteles',
                }],
            ],
            filas=[
                {'pedidos_hoy': 2, 'ventas_hoy': Decimal('80.00')},
                {'producto': 'Cheesecake', 'imagen': None, 'unidades': Decimal('2')},
                {'producto_id': 6, 'producto': 'Torta de chocolate', 'imagen': None, 'unidades': Decimal('8')},
                {'hora': 16, 'pedidos': 5},
                {
                    'lotes': 1,
                    'producidas': 8,
                    'vendidas': 5,
                    'merma': 1,
                    'disponibles': 2,
                },
                {'total': 3, 'promedio': Decimal('4.7')},
            ],
        )
        self.conn = ConexionAnalisisFalsa(self.cursor)

    def solicitar_panel(self):
        cliente = aplicacion.app.test_client()
        with patch.dict(aplicacion.app.config, {'WTF_CSRF_ENABLED': False, 'DEBUG': True}):
            with patch.object(aplicacion.login_manager, '_user_callback', return_value=self.usuario):
                with patch.object(User, 'has_permission', return_value=True):
                    with patch.object(aplicacion, 'asegurar_detalles_factura'):
                        with patch.object(aplicacion, 'asegurar_inventario_base'):
                            with patch.object(aplicacion, 'asegurar_resenas'):
                                with patch.object(aplicacion, 'get_db_connection', return_value=self.conn):
                                    with patch.object(aplicacion, 'registrar_log'):
                                        with cliente.session_transaction() as sesion:
                                            sesion['_user_id'] = str(self.usuario.id)
                                            sesion['_fresh'] = True
                                        respuesta = cliente.get('/estadisticas')
        return respuesta

    def test_panel_usa_datos_relacionados_y_muestra_pendientes_sin_inventarlos(self):
        self.preparar_cliente('Encargado', 'encargada')
        respuesta = self.solicitar_panel()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Pulso Diario de', respuesta.get_data(as_text=True))
        self.assertIn('80.00', respuesta.get_data(as_text=True))
        self.assertIn('Ranking de Productos Estrella', respuesta.get_data(as_text=True))
        self.assertIn('Costo pendiente', respuesta.get_data(as_text=True))
        self.assertIn('Merma: 12,50%', respuesta.get_data(as_text=True))
        self.assertIn('16:00–17:00', respuesta.get_data(as_text=True))
        self.assertIn('FAC-18', respuesta.get_data(as_text=True))
        self.assertIn('Productos por reponer', respuesta.get_data(as_text=True))
        self.assertIn('JOIN categorias_producto', self.cursor.consultas[0][0])
        self.assertIn('JOIN estados_documento', self.cursor.consultas[1][0])

    def test_panel_de_cliente_limita_sus_datos_y_oculta_indicadores_del_negocio(self):
        self.preparar_cliente('Cliente', 'cedula-cliente')
        respuesta = self.solicitar_panel()

        self.assertEqual(respuesta.status_code, 200)
        contenido = respuesta.get_data(as_text=True)
        self.assertIn('Tus compras de hoy', contenido)
        self.assertNotIn('Ingresos totales', contenido)
        self.assertNotIn('Productos por reponer', contenido)
        for consulta, parametros in self.cursor.consultas[:5]:
            self.assertIn('LOWER(TRIM(c.correo))', consulta)
            self.assertEqual(parametros, ('persona@example.test', 'cedula-cliente'))

    def test_panel_muestra_estado_vacio_sin_romper_si_aun_no_hay_ventas(self):
        self.preparar_cliente('Encargado', 'encargada')
        self.cursor.listas = iter([[], [], []])
        self.cursor.filas = iter([
            {'pedidos_hoy': 0, 'ventas_hoy': Decimal('0.00')},
            None,
            None,
            None,
            {'lotes': 0, 'producidas': 0, 'vendidas': 0, 'merma': 0, 'disponibles': 0},
            {'total': 0, 'promedio': None},
        ])

        respuesta = self.solicitar_panel()
        contenido = respuesta.get_data(as_text=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Aún no hay ventas para resumir', contenido)
        self.assertIn('Sin ventas este mes', contenido)
        self.assertIn('Sin pedidos con hora registrada', contenido)
        self.assertIn('Sin lotes registrados este mes', contenido)
        self.assertIn('No hay entregas programadas', contenido)
        self.assertIn('Sin reseñas registradas', contenido)

    def test_panel_muestra_promedio_de_resenas_cuando_existen(self):
        self.preparar_cliente('Encargado', 'encargada')
        respuesta = self.solicitar_panel()
        contenido = respuesta.get_data(as_text=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('4.7 / 5', contenido)
        self.assertIn('3 reseñas registradas', contenido)


if __name__ == '__main__':
    unittest.main()
