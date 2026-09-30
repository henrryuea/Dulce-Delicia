# Despliegue en Render

## Servicio web

Este repositorio incluye `render.yaml` para instalar `requirements.txt`, iniciar
Flask con Gunicorn y comprobar `/health`. Si el servicio ya existe en Render,
configura los mismos valores en **Settings**:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
- **Health Check Path:** `/health`

`requirements.txt` debe incluir `gunicorn`; no quites esa dependencia. Render
debe desplegar el mismo repositorio y rama donde están estos archivos.

## PostgreSQL

1. Crea o selecciona una base de datos PostgreSQL persistente en Render.
2. En las variables de entorno del servicio web, define `DATABASE_URL` con la
   **Internal Database URL** de esa base (no la URL externa). No publiques esa
   URL ni la guardes en Git.
3. Para una base **nueva y vacía**, ejecuta una sola vez `sql/esquema.sql` en
   esa base. El script crea el esquema y catálogos iniciales; no crea usuarios,
   clientes ni productos.
4. Para una base que ya contiene datos, **no ejecutes `sql/esquema.sql`**.
   Haz primero un respaldo y aplica únicamente las migraciones que correspondan
   a la versión y estructura real de esa base.
5. Después del despliegue, abre `/health`. La respuesta debe ser HTTP 200 e
   indicar `"schema": "ready"`. Un HTTP 503 incluye las tablas o columnas que
   faltan; resuelve el esquema antes de usar el sistema.

No se crea ni se reinicia el esquema completo al arrancar la web. La aplicación
sí aplica una migración aditiva del inventario; esta no sustituye el esquema ni
las demás migraciones. Las fotos de perfil guardadas en el sistema de archivos
local de Render no son almacenamiento persistente; configura un servicio de
objetos o almacenamiento persistente antes de depender de ellas.

## Variables de entorno

Render debe generar `SECRET_KEY` de forma aleatoria. Mantén `FLASK_ENV=production`
y `FLASK_DEBUG=false`. Para habilitar autenticación de dos factores, configura
`TOTP_ENCRYPTION_KEY` con una clave Fernet y consérvala fuera del repositorio;
perderla impide descifrar los secretos 2FA guardados.
