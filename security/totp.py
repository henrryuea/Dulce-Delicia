import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet


def generar_secreto_totp():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def cifrar_secreto_totp(secreto):
    return _fernet().encrypt(secreto.encode('ascii')).decode('ascii')


def descifrar_secreto_totp(secreto_cifrado):
    return _fernet().decrypt(secreto_cifrado.encode('ascii')).decode('ascii')


def periodo_totp_valido(secreto, codigo, timestamp=None, ventana=1):
    if not codigo or len(codigo) != 6 or not codigo.isdigit():
        return None

    instante = int(time.time() if timestamp is None else timestamp)
    periodo_actual = instante // 30
    clave = base64.b32decode(secreto + '=' * (-len(secreto) % 8), casefold=True)
    for periodo in range(periodo_actual - ventana, periodo_actual + ventana + 1):
        contador = struct.pack('>Q', periodo)
        digest = hmac.new(clave, contador, hashlib.sha1).digest()
        desplazamiento = digest[-1] & 0x0F
        valor = struct.unpack('>I', digest[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF
        esperado = f'{valor % 1_000_000:06d}'
        if hmac.compare_digest(esperado, codigo):
            return periodo
    return None


def uri_configuracion_totp(secreto, cuenta, emisor='Dulce Delicia'):
    etiqueta = f'{emisor}:{cuenta}'
    parametros = urlencode({
        'secret': secreto,
        'issuer': emisor,
        'algorithm': 'SHA1',
        'digits': 6,
        'period': 30,
    })
    return f'otpauth://totp/{quote(etiqueta)}?{parametros}'


def _fernet():
    clave = (os.getenv('TOTP_ENCRYPTION_KEY') or '').strip()
    if not clave:
        raise RuntimeError('Falta configurar TOTP_ENCRYPTION_KEY para usar autenticación en dos pasos.')
    try:
        return Fernet(clave.encode('ascii'))
    except (ValueError, UnicodeEncodeError) as error:
        raise RuntimeError('TOTP_ENCRYPTION_KEY no tiene un formato Fernet válido.') from error
