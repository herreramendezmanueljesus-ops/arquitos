from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = "supersecret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///creditos.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------
# MODELOS
# -----------------------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=0)
    nombre = db.Column(db.String(100), nullable=False)
    monto = db.Column(db.Float, nullable=False, default=0)
    saldo = db.Column(db.Float, nullable=False, default=0)
    fecha_limite = db.Column(db.Date, nullable=True)

    abonos = db.relationship("Abono", backref="cliente", lazy=True)


class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=date.today)


class Prestamo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=date.today)


class Liquidacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=date.today, unique=True)
    total_abonos = db.Column(db.Float, default=0)
    total_prestamos = db.Column(db.Float, default=0)
    caja = db.Column(db.Float, default=0)
    paquete = db.Column(db.Float, default=0)


# -----------------------
# LOGIN
# -----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]

        if usuario == "mjesus40" and clave == "198409":
            session["usuario"] = usuario
            flash("Inicio de sesión correcto", "success")
            return redirect(url_for("index"))
        else:
            flash("Usuario o clave incorrectos", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    flash("Sesión cerrada", "info")
    return redirect(url_for("login"))


# -----------------------
# RUTAS PROTEGIDAS
# -----------------------
def login_requerido(func):
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@app.route("/")
@login_requerido
def index():
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template(
        "index.html",
        clientes=clientes,
        hoy=date.today(),
        timedelta=timedelta
    )


@app.route("/nuevo", methods=["GET", "POST"])
@login_requerido
def nuevo_cliente():
    if request.method == "POST":
        codigo = request.form["codigo"]
        nombre = request.form["nombre"]
        monto = float(request.form["monto"])
        orden = int(request.form["orden"])
        fecha_limite = datetime.strptime(request.form["fecha_limite"], "%Y-%m-%d").date()

        cliente = Cliente(codigo=codigo, nombre=nombre, monto=monto, saldo=monto, orden=orden, fecha_limite=fecha_limite)
        db.session.add(cliente)

        prestamo = Prestamo(cliente=cliente, monto=monto, fecha=date.today())
        db.session.add(prestamo)

        db.session.commit()
        flash("Cliente agregado con éxito", "success")
        return redirect(url_for("index"))

    return render_template("nuevo.html")


@app.route("/abonar/<int:cliente_id>", methods=["POST"])
@login_requerido
def abonar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    monto_abono = float(request.form["monto_abono"])

    if monto_abono > 0:
        cliente.saldo -= monto_abono
        abono = Abono(cliente=cliente, monto=monto_abono, fecha=date.today())
        db.session.add(abono)
        db.session.commit()
        flash("Abono registrado", "success")

    return redirect(url_for("index"))


@app.route("/actualizar_orden/<int:cliente_id>", methods=["POST"])
@login_requerido
def actualizar_orden(cliente_id):
    nuevo_orden = int(request.form["orden"])
    cliente = Cliente.query.get_or_404(cliente_id)

    if cliente.orden != nuevo_orden:
        clientes = Cliente.query.order_by(Cliente.orden).all()
        for c in clientes:
            if c.orden >= nuevo_orden and c.id != cliente.id:
                c.orden += 1
        cliente.orden = nuevo_orden
        db.session.commit()

    return redirect(url_for("index"))


@app.route("/liquidacion")
@login_requerido
def liquidacion():
    hoy_fecha = date.today()

    liquidacion = Liquidacion.query.filter_by(fecha=hoy_fecha).first()
    if not liquidacion:
        total_abonos = db.session.query(db.func.sum(Abono.monto)).filter_by(fecha=hoy_fecha).scalar() or 0
        total_prestamos = db.session.query(db.func.sum(Prestamo.monto)).filter_by(fecha=hoy_fecha).scalar() or 0
        paquete = db.session.query(db.func.sum(Cliente.saldo)).scalar() or 0

        ultima_liq = Liquidacion.query.order_by(Liquidacion.fecha.desc()).first()
        caja_anterior = ultima_liq.caja if ultima_liq else 0
        caja = caja_anterior + total_abonos - total_prestamos

        liquidacion = Liquidacion(
            fecha=hoy_fecha,
            total_abonos=total_abonos,
            total_prestamos=total_prestamos,
            caja=caja,
            paquete=paquete
        )
        db.session.add(liquidacion)
        db.session.commit()

    liquidaciones = Liquidacion.query.order_by(Liquidacion.fecha.desc()).limit(10).all()
    return render_template("liquidacion.html", liquidaciones=liquidaciones)


@app.route("/detalle_abonos/<fecha>")
@login_requerido
def detalle_abonos(fecha):
    fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
    abonos = Abono.query.filter_by(fecha=fecha).all()
    return render_template("detalle_abonos.html", abonos=abonos, fecha=fecha)


@app.route("/detalle_prestamos/<fecha>")
@login_requerido
def detalle_prestamos(fecha):
    fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
    prestamos = Prestamo.query.filter_by(fecha=fecha).all()
    return render_template("detalle_prestamos.html", prestamos=prestamos, fecha=fecha)


@app.route("/buscar_liquidacion", methods=["GET", "POST"])
@login_requerido
def buscar_liquidacion():
    if request.method == "POST":
        fecha_inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d").date()
        fecha_fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d").date()

        total_abonos = db.session.query(db.func.sum(Liquidacion.total_abonos)).filter(
            Liquidacion.fecha >= fecha_inicio, Liquidacion.fecha <= fecha_fin).scalar() or 0
        total_prestamos = db.session.query(db.func.sum(Liquidacion.total_prestamos)).filter(
            Liquidacion.fecha >= fecha_inicio, Liquidacion.fecha <= fecha_fin).scalar() or 0
        paquete = db.session.query(db.func.max(Liquidacion.paquete)).filter(
            Liquidacion.fecha >= fecha_inicio, Liquidacion.fecha <= fecha_fin).scalar() or 0
        caja = db.session.query(db.func.max(Liquidacion.caja)).filter(
            Liquidacion.fecha >= fecha_inicio, Liquidacion.fecha <= fecha_fin).scalar() or 0

        return render_template("resumen_liquidacion.html",
                               fecha_inicio=fecha_inicio,
                               fecha_fin=fecha_fin,
                               total_abonos=total_abonos,
                               total_prestamos=total_prestamos,
                               paquete=paquete,
                               caja=caja)

    return render_template("buscar_liquidacion.html")


# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
