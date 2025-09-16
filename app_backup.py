from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random

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

    abonos = db.relationship("Abono", backref="cliente", lazy=True, cascade="all, delete-orphan")

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
        usuario = request.form.get("usuario", "")
        clave = request.form.get("clave", "")
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

@app.route("/inicio")
def inicio():
    # alias /inicio -> listado o dashboard sencillo
    if "usuario" not in session:
        return redirect(url_for("login"))
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template("inicio.html", clientes=clientes)

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))
    total_clientes = Cliente.query.count()
    total_abonos = db.session.query(db.func.coalesce(db.func.sum(Abono.monto), 0)).scalar()
    total_prestamos = db.session.query(db.func.coalesce(db.func.sum(Cliente.monto), 0)).scalar()
    return render_template("dashboard.html", total_clientes=total_clientes,
                           total_abonos=total_abonos, total_prestamos=total_prestamos)

# ==============================
# NUEVO CLIENTE / EDITAR
# ==============================
@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "usuario" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            orden = int(request.form.get("orden", 0))
        except ValueError:
            flash("Orden inválido", "warning")
            return redirect(url_for("nuevo_cliente"))
        nombre = request.form.get("nombre", "").strip()
        direccion = request.form.get("direccion", "").strip()
        try:
            monto = float(request.form.get("monto", 0))
            plazo = int(request.form.get("plazo", 0))
            interes = float(request.form.get("interes", 0))
        except ValueError:
            flash("Monto, plazo o interés inválidos", "warning")
            return redirect(url_for("nuevo_cliente"))

        # Generar código único (6 dígitos numéricos)
        codigo = ''.join(random.choices("0123456789", k=6))
        while Cliente.query.filter_by(codigo=codigo).first():
            codigo = ''.join(random.choices("0123456789", k=6))

        # Validar duplicado por nombre (opcional)
        if Cliente.query.filter_by(nombre=nombre).first():
            flash("El cliente ya existe. Use el código asignado o edite el existente.", "warning")
            return redirect(url_for("nuevo_cliente"))

        # Calcular saldo con interés
        saldo_total = monto + (monto * interes / 100)

        cliente = Cliente(
            codigo=codigo,
            orden=orden,
            nombre=nombre,
            direccion=direccion,
            monto=monto,
            plazo=plazo,
            interes=interes,
            saldo=saldo_total
        )
        db.session.add(cliente)
        db.session.commit()
        flash("Cliente creado exitosamente", "success")
        return redirect(url_for("index"))

    return render_template("nuevo_cliente.html")

@app.route("/editar_cliente/<int:cliente_id>", methods=["GET", "POST"])
def editar_cliente(cliente_id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.method == "POST":
        cliente.orden = int(request.form.get("orden", cliente.orden))
        cliente.nombre = request.form.get("nombre", cliente.nombre)
        cliente.direccion = request.form.get("direccion", cliente.direccion)
        cliente.monto = float(request.form.get("monto", cliente.monto))
        cliente.plazo = int(request.form.get("plazo", cliente.plazo))
        cliente.interes = float(request.form.get("interes", cliente.interes))

        # Recalcular saldo inicial considerando lo que ya existe:
        # si quieres reemplazar el saldo por el nuevo cálculo, descomenta la línea siguiente.
        # Por ahora NO sobrescribimos saldo existente para no romper historiales.
        # cliente.saldo = cliente.monto + (cliente.monto * cliente.interes / 100)

        db.session.commit()
        flash("Cliente actualizado correctamente", "success")
        return redirect(url_for("index"))

    return render_template("editar_cliente.html", cliente=cliente)

# ==============================
# ABONOS
# ==============================
@app.route("/abonar/<int:cliente_id>", methods=["POST"])
def abonar(cliente_id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        monto_abono = float(request.form.get("monto_abono", 0))
    except ValueError:
        flash("Abono inválido", "warning")
        return redirect(url_for("index"))

    if monto_abono <= 0:
        flash("El abono debe ser mayor a 0", "warning")
        return redirect(url_for("index"))

    if monto_abono > cliente.saldo:
        flash("El abono no puede ser mayor al saldo", "danger")
        return redirect(url_for("index"))

    cliente.saldo -= monto_abono
    ab = Abono(cliente_id=cliente.id, monto=monto_abono)
    db.session.add(ab)
    db.session.commit()
    flash("Abono registrado correctamente", "success")
    return redirect(url_for("index"))

# ==============================
# ELIMINAR CLIENTE Y ABONO
# ==============================
@app.route("/eliminar_cliente/<int:cliente_id>", methods=["POST"])
def eliminar_cliente(cliente_id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    cliente = Cliente.query.get_or_404(cliente_id)
    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente y sus abonos eliminados correctamente", "success")
    return redirect(url_for("index"))

@app.route("/eliminar_abono/<int:abono_id>", methods=["POST"])
def eliminar_abono(abono_id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    abono = Abono.query.get_or_404(abono_id)
    # Reponer el saldo al cliente
    if abono.cliente:
        abono.cliente.saldo += abono.monto
    db.session.delete(abono)
    db.session.commit()
    flash("Abono eliminado correctamente y saldo repuesto", "success")
    return redirect(url_for("index"))

# ==============================
# ACTUALIZAR ORDEN
# ==============================
@app.route("/actualizar_orden/<int:cliente_id>", methods=["POST"])
def actualizar_orden(cliente_id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        nuevo_orden = int(request.form.get("nuevo_orden", cliente.orden))
    except ValueError:
        flash("Orden inválido", "warning")
        return redirect(url_for("index"))

    if nuevo_orden <= 0:
        flash("El orden debe ser mayor que 0", "warning")
        return redirect(url_for("index"))

    if cliente.orden == nuevo_orden:
        flash("No hubo cambios en el orden", "info")
        return redirect(url_for("index"))

    # Reordenamiento: sacar cliente, insertar en nueva posición y reasignar órdenes
    clientes = Cliente.query.order_by(Cliente.orden).all()
    if cliente not in clientes:
        flash("Error al reorganizar", "danger")
        return redirect(url_for("index"))

    clientes.remove(cliente)
    insert_index = min(nuevo_orden - 1, len(clientes))
    clientes.insert(insert_index, cliente)

    # reasigna de 1...n
    for idx, c in enumerate(clientes, start=1):
        c.orden = idx

    db.session.commit()
    flash("Orden actualizado correctamente", "success")
    return redirect(url_for("index"))

# ==============================
# LIQUIDACIÓN
# ==============================
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
        # inclusive day: add time bounds if needed (here exact filter as before)
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
# HANDLERS Y INICIO DB
# ==============================
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
