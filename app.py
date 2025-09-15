from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
db = SQLAlchemy(app)

# =====================
# MODELOS
# =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=True)
    orden = db.Column(db.Integer, default=0)
    creditos = db.relationship("Credito", backref="cliente", lazy=True)

class Credito(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    interes = db.Column(db.Float, nullable=False)
    plazo_dias = db.Column(db.Integer, nullable=False)
    fecha_inicio = db.Column(db.Date, default=datetime.utcnow)
    abonos = db.relationship("Abono", backref="credito", lazy=True)

class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    credito_id = db.Column(db.Integer, db.ForeignKey("credito.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# =====================
# INICIALIZAR BASE
# =====================
@app.before_first_request
def crear_tablas_y_admin():
    db.create_all()
    if not User.query.filter_by(username="mjesus40").first():
        u = User(username="mjesus40", password_hash="198409")
        db.session.add(u)
        db.session.commit()

# =====================
# RUTAS
# =====================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username, password_hash=password).first()
        if user:
            session["user"] = user.username
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/index")
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    clientes = Cliente.query.order_by(Cliente.orden).all()
    data = []
    for c in clientes:
        for credito in c.creditos:
            saldo = credito.monto * (1 + credito.interes / 100)
            for ab in credito.abonos:
                saldo -= ab.monto
            data.append({
                "id": credito.id,
                "orden": c.orden,
                "nombre": c.nombre,
                "credito": credito.monto,
                "interes": credito.interes,
                "plazo": credito.plazo_dias,
                "saldo": saldo
            })
    return render_template("index.html", data=data)

@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nombre = request.form["nombre"]
        direccion = request.form["direccion"]
        orden = request.form["orden"]
        codigo = str(int(datetime.utcnow().timestamp()))[-6:]  # genera código único

        cliente = Cliente(nombre=nombre, direccion=direccion, codigo=codigo, orden=orden)
        db.session.add(cliente)
        db.session.commit()

        monto = float(request.form["monto"])
        interes = float(request.form["interes"])
        plazo = int(request.form["plazo"])

        credito = Credito(cliente_id=cliente.id, monto=monto, interes=interes, plazo_dias=plazo)
        db.session.add(credito)
        db.session.commit()

        return redirect(url_for("index"))

    return render_template("nuevo_cliente.html")

@app.route("/abonar/<int:credito_id>", methods=["POST"])
def abonar(credito_id):
    monto = float(request.form["monto"])
    ab = Abono(credito_id=credito_id, monto=monto)
    db.session.add(ab)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/eliminar/<int:credito_id>", methods=["POST"])
def eliminar(credito_id):
    credito = Credito.query.get_or_404(credito_id)
    db.session.delete(credito)
    db.session.commit()
    return redirect(url_for("index"))

# =====================
# MAIN
# =====================
if __name__ == "__main__":
    app.run(debug=True)
