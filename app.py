from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import and_

app = Flask(__name__)
app.secret_key = "clave_secreta"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sistema.db"
db = SQLAlchemy(app)

# -----------------------------
# MODELOS
# -----------------------------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orden = db.Column(db.String(50), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=False)
    creditos = db.relationship("Credito", backref="cliente", lazy=True)

class Credito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    plazo = db.Column(db.Integer, nullable=False)
    interes = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    abonos = db.relationship("Abono", backref="credito", lazy=True)

class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    credito_id = db.Column(db.Integer, db.ForeignKey("credito.id"), nullable=False)

# -----------------------------
# USUARIO DE LOGIN FIJO
# -----------------------------
USUARIO = "mjesus40"
CONTRASENA = "198409"

# -----------------------------
# RUTAS
# -----------------------------
@app.route("/")
def home():
    if "usuario" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        contrasena = request.form["contrasena"]

        if usuario == USUARIO and contrasena == CONTRASENA:
            session["usuario"] = usuario
            return redirect(url_for("dashboard"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        orden = request.form["orden"]
        nombre = request.form["nombre"]
        direccion = request.form["direccion"]

        cliente = Cliente(orden=orden, nombre=nombre, direccion=direccion)
        db.session.add(cliente)
        db.session.commit()
        flash("Cliente agregado con éxito", "success")
        return redirect(url_for("dashboard"))

    return render_template("nuevo_cliente.html")

@app.route("/nuevo_credito", methods=["GET", "POST"])
def nuevo_credito():
    if "usuario" not in session:
        return redirect(url_for("login"))

    clientes = Cliente.query.all()

    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        monto = request.form["monto"]
        plazo = request.form["plazo"]
        interes = request.form["interes"]

        credito = Credito(
            monto=float(monto),
            plazo=int(plazo),
            interes=float(interes),
            cliente_id=int(cliente_id),
        )
        db.session.add(credito)
        db.session.commit()
        flash("Crédito agregado con éxito", "success")
        return redirect(url_for("dashboard"))

    return render_template("nuevo_credito.html", clientes=clientes)

@app.route("/liquidacion", methods=["GET", "POST"])
def liquidacion():
    if "usuario" not in session:
        return redirect(url_for("login"))

    abonos = []
    fecha_inicio = fecha_fin = None

    if request.method == "POST":
        fecha_inicio = request.form["fecha_inicio"]
        fecha_fin = request.form["fecha_fin"]

        if fecha_inicio and fecha_fin:
            inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
            fin = datetime.strptime(fecha_fin, "%Y-%m-%d")

            abonos = (
                Abono.query.join(Credito).join(Cliente).filter(
                    and_(Abono.fecha >= inicio, Abono.fecha <= fin)
                ).all()
            )

    return render_template(
        "liquidacion.html",
        abonos=abonos,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
