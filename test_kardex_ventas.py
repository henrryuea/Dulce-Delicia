import unittest

from app import ajustar_kardex_venta


class KardexCursorFalso:
    def __init__(self, stock, movimientos=None):
        self.stock = dict(stock)
        self.movimientos = movimientos or []
        self.resultado = []
        self.escrituras = []

    def execute(self, consulta, parametros):
        if 'SELECT producto_id, tipo, cantidad' in consulta:
            self.resultado = self.movimientos
        elif 'SELECT id, nombre, stock_actual' in consulta:
            self.resultado = [
                {'id': producto_id, 'nombre': f'Producto {producto_id}', 'stock_actual': cantidad}
                for producto_id, cantidad in self.stock.items()
                if producto_id in parametros[0]
            ]
        else:
            self.escrituras.append((consulta, parametros))
            if 'UPDATE productos' in consulta:
                cantidad, producto_id = parametros
                self.stock[producto_id] = cantidad

    def fetchall(self):
        return self.resultado


class KardexVentasTests(unittest.TestCase):
    def test_rechaza_venta_que_supera_el_stock_sin_escribir_movimientos(self):
        cursor = KardexCursorFalso({1: 2})

        error = ajustar_kardex_venta(
            cursor, 'FAC-001', [{'id': 1, 'cantidad': 3}], 7, 'Factura',
            force_tracking=True
        )

        self.assertIn('Stock insuficiente', error)
        self.assertIn('Disponibles para este pedido: 2', error)
        self.assertIn('solicitadas: 3', error)
        self.assertEqual(cursor.stock[1], 2)
        self.assertEqual(cursor.escrituras, [])

    def test_editar_venta_no_permite_superar_stock_incluida_la_cantidad_ya_reservada(self):
        cursor = KardexCursorFalso(
            {1: 2},
            [{'producto_id': 1, 'tipo': 'salida', 'cantidad': 3}]
        )

        error = ajustar_kardex_venta(
            cursor, 'FAC-EDIT-001', [{'id': 1, 'cantidad': 6}], 7, 'Factura'
        )

        self.assertIn('Disponibles para este pedido: 5', error)
        self.assertIn('solicitadas: 6', error)
        self.assertEqual(cursor.stock[1], 2)
        self.assertEqual(cursor.escrituras, [])

    def test_registra_salida_automatica_y_actualiza_stock(self):
        cursor = KardexCursorFalso({1: 5})

        error = ajustar_kardex_venta(
            cursor, 'FAC-002', [{'id': 1, 'cantidad': 3}], 7, 'Factura',
            force_tracking=True
        )

        self.assertIsNone(error)
        self.assertEqual(cursor.stock[1], 2)
        movimiento = next(
            params for consulta, params in cursor.escrituras
            if 'INSERT INTO kardex_movimientos' in consulta
        )
        self.assertEqual(movimiento, (1, 'salida', 3, 'FAC-002', 'Salida automática por venta', 7, 'FAC-002'))

    def test_editar_cantidad_reconcilia_solo_la_diferencia(self):
        cursor = KardexCursorFalso(
            {1: 2},
            [{'producto_id': 1, 'tipo': 'salida', 'cantidad': 3}]
        )

        error = ajustar_kardex_venta(
            cursor, 'FAC-003', [{'id': 1, 'cantidad': 1}], 7, 'Factura'
        )

        self.assertIsNone(error)
        self.assertEqual(cursor.stock[1], 4)
        movimiento = next(
            params for consulta, params in cursor.escrituras
            if 'INSERT INTO kardex_movimientos' in consulta
        )
        self.assertEqual(movimiento[1:5], ('entrada', 2, 'FAC-003', 'Ajuste automático por edición de venta'))

    def test_revertir_venta_reintegra_existencias(self):
        cursor = KardexCursorFalso(
            {1: 2},
            [{'producto_id': 1, 'tipo': 'salida', 'cantidad': 3}]
        )

        error = ajustar_kardex_venta(cursor, 'FAC-004', [], 7, 'Cotizacion')

        self.assertIsNone(error)
        self.assertEqual(cursor.stock[1], 5)
        movimiento = next(
            params for consulta, params in cursor.escrituras
            if 'INSERT INTO kardex_movimientos' in consulta
        )
        self.assertEqual(movimiento[1:5], ('entrada', 3, 'FAC-004', 'Reverso automático por cambio o eliminación de venta'))


if __name__ == '__main__':
    unittest.main()
