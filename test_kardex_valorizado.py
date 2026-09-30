import unittest
from decimal import Decimal

from app import calcular_kardex_valorizado


def movimiento(tipo, cantidad, costo_unitario=None, **extra):
    datos = {
        'tipo': tipo,
        'cantidad': cantidad,
        'costo_unitario': costo_unitario,
        'fecha': None,
        'referencia': None,
        'descripcion': None,
        'automatico': False,
        'factura_numero': None,
        'usuario_nombre': None,
    }
    datos.update(extra)
    return datos


class KardexValorizadoTests(unittest.TestCase):
    def test_promedio_ponderado_con_dos_compras_y_una_venta(self):
        filas, totales = calcular_kardex_valorizado([
            movimiento('entrada', 10, Decimal('2.00')),
            movimiento('entrada', 5, Decimal('3.50')),
            movimiento('salida', 8),
        ])

        # Primera entrada: 10 * 2.00 = 20.00
        self.assertEqual(filas[0]['saldo_cantidad'], Decimal(10))
        self.assertEqual(filas[0]['saldo_valor'], Decimal('20.00'))
        # Segunda entrada: promedio (20 + 17.50) / 15 = 2.50
        self.assertEqual(filas[1]['saldo_cantidad'], Decimal(15))
        self.assertEqual(filas[1]['saldo_costo'], Decimal('2.50'))
        self.assertEqual(filas[1]['saldo_valor'], Decimal('37.50'))
        # Salida valorada al promedio vigente: 8 * 2.50 = 20.00
        self.assertEqual(filas[2]['salida_costo'], Decimal('2.50'))
        self.assertEqual(filas[2]['salida_total'], Decimal('20.00'))
        self.assertEqual(filas[2]['saldo_cantidad'], Decimal(7))
        self.assertEqual(filas[2]['saldo_valor'], Decimal('17.50'))

        self.assertEqual(totales['entrada_cantidad'], Decimal(15))
        self.assertEqual(totales['entrada_valor'], Decimal('37.50'))
        self.assertEqual(totales['salida_cantidad'], Decimal(8))
        self.assertEqual(totales['salida_valor'], Decimal('20.00'))
        self.assertEqual(totales['saldo_cantidad'], Decimal(7))
        self.assertEqual(totales['saldo_valor'], Decimal('17.50'))
        self.assertEqual(totales['saldo_costo'], Decimal('2.50'))

    def test_entrada_sin_costo_adopta_el_promedio_vigente(self):
        filas, _ = calcular_kardex_valorizado([
            movimiento('entrada', 4, Decimal('3.00')),
            movimiento('entrada', 6, None),
        ])

        # La segunda entrada se valora al promedio de 3.00 => saldo 10 * 3.00
        self.assertEqual(filas[1]['entrada_costo'], Decimal('3.00'))
        self.assertEqual(filas[1]['saldo_cantidad'], Decimal(10))
        self.assertEqual(filas[1]['saldo_valor'], Decimal('30.00'))

    def test_primera_entrada_sin_costo_queda_en_cero(self):
        filas, totales = calcular_kardex_valorizado([
            movimiento('entrada', 5, None),
            movimiento('salida', 2),
        ])

        self.assertEqual(filas[0]['entrada_costo'], Decimal('0.00'))
        self.assertEqual(filas[1]['salida_costo'], Decimal('0.00'))
        self.assertEqual(totales['saldo_cantidad'], Decimal(3))
        self.assertEqual(totales['saldo_valor'], Decimal('0.00'))

    def test_salida_total_deja_saldo_en_cero(self):
        filas, totales = calcular_kardex_valorizado([
            movimiento('entrada', 10, Decimal('1.50')),
            movimiento('salida', 10),
        ])

        self.assertEqual(totales['saldo_cantidad'], Decimal(0))
        self.assertEqual(totales['saldo_valor'], Decimal('0.00'))
        self.assertEqual(filas[1]['salida_total'], Decimal('15.00'))

    def test_historial_vacio(self):
        filas, totales = calcular_kardex_valorizado([])

        self.assertEqual(filas, [])
        self.assertEqual(totales['saldo_cantidad'], Decimal(0))
        self.assertEqual(totales['saldo_valor'], Decimal('0.00'))


if __name__ == '__main__':
    unittest.main()
