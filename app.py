from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime, date, timedelta
import random

app = Flask(__name__)
app.secret_key = "supersecret_change_this"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///creditos.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# -----------------------
# MODELOS
# -----------------------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)   # 6 dígitos numéricos
    orden = db.Column(db.Integer, nullable=False, default=0)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=True)
    monto = db.Column(db.Float, nullable=False, default=0.0)         # monto prestado inicial
    plazo = db.Column(db.Integer, nullable=False, default=30)        # plazo en días
    interes = db.Column(db.Float, nullable=False, default=0.0)      # porcentaje
    saldo = db.Column(db.Float, nullable=False, default=0.0)        # saldo pendiente
    fecha_creacion = db.Column(db.Date, default=date.today)
    ultimo_abono_fecha = db.Column(db.Date, nullable=True)          # fecha del último abono

    abonos = db.relationship("Abono", backref="cliente", lazy=True, cascade="all, delete-orphan")
    prestamos = db.relationship("Prestamo", backref="cliente", lazy=True, cascade="all, delete-orphan")

    # 👉 Nueva propiedad para saber si abonó hoy
    @property
    def abono_hoy(self):
        return self.ultimo_abono_fecha == date.today()


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
    fecha = db.Column(db.Date, unique=True, nullable=False)
    total_abonos = db.Column(db.Float, default=0.0)
    total_prestamos = db.Column(db.Float, default=0.0)
    caja = db.Column(db.Float, default=0.0)
    paquete = db.Column(db.Float, default=0.0)  # suma de saldos al cierre del día


class MovimientoCaja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # "entrada", "salida", "gasto"
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    fecha = db.Column(db.Date, default=date.today)


# -----------------------
# LOGIN (fijo)
# -----------------------
VALID_USER = "mjesus40"
VALID_PASS = "198409"

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "").strip()
        if usuario == VALID_USER and clave == VALID_PASS:
            session["usuario"] = usuario
            flash("Inicio de sesión correcto", "success")
            return redirect(url_for("index"))
        flash("Usuario o contraseña incorrectos", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    flash("Sesión cerrada", "info")
    return redirect(url_for("login"))


# -----------------------
# HELPERS: liquidación diaria & utilidades
# -----------------------
def generar_codigo_numerico():
    code = ''.join(random.choices("0123456789", k=6))
    while Cliente.query.filter_by(codigo=code).first():
        code = ''.join(random.choices("0123456789", k=6))
    return code


def crear_liquidacion_para_fecha(fecha: date):
    """Crea una liquidación para `fecha` si no existe. Paquete = suma saldos actuales; caja hereda la anterior."""
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if liq:
        return liq

    tot_abonos = db.session.query(db.func.coalesce(db.func.sum(Abono.monto), 0)).filter(Abono.fecha == fecha).scalar() or 0.0
    tot_prestamos = db.session.query(db.func.coalesce(db.func.sum(Prestamo.monto), 0)).filter(Prestamo.fecha == fecha).scalar() or 0.0
    paquete_actual = db.session.query(db.func.coalesce(db.func.sum(Cliente.saldo), 0)).scalar() or 0.0

    ultima = Liquidacion.query.filter(Liquidacion.fecha < fecha).order_by(Liquidacion.fecha.desc()).first()
    caja_anterior = ultima.caja if ultima else 0.0

    # considerar movimientos manuales (entrada/salida/gasto) del día
    mov_entrada = db.session.query(db.func.coalesce(db.func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha == fecha, MovimientoCaja.tipo == "entrada"
    ).scalar() or 0.0
    mov_salida = db.session.query(db.func.coalesce(db.func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha == fecha, MovimientoCaja.tipo == "salida"
    ).scalar() or 0.0
    mov_gasto = db.session.query(db.func.coalesce(db.func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha == fecha, MovimientoCaja.tipo == "gasto"
    ).scalar() or 0.0

    caja = caja_anterior + tot_abonos - tot_prestamos + mov_entrada - mov_salida - mov_gasto

    liq = Liquidacion(
        fecha=fecha,
        total_abonos=tot_abonos,
        total_prestamos=tot_prestamos,
        caja=caja,
        paquete=paquete_actual
    )
    db.session.add(liq)
    db.session.commit()
    return liq


def actualizar_liquidacion_por_movimiento(fecha: date):
    """Recalcula y actualiza la liquidación del día `fecha`."""
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if not liq:
        liq = crear_liquidacion_para_fecha(fecha)

    tot_abonos = db.session.query(db.func.coalesce(db.func.sum(Abono.monto), 0)).filter(Abono.fecha == fecha).scalar() or 0.0
    tot_prestamos = db.session.query(db.func.coalesce(db.func.sum(Prestamo.monto), 0)).filter(Prestamo.fecha == fecha).scalar() or 0.0
    paquete_actual = db.session.query(db.func.coalesce(db.func.sum(Cliente.saldo), 0)).scalar() or 0.0

    anterior = Liquidacion.query.filter(Liquidacion.fecha < fecha).order_by(Liquidacion.fecha.desc()).first()
    caja_anterior = anterior.caja if anterior else 0.0

    mov_entrada = db.session.query(db.func.coalesce(db.func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha == fecha, MovimientoCaja.tipo == "entrada"
    ).scalar() or 0.0
    mov_salida = db.session.query(db.func.coalesce(db.func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha == fecha, MovimientoCaja.tipo == "salida"
    ).scalar() or 0.0
    mov_gasto = db.session.query(db.func.coalesce(db.func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha == fecha, MovimientoCaja.tipo == "gasto"
    ).scalar() or 0.0

    caja = caja_anterior + tot_abonos - tot_prestamos + mov_entrada - mov_salida - mov_gasto

    liq.total_abonos = tot_abonos
    liq.total_prestamos = tot_prestamos
    liq.caja = caja
    liq.paquete = paquete_actual
    db.session.commit()
    return liq


def cliente_estado_class(cliente: Cliente):
    """Devuelve clase bootstrap para la fila según saldo / vencimiento / abonos del día."""
    try:
        venc = cliente.fecha_creacion + timedelta(days=cliente.plazo)
        hoy = date.today()

        # si todo pagado
        if cliente.saldo <= 0:
            return "table-success"
        # si abonó hoy
        if cliente.ultimo_abono_fecha == hoy:
            return "table-info"
        # vencido > 30 días
        if hoy > venc + timedelta(days=30):
            return "table-danger"
        # vencido dentro de 30 días
        if hoy > venc:
            return "table-warning"
        return ""
    except Exception:
        return ""


# -----------------------
# RUTAS PRINCIPALES
# -----------------------
@app.route("/")
@login_required
def index():
    crear_liquidacion_para_fecha(date.today())
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template("index.html", clientes=clientes, hoy=date.today(), estado_class=cliente_estado_class)


@app.route("/nuevo_cliente", methods=["GET", "POST"])
@login_required
def nuevo_cliente():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        direccion = request.form.get("direccion", "").strip()
        try:
            monto = float(request.form.get("monto", 0))
            plazo = int(request.form.get("plazo", 30))
            interes = float(request.form.get("interes", 0))
        except ValueError:
            flash("Monto/plazo/interés inválidos", "warning")
            return redirect(url_for("nuevo_cliente"))

        codigo = generar_codigo_numerico()
        saldo_total = monto + (monto * (interes / 100.0))
        last = Cliente.query.order_by(Cliente.orden.desc()).first()
        nuevo_orden = (last.orden + 1) if last else 1

        cliente = Cliente(
            codigo=codigo,
            orden=nuevo_orden,
            nombre=nombre,
            direccion=direccion,
            monto=monto,
            plazo=plazo,
            interes=interes,
            saldo=saldo_total,
            fecha_creacion=date.today()
        )
        db.session.add(cliente)
        db.session.flush()

        # registrar préstamo
        prestamo = Prestamo(cliente_id=cliente.id, monto=monto, fecha=date.today())
        db.session.add(prestamo)
        db.session.commit()

        actualizar_liquidacion_por_movimiento(date.today())
        flash("Cliente creado y préstamo registrado", "success")
        return redirect(url_for("index"))

    return render_template("nuevo_cliente.html")


@app.route("/editar_cliente/<int:cliente_id>", methods=["GET", "POST"])
@login_required
def editar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.method == "POST":
        cliente.orden = int(request.form.get("orden", cliente.orden))
        cliente.nombre = request.form.get("nombre", cliente.nombre)
        cliente.direccion = request.form.get("direccion", cliente.direccion)
        cliente.monto = float(request.form.get("monto", cliente.monto))
        cliente.plazo = int(request.form.get("plazo", cliente.plazo))
        cliente.interes = float(request.form.get("interes", cliente.interes))
        db.session.commit()
        flash("Cliente actualizado", "success")
        return redirect(url_for("index"))
    return render_template("editar_cliente.html", cliente=cliente)


@app.route("/abonar/<int:cliente_id>", methods=["POST"])
@login_required
def abonar(cliente_id):
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
    cliente.ultimo_abono_fecha = date.today()

    ab = Abono(cliente_id=cliente.id, monto=monto_abono, fecha=date.today())
    db.session.add(ab)

    mov = MovimientoCaja(tipo="entrada", monto=monto_abono, descripcion=f"Abono {cliente.nombre}", fecha=date.today())
    db.session.add(mov)

    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    flash("Abono registrado correctamente", "success")
    return redirect(url_for("index"))


@app.route("/actualizar_orden/<int:cliente_id>", methods=["POST"])
@login_required
def actualizar_orden(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        nuevo_orden = int(request.form.get("orden", cliente.orden))
    except ValueError:
        flash("Orden inválido", "warning")
        return redirect(url_for("index"))

    if nuevo_orden <= 0:
        flash("El orden debe ser mayor a 0", "warning")
        return redirect(url_for("index"))

    clientes = Cliente.query.order_by(Cliente.orden).all()
    if cliente not in clientes:
        flash("Error al reorganizar", "danger")
        return redirect(url_for("index"))

    clientes.remove(cliente)
    insert_index = min(nuevo_orden - 1, len(clientes))
    clientes.insert(insert_index, cliente)
    for idx, c in enumerate(clientes, start=1):
        c.orden = idx

    db.session.commit()
    flash("Orden actualizado correctamente", "success")
    return redirect(url_for("index"))


@app.route("/eliminar_cliente/<int:cliente_id>", methods=["POST"])
@login_required
def eliminar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    db.session.delete(cliente)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    flash("Cliente eliminado", "success")
    return redirect(url_for("index"))


# -----------------------
# LIQUIDACIÓN / BUSCAR / RESUMEN
# -----------------------
@app.route("/liquidacion")
@login_required
def liquidacion():
    crear_liquidacion_para_fecha(date.today())

    fecha_inicio = request.args.get("fecha_inicio")
    fecha_fin = request.args.get("fecha_fin")

    resumen_rango = None
    if fecha_inicio and fecha_fin:
        try:
            desde = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
            hasta = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
        except ValueError:
            flash("Fechas inválidas", "warning")
            return redirect(url_for("liquidacion"))

        liquidaciones = Liquidacion.query.filter(Liquidacion.fecha.between(desde, hasta)).order_by(Liquidacion.fecha.desc()).all()
        total_abonos = sum(l.total_abonos for l in liquidaciones)
        total_prestamos = sum(l.total_prestamos for l in liquidaciones)
        caja_final = liquidaciones[0].caja if liquidaciones else 0.0
        paquete_final = liquidaciones[0].paquete if liquidaciones else 0.0

        resumen_rango = {
            "desde": desde,
            "hasta": hasta,
            "total_abonos": total_abonos,
            "total_prestamos": total_prestamos,
            "caja": caja_final,
            "paquete": paquete_final
        }
        return render_template("liquidacion.html", liquidaciones=liquidaciones, resumen_rango=resumen_rango, hoy=date.today())
    else:
        ultimas = Liquidacion.query.order_by(Liquidacion.fecha.desc()).limit(10).all()
        return render_template("liquidacion.html", liquidaciones=ultimas, resumen_rango=None, hoy=date.today())


# -----------------------
# API / Detalle
# -----------------------
@app.route("/api/detalle/abonos/<fecha>")
@login_required
def api_detalle_abonos(fecha):
    try:
        f = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        return jsonify([])
    abonos = Abono.query.filter_by(fecha=f).all()
    data = [{"cliente": a.cliente.nombre, "monto": a.monto, "fecha": a.fecha.isoformat()} for a in abonos]
    return jsonify(data)


@app.route("/api/detalle/prestamos/<fecha>")
@login_required
def api_detalle_prestamos(fecha):
    try:
        f = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        return jsonify([])
    prestamos = Prestamo.query.filter_by(fecha=f).all()
    data = [{"cliente": p.cliente.nombre, "monto": p.monto, "fecha": p.fecha.isoformat()} for p in prestamos]
    return jsonify(data)


# -----------------------
# MOVIMIENTOS DE CAJA (entrada/salida/gasto)
# -----------------------
@app.route("/caja/entrada", methods=["POST"])
@login_required
def caja_entrada():
    try:
        monto = float(request.form.get("monto", 0))
    except ValueError:
        flash("Monto inválido", "warning")
        return redirect(url_for("liquidacion"))
    if monto <= 0:
        flash("Monto debe ser mayor a 0", "warning")
        return redirect(url_for("liquidacion"))
    descripcion = request.form.get("descripcion", "Entrada manual")
    mov = MovimientoCaja(tipo="entrada", monto=monto, descripcion=descripcion, fecha=date.today())
    db.session.add(mov)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    flash("Entrada registrada en caja", "success")
    return redirect(url_for("liquidacion"))


@app.route("/caja/salida", methods=["POST"])
@login_required
def caja_salida():
    try:
        monto = float(request.form.get("monto", 0))
    except ValueError:
        flash("Monto inválido", "warning")
        return redirect(url_for("liquidacion"))
    if monto <= 0:
        flash("Monto debe ser mayor a 0", "warning")
        return redirect(url_for("liquidacion"))
    descripcion = request.form.get("descripcion", "Salida manual")
    mov = MovimientoCaja(tipo="salida", monto=monto, descripcion=descripcion, fecha=date.today())
    db.session.add(mov)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    flash("Salida registrada en caja", "success")
    return redirect(url_for("liquidacion"))


@app.route("/caja/gasto", methods=["POST"])
@login_required
def caja_gasto():
    try:
        monto = float(request.form.get("monto", 0))
    except ValueError:
        flash("Monto inválido", "warning")
        return redirect(url_for("liquidacion"))
    if monto <= 0:
        flash("Monto debe ser mayor a 0", "warning")
        return redirect(url_for("liquidacion"))
    descripcion = request.form.get("descripcion", "Gasto manual")
    mov = MovimientoCaja(tipo="gasto", monto=monto, descripcion=descripcion, fecha=date.today())
    db.session.add(mov)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    flash("Gasto registrado en caja", "success")
    return redirect(url_for("liquidacion"))


# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

