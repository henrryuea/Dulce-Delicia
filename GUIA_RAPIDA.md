# Guía rápida — Dulce Delicia

Sistema Flask de administración de pastelería con CRUD, login protegido, facturación e
inventario. Usa SQLite en desarrollo si no se define `DATABASE_URL`; en Render utiliza
PostgreSQL.

## Arranque local

Desde PowerShell, en la raíz del repositorio:

```powershell
pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
flask --app app crear-admin
python app.py
```

No hay contraseña de administrador predeterminada. Para crear el primer administrador,
`crear-admin` solicita usuario y contraseña (12–128 caracteres) y no la muestra en pantalla.
Para recuperar una cuenta ejecute `flask --app app restablecer-admin`. Los clientes y el
personal pueden solicitar cuenta desde **Crear cuenta**; el acceso solo se activa cuando
un administrador aprueba la solicitud. Acceda a `http://127.0.0.1:5000/login`.

## Módulos administrativos

- **Productos:** alta, consulta, edición y eliminación. El stock inicial se registra en el
  historial; después, las existencias se cambian desde Inventario o mediante una factura.
- **Clientes y proveedores:** formularios validados, listados relacionados y operaciones CRUD.
- **Pedidos y facturación:** busque el cliente por cédula/RUC; si no existe, regístrelo desde
  el pedido. Seleccione productos activos en stock. El sistema calcula el IVA y reserva las
  existencias en una transacción PostgreSQL. Cada abono emite un comprobante único y no puede
  superar el saldo; la factura única se genera cuando el pedido queda totalmente pagado.
  Consulte o imprima los comprobantes desde el historial.
- **Inventario:** consulta de existencias, alertas por mínimo, entradas/salidas y los últimos
  movimientos. No se permite dejar el stock negativo.
- **Sesión:** las rutas administrativas requieren autenticación. Cerrar sesión es una petición
  protegida; cinco intentos incorrectos bloquean temporalmente la cuenta.
- **Roles internos:** `ADMIN` administra catálogo, clientes, proveedores, facturas y solicitudes.
  `STAFF` atiende ventas, abonos e inventario; puede consultar productos y clientes, pero no
  modificar registros maestros, gestionar proveedores ni aprobar cuentas. Estas reglas se
  aplican también en el servidor, no solo ocultando botones.
- **Portal del cliente:** tras la aprobación, cada cliente consulta solo sus propias facturas
  y el catálogo con productos activos/en stock. El portal no permite modificar datos ni
  entrar a módulos administrativos.
- **Autorización:** la cuenta `ADMIN` administra solicitudes. Las cuentas de personal se
  registran como pendientes y obtienen acceso interno solo tras aprobación; no pueden elevarse
  a administrador desde el formulario público.

## PostgreSQL y Render

1. Cree una base PostgreSQL y el servicio web desde [`render.yaml`](./render.yaml).
2. Configure `ADMIN_USERNAME` y `ADMIN_PASSWORD` (12–128 caracteres) como variables privadas de Render
   (contraseña de al menos 12 caracteres); Render genera `SECRET_KEY` y conecta `DATABASE_URL`.
3. Render instala dependencias desde `requirements.txt` y ejecuta Flask con Gunicorn.
4. Complete la prueba: login → listar → agregar → modificar → eliminar → crear pedido → abonar
   → revisar comprobantes → completar saldo → consultar factura y productos relacionados →
   cerrar sesión. Compruebe además que un producto sin stock no se vende ni permite sobrepago.

Los servicios gratuitos pueden suspenderse y las bases gratuitas están sujetas a los límites
y la retención definidos por Render. Para operación continua, habilite el plan y los respaldos
adecuados en Render. No use SQLite en el disco efímero de producción.

Consulte [`README.md`](./README.md) para instalación, variables de entorno y detalles técnicos.
