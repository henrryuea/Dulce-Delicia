import unittest

from app import (
    calcular_impuestos,
    identificacion_valida_para_tipo,
    normalizar_detalles_factura,
    obtener_siguiente_numero_documento,
)


class CursorCatalogoFalso:
    def __init__(self, productos):
        self.productos = productos

    def execute(self, consulta, parametros):
        self.resultado = [
            producto for producto in self.productos
            if producto['id'] in parametros[0]
        ]

    def fetchall(self):
        return self.resultado


class CursorNumeracionFalso:
    def __init__(self, numeros):
        self.numeros = numeros

    def execute(self, consulta, parametros):
        prefijo = parametros[0][:-1]
        self.resultado = [{'numero': numero} for numero in self.numeros if numero.startswith(prefijo)]

    def fetchall(self):
        return self.resultado


class FacturacionExtensionesTests(unittest.TestCase):
    def test_tipo_de_identificacion_exige_longitud_correspondiente(self):
        self.assertTrue(identificacion_valida_para_tipo('cedula', '1234567890'))
        self.assertTrue(identificacion_valida_para_tipo('ruc', '1234567890123'))
        self.assertFalse(identificacion_valida_para_tipo('cedula', '1234567890123'))
        self.assertFalse(identificacion_valida_para_tipo('ruc', '1234567890'))
        self.assertFalse(identificacion_valida_para_tipo('pasaporte', '1234567890'))

    def test_nuevo_numero_comercial_usa_secuencia_de_nueve_digitos(self):
        cursor = CursorNumeracionFalso(['001-001-000000008', '001-001-0003'])

        self.assertEqual(
            obtener_siguiente_numero_documento(cursor, 'Factura'),
            '001-001-000000009',
        )

    def test_calcula_tasas_activas_y_conserva_el_desglose(self):
        total, desglose = calcular_impuestos(
            100,
            [
                {'codigo': 'iva', 'nombre': 'IVA', 'porcentaje': 15.0, 'descripcion': None},
                {'codigo': 'tasa_local', 'nombre': 'Tasa local', 'porcentaje': 2.5, 'descripcion': None},
            ],
        )

        self.assertEqual(total, 17.5)
        self.assertEqual([impuesto['monto'] for impuesto in desglose], [15.0, 2.5])

    def test_normaliza_producto_y_adicional_con_unidad_y_detalle(self):
        cursor = CursorCatalogoFalso([
            {'id': 4, 'nombre': 'Torta', 'descripcion': 'Bizcocho artesanal', 'precio_base': 10}
        ])

        lineas = normalizar_detalles_factura(cursor, [
            {'id': 4, 'producto': 'Torta', 'cantidad': 2, 'precio': 99, 'ajuste': 1},
            {
                'id': None, 'producto': 'Decoración', 'descripcion': 'Aplicar en la parte superior',
                'cantidad': 0.5, 'unidad_medida': 'lb', 'precio': 3, 'es_adicional': True,
            },
        ], usar_precio_catalogo=True)

        self.assertEqual(len(lineas), 2)
        self.assertEqual(lineas[0]['precio'], 10)
        self.assertEqual(lineas[0]['descripcion'], 'Bizcocho artesanal')
        self.assertEqual(lineas[0]['total'], 22)
        self.assertTrue(lineas[1]['es_adicional'])
        self.assertEqual(lineas[1]['unidad_medida'], 'lb')
        self.assertEqual(lineas[1]['total'], 1.5)

    def test_no_permite_producto_fuera_del_catalogo_ni_adicional_sin_nombre(self):
        cursor = CursorCatalogoFalso([])

        with self.assertRaisesRegex(ValueError, 'no existe'):
            normalizar_detalles_factura(cursor, [
                {'id': 99, 'producto': 'Desconocido', 'cantidad': 1, 'precio': 2}
            ])

        with self.assertRaisesRegex(ValueError, 'nombre'):
            normalizar_detalles_factura(cursor, [
                {'producto': '', 'cantidad': 1, 'precio': 2, 'es_adicional': True}
            ])


if __name__ == '__main__':
    unittest.main()
