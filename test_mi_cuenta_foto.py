import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage

from app import app, guardar_foto_perfil


class FotoPerfilTests(unittest.TestCase):
    def crear_archivo_imagen(self, formato='PNG'):
        contenido = io.BytesIO()
        Image.new('RGB', (64, 32), color='salmon').save(contenido, format=formato)
        contenido.seek(0)
        return FileStorage(stream=contenido, filename='foto.local')

    def test_guarda_foto_normalizada_como_jpeg_en_carpeta_de_perfiles(self):
        with TemporaryDirectory() as carpeta:
            with patch.dict(app.config, {'PROFILE_UPLOAD_FOLDER': carpeta}):
                ruta_relativa, ruta_archivo = guardar_foto_perfil(self.crear_archivo_imagen(), 21)

            self.assertTrue(ruta_relativa.startswith('uploads/perfiles/usuario-21-'))
            self.assertEqual(ruta_archivo.suffix, '.jpg')
            with Image.open(ruta_archivo) as imagen:
                self.assertEqual(imagen.format, 'JPEG')
                self.assertEqual(imagen.size, (512, 512))
            self.assertTrue(Path(carpeta, ruta_archivo.name).is_file())

    def test_rechaza_formatos_no_admitidos(self):
        contenido = io.BytesIO(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        archivo = FileStorage(stream=contenido, filename='foto.svg')

        with self.assertRaisesRegex(ValueError, 'JPG, PNG o WEBP'):
            guardar_foto_perfil(archivo, 21)

    def test_rechaza_archivos_mayores_a_cinco_megabytes(self):
        archivo = FileStorage(stream=io.BytesIO(b'x' * (5 * 1024 * 1024 + 1)), filename='foto.png')

        with self.assertRaisesRegex(ValueError, '5 MB'):
            guardar_foto_perfil(archivo, 21)

    def test_muestra_pagina_404_con_respuesta_y_mensaje_tematicos(self):
        respuesta = app.test_client().get('/no-existe')

        self.assertEqual(respuesta.status_code, 404)
        self.assertIn('404 · Receta no encontrada'.encode(), respuesta.data)

    def test_mantiene_el_codigo_http_en_metodos_no_admitidos(self):
        respuesta = app.test_client().put('/mi-cuenta')

        self.assertEqual(respuesta.status_code, 405)
        self.assertIn('Esta acción no está disponible aquí'.encode(), respuesta.data)


if __name__ == '__main__':
    unittest.main()
