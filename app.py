from flask import Flask, render_template

app = Flask(__name__)

PRODUCTOS = [
    {"nombre": "Cheesecake clásico", "descripcion": "Cremoso y delicioso, con base de galleta.", "precio": 18.50, "stock": 8, "imagen": "img/CHEESCAKE.png"},
    {"nombre": "Tarta de frutas", "descripcion": "Fresca y colorida, perfecta para compartir.", "precio": 15.00, "stock": 4, "imagen": "img/TARTADEFRUTA.png"},
    {"nombre": "Mousse de chocolate", "descripcion": "Ligero y suave, con sabor intenso.", "precio": 12.00, "stock": 0, "imagen": "img/MOUSSE.png"},
]

CLIENTES = [
    {"nombre": "Ana Torres", "correo": "ana.torres@email.com", "telefono": "099 111 2233"},
    {"nombre": "Luis Mendoza", "correo": "luis.mendoza@email.com", "telefono": "098 444 5566"},
]

PROVEEDORES = [
    {"empresa": "Lácteos Andinos", "contacto": "María León", "categoria": "Ingredientes", "estado": "Activo"},
    {"empresa": "Frutas del Valle", "contacto": "Carlos Ruiz", "categoria": "Frutas frescas", "estado": "Activo"},
]

FACTURAS = [
    {"numero": "FAC-001", "cliente": "Ana Torres", "fecha": "2026-08-20", "total": 37.00, "estado": "Pagada"},
    {"numero": "FAC-002", "cliente": "Luis Mendoza", "fecha": "2026-08-22", "total": 27.00, "estado": "Pendiente"},
]


@app.route('/')
def inicio():
    empresa = {"nombre": "Dulce Delicia", "ubicacion": "Quito - Ecuador"}
    return render_template("index.html", mensaje="Endulzamos tu día", empresa=empresa, productos=PRODUCTOS)


@app.route('/productos')
def productos():
    return render_template("productos.html", productos=PRODUCTOS)


@app.route('/clientes')
def clientes():
    return render_template("clientes.html", clientes=CLIENTES)


@app.route('/provedores')
@app.route('/proveedores')
def proveedores():
    return render_template("proveedores.html", proveedores=PROVEEDORES)


@app.route('/facturacion')
def facturacion():
    return render_template("facturacion.html", facturas=FACTURAS)


if __name__ == '__main__':
    app.run(debug=True)
