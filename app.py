from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "clave_super_secreta"

# Configuración de base de datos (SQLite local)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sistema.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ------------------------
# MODELOS
# ------------------------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=False)
    creditos = db.relationship("Credito", backref="cliente", lazy=True)

class Credito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    plazo_dias = db.Column(db.Integer, nullable=False)
    interes = db.Column(db.Float, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)

# ------------------------
# USUARIO FIJO (DEMO)
# ------------------------
USUARIO = "mjesus40"
CLAVE = "198409"

# ------------------------
# RUTAS
# ------------------------
@app.route("/")
def home():
    if "usuario" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["username"]
        clave = request.form["password"]

        if usuario == USUARIO and clave == CLAVE:
            session["usuario"] = usuario
            flash("Bienvenido, sesión iniciada correctamente", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    flash("Sesión cerrada correctamente", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))
    clientes = Cliente.query.all()
    creditos = Credito.query.all()
    return render_template("dashboard.html", clientes=clientes, creditos=creditos)

@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form["nombre"]
        direccion = request.form["direccion"]

        cliente = Cliente(nombre=nombre, direccion=direccion)
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
        monto = float(request.form["monto"])
        plazo = int(request.form["plazo"])
        interes = float(request.form["interes"])

        credito = Credito(
            cliente_id=cliente_id,
            monto=monto,
            plazo_dias=plazo,
            interes=interes
        )
        db.session.add(credito)
        db.session.commit()

        flash("Crédito agregado con éxito", "success")
        return redirect(url_for("dashboard"))

    return render_template("nuevo_credito.html", clientes=clientes)

@app.route("/liquidacion")
def liquidacion():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("liquidacion.html")

@app.route("/lodging")
def lodging():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("lodging.html")

# ------------------------
# CREACIÓN DE TABLAS
# ------------------------
with app.app_context():
    db.create_all()

# ------------------------
# EJECUCIÓN
# ------------------------
if __name__ == "__main__":
    app.run(debug=True)
