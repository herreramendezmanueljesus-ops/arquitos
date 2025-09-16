from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string

app = Flask(__name__)
app.secret_key = "clave_secreta"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ==============================
# MODELOS
# ==============================
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)
    orden = db.Column(db.Integer, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    monto = db.Column(db.Float, nullable=False)
    plazo = db.Column(db.Integer, nullable=False)
    interes = db.Column(db.Float, nullable=False)
    saldo = db.Column(db.Float, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    abonos = db.relationship("Abono", backref="cliente", lazy=True)

class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# ==============================
# LOGIN
# ==============================
USUARIO = "mjesus40"
CLAVE = "198409"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        if usuario == USUARIO and clave == CLAVE:
            session["usuario"] = usuario
            return redirect(url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

# ==============================
# RUTAS PRINCIPALES
# ==============================
@app.route("/")
def raiz():
    return redirect(url_for("login"))

@app.route("/index")
def index():
    if "usuario" not in session:
        return redirect(url_for("login"))

    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template("index.html", clientes=clientes)

@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        orden = request.form["orden"]
        nombre = request.form["nombre"]
        direccion = request.form["direccion"]
        monto = float(request.form["monto"])
        plazo = int(request.form["plazo"])
        interes = float(request.form["interes"])

        # Generar código aleatorio único
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        while Cliente.query.filter_by(codigo=codigo).first():
            codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Validar duplicado por nombre
        if Cliente.query.filter_by(nombre=nombre).first():
            flash("El cliente ya existe. Use el código asignado.", "warning")
            return redirect(url_for("nuevo_cliente"))

        cliente = Cliente(
            codigo=codigo,
            orden=orden,
            nombre=nombre,
            direccion=direccion,
            monto=monto,
            plazo=plazo,
            interes=interes,
            saldo=monto
        )
        db.session.add(cliente)
        db.session.commit()
        flash("Cliente creado exitosamente", "success")
        return redirect(url_for("index"))

    return render_template("nuevo_cliente.html")

@app.route("/abonar/<int:cliente_id>", methods=["POST"])
def abonar(cliente_id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    cliente = Cliente.query.get_or_404(cliente_id)
    monto_abono = float(request.form["monto_abono"])

    if monto_abono <= 0:
        flash("El abono debe ser mayor a 0", "warning")
        return redirect(url_for("index"))

    if monto_abono > cliente.saldo:
        flash("El abono no puede ser mayor al saldo", "danger")
        return redirect(url_for("index"))

    cliente.saldo -= monto_abono
    abono = Abono(cliente_id=cliente.id, monto=monto_abono)
    db.session.add(abono)
    db.session.commit()

    flash("Abono registrado correctamente", "success")
    return redirect(url_for("index"))

@app.route("/liquidacion", methods=["GET", "POST"])
def liquidacion():
    if "usuario" not in session:
        return redirect(url_for("login"))

    fecha_inicio = None
    fecha_fin = None
    abonos = []
    prestamos = []
    total_abonos = 0
    total_prestamos = 0
    caja = 0

    if request.method == "POST":
        fecha_inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d")
        fecha_fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d")

        abonos = Abono.query.filter(Abono.fecha >= fecha_inicio, Abono.fecha <= fecha_fin).all()
        prestamos = Cliente.query.filter(Cliente.fecha_creacion >= fecha_inicio, Cliente.fecha_creacion <= fecha_fin).all()

        total_abonos = sum([a.monto for a in abonos])
        total_prestamos = sum([p.monto for p in prestamos])
        caja = total_abonos - total_prestamos

    return render_template(
        "liquidacion.html",
        abonos=abonos,
        prestamos=prestamos,
        total_abonos=total_abonos,
        total_prestamos=total_prestamos,
        caja=caja,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )

# ==============================
# INICIO DB
# ==============================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
