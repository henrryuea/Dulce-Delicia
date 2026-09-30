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
   a la versión y estructura real de esa base. Para el modelo actual, aplica
   `sql/migracion_integridad_relacional.sql` y
   `sql/migracion_normalizar_impuestos.sql` y
   `sql/migracion_produccion_facturas_imagenes.sql` con PostgreSQL 15 o superior.
   La primera aborta (y revierte sus cambios) si detecta saldos de cuota
   inconsistentes o cuotas enlazadas con pagos inexistentes o de otra factura.
   La segunda conserva el desglose histórico de impuestos en `impuestos_factura`
   y luego elimina la columna JSON antigua; aborta si encuentra datos fiscales
   que no puede migrar. La tercera agrega horas, lotes e imágenes locales y
   elimina las URL antiguas de imagen del catálogo; haz respaldo antes de
   aplicarla. No descarga esas imágenes antiguas: el catálogo usa una imagen
   local de reemplazo hasta que se suba un archivo para ese producto.
5. Después de las migraciones, ejecuta `flask auditar-esquema` con la misma
   `DATABASE_URL` del servicio. Debe reportar todas las relaciones, incluida
   la relación de impuestos con documentos y parámetros, y aplicaciones
   pago-cuota consistentes.
6. Después del despliegue, abre `/health`. La respuesta debe ser HTTP 200 e
   indicar `"schema": "ready"`. Un HTTP 503 incluye las tablas o columnas que
   faltan; resuelve el esquema antes de usar el sistema.

No se crea ni se reinicia el esquema completo al arrancar la web. La aplicación
aplica de forma idempotente cambios aditivos de inventario, lotes, imágenes y
relaciones de solicitudes de contacto; estos no sustituyen el esquema ni las
demás migraciones. Los envíos públicos registran las consultas en `solicitudes`
y el personal operativo puede ver las que todavía no están asignadas. Las imágenes del
catálogo se optimizan y guardan en PostgreSQL para que sobrevivan los despliegues.
Las horas de facturas antiguas quedan vacías cuando no hay un dato fiable; la
hora pico se calcula con documentos que sí tienen hora registrada.
Las fotos de perfil todavía se guardan en el sistema de archivos local de Render,
que no es persistente en el plan gratuito.

## Variables de entorno

Render debe generar `SECRET_KEY` de forma aleatoria. Mantén `FLASK_ENV=production`
y `FLASK_DEBUG=false`. `render.yaml` genera `TOTP_ENCRYPTION_KEY` automáticamente
para habilitar autenticación de dos factores. Al sincronizar el Blueprint, Render
guarda el secreto y lo conserva entre despliegues. Si el servicio ya existía y no
se sincroniza el Blueprint, añade esa variable en **Environment** en Render y
asigna un secreto aleatorio persistente. Si esa variable no está definida, la
aplicación deriva la clave de cifrado de la `SECRET_KEY` ya configurada, así que
2FA también funciona en servicios existentes sin sincronizar el Blueprint. La
aplicación acepta tanto una clave Fernet como un secreto aleatorio de Render.
La aplicación prepara de forma idempotente las columnas de seguridad para bases
existentes; la clave debe permanecer estable entre despliegues. Perderla impide
descifrar los secretos 2FA guardados. Si falta, la pantalla de seguridad muestra
el motivo y no permite iniciar la configuración 2FA hasta corregirla; en
producción, `SECRET_KEY` es obligatoria y proporciona esa alternativa.

No cambies ni regeneres el valor de esta variable después de activar 2FA. Si no
la defines, tampoco cambies la `SECRET_KEY`: la clave anterior es necesaria para
descifrar los factores ya registrados. Para entornos locales, crea una clave
Fernet una sola vez con `Fernet.generate_key()` y guárdala en `.env`, que no se
sube a Git.
