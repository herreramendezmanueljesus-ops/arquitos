from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.secret_key = "supersecret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# ============================
# MODELOS
# ============================
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    monto = db.Column(db.Float, default=0)
    saldo = db.Column(db.Float, default=0)
    orden = db.Column(db.Integer, default=0)
    fecha_prestamo = db.Column(db.Date, default=date.today)
    plazo_dias = db.Column(db.Integer, default=30)

    abonos = db.relationship("Abono", backref="cliente", lazy=True)


class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=date.today)


class Liquidacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=date.today, unique=True)
    total_prestamos = db.Column(db.Float, default=0)
    total_abonos = db.Column(db.Float, default=0)
    caja = db.Column(db.Float, default=0)
    paquete = db.Column(db.Float, default=0)


# ============================
# HELPERS
# ============================
def crear_liquidacion_si_no_existe():
    """Crea un registro de liquidación para el día actual si no existe."""
    hoy = date.today()
    liquidacion = Liquidacion.query.filter_by(fecha=hoy).first()

    if not liquidacion:
        ultima = Liquidacion.query.order_by(Liquidacion.fecha.desc()).first()
        caja_anterior = ultima.caja if ultima else 0

        # Suma del paquete actual (todos los saldos de clientes)
        paquete_actual = sum([c.saldo for c in Cliente.query.all()])

        nueva = Liquidacion(
            fecha=hoy,
            total_prestamos=0,
            total_abonos=0,
            caja=caja_anterior,
            paquete=paquete_actual,
        )
        db.session.add(nueva)
        db.session.commit()


def color_estado(cliente):
    """Devuelve el color según la fecha de vencimiento del cliente."""
    vencimiento = cliente.fecha_prestamo + timedelta(days=cliente.plazo_dias)
    hoy = date.today()
    if hoy <= vencimiento:
        return "table-success"  # verde
    elif hoy <= vencimiento + timedelta(days=30):
        return "table-warning"  # naranja
    else:
        return "table-danger"   # rojo


# ============================
# RUTAS
# ============================
@app.route("/")
def index():
    if not session.get("usuario"):
        return redirect(url_for("login"))

    crear_liquidacion_si_no_existe()
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template("index.html", clientes=clientes, color_estado=color_estado)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]
        if usuario == "admin" and clave == "1234":
            session["usuario"] = usuario
            return redirect(url_for("index"))
        flash("Usuario o clave incorrectos", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))


@app.route("/abonar/<int:cliente_id>", methods=["POST"])
def abonar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    monto = float(request.form["monto_abono"])
    if monto <= 0:
        flash("El abono debe ser mayor que cero", "warning")
        return redirect(url_for("index"))

    cliente.saldo -= monto
    db.session.add(Abono(cliente_id=cliente.id, monto=monto, fecha=date.today()))

    liquidacion = Liquidacion.query.filter_by(fecha=date.today()).first()
    if liquidacion:
        liquidacion.total_abonos += monto
        liquidacion.caja += monto
        liquidacion.paquete = sum([c.saldo for c in Cliente.query.all()])

    db.session.commit()
    return redirect(url_for("index"))


@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if request.method == "POST":
        codigo = request.form["codigo"]
        nombre = request.form["nombre"]
        monto = float(request.form["monto"])
        plazo = int(request.form.get("plazo", 30))

        cliente = Cliente(
            codigo=codigo,
            nombre=nombre,
            monto=monto,
            saldo=monto,
            fecha_prestamo=date.today(),
            plazo_dias=plazo,
        )
        db.session.add(cliente)

        liquidacion = Liquidacion.query.filter_by(fecha=date.today()).first()
        if liquidacion:
            liquidacion.total_prestamos += monto
            liquidacion.caja -= monto
            liquidacion.paquete = sum([c.saldo for c in Cliente.query.all()] + [monto])

        db.session.commit()
        return redirect(url_for("index"))
    return render_template("nuevo_cliente.html")


@app.route("/actualizar_orden/<int:cliente_id>", methods=["POST"])
def actualizar_orden(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    nuevo_orden = int(request.form["orden"])
    cliente.orden = nuevo_orden
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/liquidacion")
def liquidacion():
    crear_liquidacion_si_no_existe()

    fecha_inicio = request.args.get("fecha_inicio")
    fecha_fin = request.args.get("fecha_fin")

    query = Liquidacion.query.order_by(Liquidacion.fecha.desc())

    resumen_rango = None
    if fecha_inicio and fecha_fin:
        inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
        fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
        liquidaciones = query.filter(Liquidacion.fecha.between(inicio, fin)).all()

        if liquidaciones:
            resumen_rango = {
                "desde": inicio,
                "hasta": fin,
                "total_prestamos": sum([l.total_prestamos for l in liquidaciones]),
                "total_abonos": sum([l.total_abonos for l in liquidaciones]),
                "caja": liquidaciones[-1].caja,  # caja final del rango
                "paquete": liquidaciones[-1].paquete,
            }
    else:
        liquidaciones = query.limit(10).all()

    return render_template(
        "liquidacion.html", liquidaciones=liquidaciones, resumen_rango=resumen_rango
    )


@app.route("/detalle_prestamos/<fecha>")
def detalle_prestamos(fecha):
    fecha_dt = datetime.strptime(fecha, "%Y-%m-%d").date()
    clientes = Cliente.query.filter_by(fecha_prestamo=fecha_dt).all()
    return render_template("detalle_prestamos.html", clientes=clientes, fecha=fecha_dt)


@app.route("/detalle_abonos/<fecha>")
def detalle_abonos(fecha):
    fecha_dt = datetime.strptime(fecha, "%Y-%m-%d").date()
    abonos = Abono.query.filter_by(fecha=fecha_dt).all()
    return render_template("detalle_abonos.html", abonos=abonos, fecha=fecha_dt)


# ============================
# INICIALIZAR DB
# ============================
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
