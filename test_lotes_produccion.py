import io
import unittest
from datetime import datetime

from PIL import Image
from werkzeug.datastructures import FileStorage

from app import guardar_imagen_producto, registrar_ventas_en_lotes


class CursorLotesFalso:
    def __init__(self):
        self.resultado = []
        self.inserciones = []
        self.consultas_lotes = 0

    def execute(self, consulta, parametros=None):
        if 'SELECT d.id, d.producto_id, d.cantidad, f.fecha_hora_emision' in consulta:
            self.resultado = [{
                'id': 44,
                'producto_id': 8,
                'cantidad': 7,
                'fecha_hora_emision': datetime(2026, 9, 30, 16, 15),
            }]
        elif 'FROM lotes_produccion l' in consulta:
            self.consultas_lotes += 1
            self.resultado = [
                {
                    'id': 1,
                    'cantidad_producida': 5,
                    'cantidad_vendida': 2,
                    'cantidad_merma': 1,
                },
                {
                    'id': 2,
                    'cantidad_producida': 8,
                    'cantidad_vendida': 1,
                    'cantidad_merma': 0,
                },
            ]
        elif 'INSERT INTO ventas_lote' in consulta:
            self.inserciones.append(parametros)

    def fetchall(self):
        return self.resultado


class LotesProduccionTests(unittest.TestCase):
    def test_asigna_ventas_a_lotes_en_orden_y_descuenta_merma(self):
        cursor = CursorLotesFalso()

        registrar_ventas_en_lotes(cursor, 'FAC-001')

        self.assertEqual(cursor.consultas_lotes, 1)
        self.assertEqual(cursor.inserciones, [(1, 44, 2), (2, 44, 5)])

    def test_guarda_imagen_local_normalizada_a_jpeg(self):
        original = io.BytesIO()
        Image.new('RGB', (400, 200), 'pink').save(original, format='PNG')
        archivo = FileStorage(
            stream=io.BytesIO(original.getvalue()),
            filename='torta.png',
            content_type='image/png',
        )

        resultado = guardar_imagen_producto(archivo)

        with Image.open(io.BytesIO(resultado)) as imagen:
            self.assertEqual(imagen.format, 'JPEG')
            self.assertEqual(imagen.size, (400, 200))

    def test_rechaza_archivo_que_no_es_imagen(self):
        archivo = FileStorage(
            stream=io.BytesIO(b'not an image'),
            filename='imagen.png',
            content_type='image/png',
        )

        with self.assertRaisesRegex(ValueError, 'No se pudo leer'):
            guardar_imagen_producto(archivo)


if __name__ == '__main__':
    unittest.main()
