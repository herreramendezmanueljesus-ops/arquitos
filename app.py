from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import random
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///creditos.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# =========================
# MODELOS
# =========================
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=False)
    orden = db.Column(db.Integer, default=1)

    # relación
    creditos = db.relationship("Credito", backref="cliente", cascade="all, delete-orphan")


class Credito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    interes = db.Column(db.Float, nullable=False)
    plazo_dias = db.Column(db.Integer, nullable=False)
    saldo = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=datetime.utcnow)

    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))
    abonos = db.relationship("Abono", backref="credito", cascade="all, delete-orphan")


class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=datetime.utcnow)
    credito_id = db.Column(db.Integer, db.ForeignKey("credito.id"))


# =========================
# RUTAS
# =========================
@app.route("/")
def index():
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template("index.html", clientes=clientes)


@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if request.method == "POST":
        nombre = request.form["nombre"]
        direccion = request.form["direccion"]

        # generar código aleatorio
        codigo = str(random.randint(10000, 99999))

        cliente = Cliente(nombre=nombre, direccion=direccion, codigo=codigo)
        db.session.add(cliente)
        db.session.commit()

        return redirect(url_for("nuevo_credito", cliente_id=cliente.id))
    return render_template("nuevo_cliente.html")


@app.route("/nuevo_credito/<int:cliente_id>", methods=["GET", "POST"])
def nuevo_credito(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.method == "POST":
        monto = float(request.form["monto"])
        interes = float(request.form["interes"])
        plazo = int(request.form["plazo"])
        orden = int(request.form["orden"])

        credito = Credito(
            monto=monto,
            interes=interes,
            plazo_dias=plazo,
            saldo=monto,
            cliente=cliente,
        )
        cliente.orden = orden

        db.session.add(credito)
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("nuevo_credito.html", cliente=cliente)


@app.route("/registrar_abono/<int:cliente_id>", methods=["POST"])
def registrar_abono(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    credito = Credito.query.filter_by(cliente_id=cliente.id).order_by(Credito.id.desc()).first()
    if credito:
        monto = float(request.form["monto"])
        abono = Abono(monto=monto, credito=credito)
        credito.saldo -= monto
        if credito.saldo < 0:
            credito.saldo = 0
        db.session.add(abono)
        db.session.commit()
    return redirect(url_for("index"))


@app.route("/actualizar_orden/<int:cliente_id>", methods=["POST"])
def actualizar_orden(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.orden = int(request.form["orden"])
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/eliminar_cliente/<int:cliente_id>", methods=["POST"])
def eliminar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    db.session.delete(cliente)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/liquidacion")
def liquidacion():
    # últimas 10 fechas de créditos o abonos
    registros = (
        db.session.query(Credito.fecha)
        .distinct()
        .order_by(Credito.fecha.desc())
        .limit(10)
        .all()
    )
    return render_template("liquidacion.html", registros=registros)


# =========================
# INICIALIZAR BASE DE DATOS
# =========================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

