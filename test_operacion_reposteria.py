import base64
import os
import re
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet, InvalidToken
from models import User
from app import (
    app,
    asegurar_relaciones_solicitudes,
    puede_ver_productos_futuros,
    registro_es_automatizado,
    rol_requiere_aprobacion,
    validar_password_segura,
)

from security.totp import (
    cifrar_secreto_totp,
    descifrar_secreto_totp,
    periodo_totp_valido,
    uri_configuracion_totp,
)


class TotpTests(unittest.TestCase):
    def setUp(self):
        self.secreto = base64.b32encode(b'12345678901234567890').decode('ascii').rstrip('=')

    def test_acepta_codigo_rfc_6238_y_devuelve_periodo(self):
        self.assertEqual(periodo_totp_valido(self.secreto, '287082', timestamp=59, ventana=0), 1)

    def test_rechaza_codigo_invalido_y_formato_incorrecto(self):
        self.assertIsNone(periodo_totp_valido(self.secreto, '000000', timestamp=59, ventana=0))
        self.assertIsNone(periodo_totp_valido(self.secreto, '12345', timestamp=59, ventana=0))

    def test_cifra_semilla_con_clave_separada(self):
        clave = Fernet.generate_key().decode('ascii')
        with patch.dict(os.environ, {'TOTP_ENCRYPTION_KEY': clave}):
            cifrado = cifrar_secreto_totp(self.secreto)
            self.assertNotEqual(cifrado, self.secreto)
            self.assertEqual(descifrar_secreto_totp(cifrado), self.secreto)

    def test_rechaza_clave_de_cifrado_incorrecta(self):
        clave = Fernet.generate_key().decode('ascii')
        with patch.dict(os.environ, {'TOTP_ENCRYPTION_KEY': Fernet.generate_key().decode('ascii')}):
            cifrado = cifrar_secreto_totp(self.secreto)
        with patch.dict(os.environ, {'TOTP_ENCRYPTION_KEY': clave}):
            with self.assertRaises(InvalidToken):
                descifrar_secreto_totp(cifrado)

    def test_uri_se_identifica_como_totp_para_dulce_delicia(self):
        uri = uri_configuracion_totp(self.secreto, 'cliente')
        self.assertTrue(uri.startswith('otpauth://totp/'))
        self.assertIn('issuer=Dulce+Delicia', uri)
        self.assertIn(f'secret={self.secreto}', uri)


class EntregaPedidoTests(unittest.TestCase):
    def setUp(self):
        from app import validar_datos_entrega

        self.validar = validar_datos_entrega

    def formulario(self, fecha='2026-10-01', modalidad='domicilio', ubicacion='Av. Central 123'):
        return SimpleNamespace(
            fecha_entrega=SimpleNamespace(data=fecha),
            modalidad_entrega=SimpleNamespace(data=modalidad),
            ubicacion_entrega=SimpleNamespace(data=ubicacion),
        )

    def test_valida_entrega_a_domicilio_y_conserva_ubicacion(self):
        resultado = self.validar(self.formulario(), 'Factura', date(2026, 9, 27))
        self.assertEqual(resultado, (date(2026, 10, 1), 'domicilio', 'Av. Central 123'))

    def test_retiro_local_no_exige_direccion(self):
        resultado = self.validar(self.formulario(modalidad='retiro_local', ubicacion=''), 'Factura', date(2026, 9, 27))
        self.assertEqual(resultado, (date(2026, 10, 1), 'retiro_local', None))

    def test_rechaza_domicilio_sin_direccion(self):
        resultado = self.validar(self.formulario(ubicacion=''), 'Factura', date(2026, 9, 27))
        self.assertIsInstance(resultado, str)
        self.assertIn('dirección', resultado)

    def test_rechaza_entrega_anterior_a_emision(self):
        resultado = self.validar(self.formulario(fecha='2026-09-26'), 'Factura', date(2026, 9, 27))
        self.assertIsInstance(resultado, str)
        self.assertIn('anterior', resultado)

    def test_cotizacion_no_guarda_datos_de_entrega(self):
        self.assertEqual(self.validar(self.formulario(), 'Cotizacion', date(2026, 9, 27)), (None, None, None))


class RegistroSecurityTests(unittest.TestCase):
    def test_clave_exige_longitud_y_tres_clases_no_simbolos_obligatorios(self):
        self.assertTrue(validar_password_segura('dulceDulce123'))
        self.assertTrue(validar_password_segura('dulce-delicia1'))
        self.assertFalse(validar_password_segura('Dulce123!'))
        self.assertFalse(validar_password_segura('dulcedulcedulce'))

    def test_proteccion_automatica_rechaza_campo_oculto_rellenado(self):
        self.assertTrue(registro_es_automatizado('bot.example', 100, ahora=105))

    def test_proteccion_automatica_rechaza_envio_inmediato_y_formulario_vencido(self):
        self.assertTrue(registro_es_automatizado('', 100, ahora=101))
        self.assertTrue(registro_es_automatizado('', 100, ahora=3701))

    def test_proteccion_automatica_permite_envio_humano_dentro_de_una_hora(self):
        self.assertFalse(registro_es_automatizado('', 100, ahora=103))

    def test_registro_muestra_roles_solicitables_incluido_administrador(self):
        roles = [
            {'id': 1, 'nombre': 'Administrador'},
            {'id': 2, 'nombre': 'Cliente'},
            {'id': 3, 'nombre': 'Vendedor'},
        ]
        with patch('app.Role.get_all', return_value=roles):
            respuesta = app.test_client().get('/registro')

        contenido = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertRegex(contenido, r'<option[^>]*value="1"[^>]*>Administrador</option>')
        self.assertRegex(contenido, r'<option[^>]*value="2"[^>]*>Cliente</option>')
        self.assertRegex(contenido, r'<option[^>]*value="3"[^>]*>Vendedor</option>')
        self.assertIn('aviso-privacidad', contenido)
        self.assertIn('Protección automática contra envíos no deseados', contenido)

    def test_todos_los_roles_solicitados_solicitan_aprobacion_salvo_cliente(self):
        for rol in ('Administrador', 'Encargado', 'Repostero', 'Vendedor'):
            with self.subTest(rol=rol):
                self.assertTrue(rol_requiere_aprobacion(rol))
        self.assertFalse(rol_requiere_aprobacion('Cliente'))

    def test_aviso_privacidad_menciona_ley_y_derechos(self):
        respuesta = app.test_client().get('/aviso-privacidad')
        contenido = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Ley Orgánica de Protección de Datos Personales', contenido)
        self.assertIn('rectificación', contenido)


class CatalogVisibilityTests(unittest.TestCase):
    def usuario(self, autenticado, rol, permiso_futuros):
        return SimpleNamespace(
            is_authenticated=autenticado,
            has_role=lambda *roles: rol in roles,
            has_permission=lambda codigo: permiso_futuros and codigo == 'productos.futuros',
        )

    def test_solo_cuenta_autenticada_con_permiso_ve_lanzamientos(self):
        self.assertFalse(puede_ver_productos_futuros(self.usuario(False, 'Cliente', True)))
        self.assertFalse(puede_ver_productos_futuros(self.usuario(True, 'Vendedor', True)))
        self.assertFalse(puede_ver_productos_futuros(self.usuario(True, 'Cliente', False)))
        self.assertTrue(puede_ver_productos_futuros(self.usuario(True, 'Cliente', True)))

    def test_portada_solicita_seis_productos_y_filtra_lanzamientos_para_visitantes(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [[], []]
        conn = Mock()
        conn.cursor.return_value = cursor

        with patch('app.get_db_connection', return_value=conn):
            respuesta = app.test_client().get('/')

        self.assertEqual(respuesta.status_code, 200)
        consulta_portada = cursor.execute.call_args_list[-1].args[0]
        parametros = cursor.execute.call_args_list[-1].args[1]
        self.assertIn('p.disponible = TRUE OR (%s = TRUE AND p.disponible = FALSE)', consulta_portada)
        self.assertIn('LIMIT 6', consulta_portada)
        self.assertEqual(parametros, (False,))

    def test_catalogo_filtra_lanzamientos_en_la_consulta_para_visitantes(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [[], []]
        conn = Mock()
        conn.cursor.return_value = cursor

        with patch('app.get_db_connection', return_value=conn):
            respuesta = app.test_client().get('/productos')

        self.assertEqual(respuesta.status_code, 200)
        consulta_productos = cursor.execute.call_args_list[-1].args[0]
        parametros = cursor.execute.call_args_list[-1].args[1]
        self.assertIn('p.disponible = TRUE OR (%s = TRUE AND p.disponible = FALSE)', consulta_productos)
        self.assertEqual(parametros[0], False)

    def test_contacto_muestra_redes_y_referencia_de_mapa_quitena(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [[], []]
        conn = Mock()
        conn.cursor.return_value = cursor

        with patch('app.get_db_connection', return_value=conn):
            respuesta = app.test_client().get('/')

        contenido = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('https://www.facebook.com/login/', contenido)
        self.assertIn('https://www.instagram.com/accounts/login/', contenido)
        self.assertIn('https://www.tiktok.com/login', contenido)
        self.assertIn('https://web.whatsapp.com/', contenido)
        self.assertIn('Parque+La+Carolina%2C+Quito%2C+Ecuador', contenido)
        self.assertIn('referencia, no dirección del local', contenido)
        self.assertIn('rel="noopener noreferrer"', contenido)

    def test_esquema_contacto_agrega_relaciones_sin_borrar_datos(self):
        cursor = Mock()
        conn = Mock()
        conn.cursor.return_value = cursor

        with patch('app.get_db_connection', return_value=conn):
            asegurar_relaciones_solicitudes()

        consultas = [llamada.args[0] for llamada in cursor.execute.call_args_list]
        self.assertIn('ADD COLUMN IF NOT EXISTS usuario_id INT', consultas[0])
        self.assertIn('ADD COLUMN IF NOT EXISTS categoria_producto_id INT', consultas[0])
        self.assertIn('FOREIGN KEY (usuario_id)', consultas[1])
        self.assertIn('FOREIGN KEY (categoria_producto_id)', consultas[1])
        self.assertTrue(any('idx_solicitudes_usuario' in consulta for consulta in consultas))
        conn.commit.assert_called_once()
        cursor.close.assert_called_once()
        conn.close.assert_called_once()

    def test_bandeja_repostero_incluye_solicitudes_publicas_sin_asignar(self):
        cursor = Mock()
        cursor.fetchall.return_value = []
        conn = Mock()
        conn.cursor.return_value = cursor
        usuario = User(
            id=18,
            usuario='repostero_prueba',
            correo='repostero@example.test',
            password='irrelevante',
            rol_id=3,
            rol_nombre='Repostero',
        )
        cliente = app.test_client()

        with patch.object(app.login_manager, '_user_callback', return_value=usuario):
            with patch('app.get_db_connection', return_value=conn):
                with patch('app.registrar_log'):
                    with cliente.session_transaction() as sesion:
                        sesion['_user_id'] = str(usuario.id)
                        sesion['_fresh'] = True
                    respuesta = cliente.get('/solicitudes')

        self.assertEqual(respuesta.status_code, 200)
        consulta = cursor.execute.call_args_list[0].args[0]
        self.assertIn('s.responsable_id IS NULL', consulta)

    def test_csrf_rechazado_en_contacto_responde_json_y_no_html(self):
        cliente = app.test_client()
        with patch.dict(app.config, {'WTF_CSRF_ENABLED': True}):
            respuesta = cliente.post(
                '/api/solicitudes',
                json={
                    'nombre': 'Ana Perez',
                    'correo': 'ana@example.com',
                    'telefono': '0991234567',
                    'tipo_producto': 'Cheesecake',
                    'mensaje': 'Quisiera consultar por un pedido para mi evento.'
                },
                headers={'Accept': 'application/json'}
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(respuesta.is_json)
        self.assertFalse(respuesta.get_json()['ok'])
        self.assertIn('sesión del formulario', respuesta.get_json()['mensaje'])

    def test_consulta_de_contacto_se_envia_con_csrf_y_no_asigna_al_cliente_como_responsable(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [[], []]
        cursor.fetchone.side_effect = [{'id': 3}, None, {'id': 41}]
        conn = Mock()
        conn.cursor.return_value = cursor
        cliente = app.test_client()

        with patch('app.get_db_connection', return_value=conn):
            portada = cliente.get('/')
            token_match = re.search(
                r'<input type="hidden" name="csrf_token" value="([^"]+)"',
                portada.get_data(as_text=True)
            )
            self.assertIsNotNone(token_match)
            respuesta = cliente.post(
                '/api/solicitudes',
                json={
                    'nombre': 'Ana Perez',
                    'correo': 'ana@example.com',
                    'telefono': '0991234567',
                    'tipo_producto': 'Cheesecake',
                    'mensaje': 'Quisiera consultar por un pedido para mi evento.'
                },
                headers={'X-CSRFToken': token_match.group(1)}
            )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.get_json(), {'ok': True, 'id': 41})
        consulta_insert = cursor.execute.call_args_list[-1].args[0]
        self.assertIn('usuario_id, categoria_producto_id)', consulta_insert)
        self.assertNotIn('responsable_id', consulta_insert)
        self.assertEqual(conn.commit.call_count, 2)

    def test_catalogo_pagina_de_doce_productos(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [],
            [
                {
                    'id': index,
                    'nombre': f'Producto {index}',
                    'descripcion': 'Producto de prueba con descripción',
                    'categoria_nombre': 'Postres individuales',
                    'disponible': True,
                    'precio_base': 2.50,
                    'imagen': None,
                    'detalles_relacionados': 0,
                }
                for index in range(1, 14)
            ],
        ]
        conn = Mock()
        conn.cursor.return_value = cursor

        with patch('app.get_db_connection', return_value=conn):
            respuesta = app.test_client().get('/productos')

        contenido = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('1 - 12', contenido)
        self.assertIn('const REGISTROS_POR_PAGINA = 12;', contenido)


class LoginVisualTests(unittest.TestCase):
    def test_inicio_sesion_usa_icono_de_cafeteria_y_no_escudo_generico(self):
        respuesta = app.test_client().get('/login')
        contenido = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('login-brand-mark', contenido)
        self.assertIn('bi-cup-hot-fill', contenido)
        self.assertNotIn('bi-shield-lock-fill', contenido)


if __name__ == '__main__':
    unittest.main()
