from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configuración de la base de datos SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# --------- MODELOS ---------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=False)
    prestamos = db.relationship("Prestamo", backref="cliente", lazy=True, cascade="all, delete-orphan")

class Prestamo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    interes = db.Column(db.Float, nullable=False)
    plazo_dias = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    abonos = db.relationship("Abono", backref="prestamo", lazy=True, cascade="all, delete-orphan")

class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey("prestamo.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# --------- LOGIN ---------
USUARIO = "mjesus40"
CLAVE = "198409"

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        if usuario == USUARIO and clave == CLAVE:
            session["usuario"] = usuario
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

# --------- INDEX ---------
@app.route("/index")
def index():
    if "usuario" not in session:
        return redirect(url_for("login"))
    clientes = Cliente.query.all()
    return render_template("index.html", clientes=clientes)

# --------- NUEVO CLIENTE ---------
@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form["nombre"]
        direccion = request.form["direccion"]
        codigo = str(random.randint(10000, 99999))

        cliente = Cliente(nombre=nombre, direccion=direccion, codigo=codigo)
        db.session.add(cliente)
        db.session.commit()

        return redirect(url_for("nuevo_credito", cliente_id=cliente.id))

    return render_template("nuevo_cliente.html")

# --------- NUEVO CRÉDITO ---------
@app.route("/nuevo_credito/<int:cliente_id>", methods=["GET", "POST"])
def nuevo_credito(cliente_id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        monto = float(request.form["monto"])
        interes = float(request.form["interes"])
        plazo = int(request.form["plazo"])

        prestamo = Prestamo(
            cliente_id=cliente.id,
            monto=monto,
            interes=interes,
            plazo_dias=plazo
        )
        db.session.add(prestamo)
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("nuevo_credito.html", cliente=cliente)

# --------- ABONOS ---------
@app.route("/abonar/<int:prestamo_id>", methods=["POST"])
def abonar(prestamo_id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    monto = float(request.form["monto"])
    abono = Abono(prestamo_id=prestamo_id, monto=monto)
    db.session.add(abono)
    db.session.commit()
    return redirect(url_for("index"))

# --------- ELIMINAR CLIENTE ---------
@app.route("/eliminar_cliente/<int:cliente_id>")
def eliminar_cliente(cliente_id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    cliente = Cliente.query.get_or_404(cliente_id)
    db.session.delete(cliente)
    db.session.commit()
    return redirect(url_for("index"))

# --------- INICIALIZACIÓN ---------
@app.before_serving
def inicializar():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
