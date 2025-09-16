from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime, date, timedelta
import random

app = Flask(__name__)
app.secret_key = "supersecret"  # puedes cambiarlo por una cadena segura
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///creditos.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------
# MODELOS
# -----------------------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), unique=True, nullable=False)  # 6 dígitos permite 10
    orden = db.Column(db.Integer, nullable=False, default=0)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200), nullable=True)
    monto = db.Column(db.Float, nullable=False, default=0.0)   # monto inicial prestado
    plazo = db.Column(db.Integer, nullable=False, default=30)  # días de plazo
    interes = db.Column(db.Float, nullable=False, default=0.0)  # porcentaje
    saldo = db.Column(db.Float, nullable=False, default=0.0)   # saldo pendiente
    fecha_creacion = db.Column(db.Date, default=date.today)

    abonos = db.relationship("Abono", backref="cliente", lazy=True, cascade="all, delete-orphan")
    prestamos = db.relationship("Prestamo", backref="cliente", lazy=True, cascade="all, delete-orphan")

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
    caja = db.Column(db.Float, default=0.0)    # caja acumulada (heredada y sumada)
    paquete = db.Column(db.Float, default=0.0) # suma de saldos al cierre del día


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
        flash("Usuario o clave incorrectos", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    flash("Sesión cerrada", "info")
    return redirect(url_for("login"))


# -----------------------
# HELPERS: liquidación diaria & utilidades
# -----------------------
def crear_liquidacion_para_fecha(fecha: date):
    """Crea (si no existe) una liquidación para `fecha`. 
       - si no hay movimientos ese día total_abonos y total_prestamos = 0.
       - caja se hereda del último registro previo.
       - paquete se calcula con suma actual de saldos (foto del momento).
    """
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if liq:
        return liq

    # totals for that date (if any)
    tot_abonos = db.session.query(db.func.coalesce(db.func.sum(Abono.monto), 0)).filter(Abono.fecha == fecha).scalar() or 0.0
    tot_prestamos = db.session.query(db.func.coalesce(db.func.sum(Prestamo.monto), 0)).filter(Prestamo.fecha == fecha).scalar() or 0.0
    paquete_actual = db.session.query(db.func.coalesce(db.func.sum(Cliente.saldo), 0)).scalar() or 0.0

    # inherit last caja
    ultima = Liquidacion.query.filter(Liquidacion.fecha < fecha).order_by(Liquidacion.fecha.desc()).first()
    caja_anterior = ultima.caja if ultima else 0.0
    caja = caja_anterior + tot_abonos - tot_prestamos

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
    """Recalcula y actualiza la liquidación del día `fecha` (totales y paquete y caja)."""
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if not liq:
        liq = crear_liquidacion_para_fecha(fecha)

    tot_abonos = db.session.query(db.func.coalesce(db.func.sum(Abono.monto), 0)).filter(Abono.fecha == fecha).scalar() or 0.0
    tot_prestamos = db.session.query(db.func.coalesce(db.func.sum(Prestamo.monto), 0)).filter(Prestamo.fecha == fecha).scalar() or 0.0
    paquete_actual = db.session.query(db.func.coalesce(db.func.sum(Cliente.saldo), 0)).scalar() or 0.0

    # caja = caja_anterior + tot_abonos - tot_prestamos
    anterior = Liquidacion.query.filter(Liquidacion.fecha < fecha).order_by(Liquidacion.fecha.desc()).first()
    caja_anterior = anterior.caja if anterior else 0.0
    caja = caja_anterior + tot_abonos - tot_prestamos

    liq.total_abonos = tot_abonos
    liq.total_prestamos = tot_prestamos
    liq.caja = caja
    liq.paquete = paquete_actual
    db.session.commit()
    return liq

def generar_codigo_numerico():
    code = ''.join(random.choices("0123456789", k=6))
    while Cliente.query.filter_by(codigo=code).first():
        code = ''.join(random.choices("0123456789", k=6))
    return code

def cliente_estado_class(cliente: Cliente):
    """Devuelve clase bootstrap según plazo/fecha de creación + plazo."""
    try:
        venc = cliente.fecha_creacion + timedelta(days=cliente.plazo)
        hoy = date.today()
        if cliente.saldo <= 0:
            return "table-success"
        if hoy <= venc:
            return ""  # dentro del plazo, sin color
        if hoy <= venc + timedelta(days=30):
            return "table-warning"
        return "table-danger"
    except Exception:
        return ""


# -----------------------
# RUTAS PRINCIPALES
# -----------------------
@app.route("/")
@login_required
def index():
    # aseguro la liquidación de hoy exista (si aún no)
    crear_liquidacion_para_fecha(date.today())
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template(
        "index.html",
        clientes=clientes,
        hoy=date.today(),
        timedelta=timedelta,
        estado_class=cliente_estado_class
    )

@app.route("/nuevo_cliente", methods=["GET", "POST"])
@login_required
def nuevo_cliente():
    if request.method == "POST":
        # recuperar formulario
        nombre = request.form.get("nombre", "").strip()
        direccion = request.form.get("direccion", "").strip()
        try:
            monto = float(request.form.get("monto", 0))
            plazo = int(request.form.get("plazo", 30))
            interes = float(request.form.get("interes", 0))
        except ValueError:
            flash("Monto, plazo o interés inválidos", "warning")
            return redirect(url_for("nuevo_cliente"))

        codigo = generar_codigo_numerico()
        saldo_total = monto + (monto * (interes / 100.0))
        # calcular orden: al final
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
        db.session.flush()  # para obtener cliente.id antes de commit

        # registrar préstamo del día
        prestamo = Prestamo(cliente_id=cliente.id, monto=monto, fecha=date.today())
        db.session.add(prestamo)
        db.session.commit()

        # actualizar liquidación de hoy (sumar préstamo)
        actualizar_liquidacion_por_movimiento(date.today())
        flash("Cliente creado y préstamo registrado", "success")
        return redirect(url_for("index"))

    return render_template("nuevo_cliente.html")


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
    ab = Abono(cliente_id=cliente.id, monto=monto_abono, fecha=date.today())
    db.session.add(ab)
    db.session.commit()

    # actualizar liquidación de hoy
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

    # reordenar: sacar el cliente y volver a insertar en la posición indicada
    clientes = Cliente.query.order_by(Cliente.orden).all()
    if cliente not in clientes:
        flash("Error al reorganizar", "danger")
        return redirect(url_for("index"))

    clientes.remove(cliente)
    insert_index = min(nuevo_orden - 1, len(clientes))
    clientes.insert(insert_index, cliente)

    # reasignar órdenes 1..n
    for idx, c in enumerate(clientes, start=1):
        c.orden = idx

    db.session.commit()
    flash("Orden actualizado correctamente", "success")
    return redirect(url_for("index"))


# -----------------------
# ELIMINAR
# -----------------------
@app.route("/eliminar_cliente/<int:cliente_id>", methods=["POST"])
@login_required
def eliminar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    db.session.delete(cliente)
    db.session.commit()
    # actualizar paquete/liquidación de hoy por si afecta
    actualizar_liquidacion_por_movimiento(date.today())
    flash("Cliente y sus abonos eliminados", "success")
    return redirect(url_for("index"))

@app.route("/eliminar_abono/<int:abono_id>", methods=["POST"])
@login_required
def eliminar_abono(abono_id):
    ab = Abono.query.get_or_404(abono_id)
    # devolver saldo
    cliente = ab.cliente
    if cliente:
        cliente.saldo += ab.monto
    fecha = ab.fecha
    db.session.delete(ab)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(fecha)
    flash("Abono eliminado y saldo repuesto", "success")
    return redirect(url_for("liquidacion"))


# -----------------------
# LIQUIDACIÓN / BUSCAR / RESUMEN
# -----------------------
@app.route("/liquidacion")
@login_required
def liquidacion():
    # aseguro que exista la liquidación de hoy
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
        # resumen acumulado en rango
        total_abonos = sum(l.total_abonos for l in liquidaciones)
        total_prestamos = sum(l.total_prestamos for l in liquidaciones)
        caja_final = liquidaciones[0].caja if liquidaciones else 0.0  # la más reciente del rango
        paquete_final = liquidaciones[0].paquete if liquidaciones else 0.0

        resumen_rango = {
            "desde": desde,
            "hasta": hasta,
            "total_abonos": total_abonos,
            "total_prestamos": total_prestamos,
            "caja": caja_final,
            "paquete": paquete_final
        }
        # además devolvemos las liquidaciones del rango para detalle si quiere
        return render_template("liquidacion.html", liquidaciones=liquidaciones, resumen_rango=resumen_rango)

    # si no hay rango, muestro últimas 10
    ultimas = Liquidacion.query.order_by(Liquidacion.fecha.desc()).limit(10).all()
    return render_template("liquidacion.html", liquidaciones=ultimas, resumen_rango=None)


# -----------------------
# DETALLES (JSON para modal) y páginas fallback
# -----------------------
@app.route("/api/detalle/abonos/<fecha>")
@login_required
def api_detalle_abonos(fecha):
    """Devuelve JSON con abonos de la fecha (formato YYYY-MM-DD)."""
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

# Fallback páginas html (ya las tenías)
@app.route("/detalle_abonos/<fecha>")
@login_required
def detalle_abonos(fecha):
    try:
        f = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))
    abonos = Abono.query.filter_by(fecha=f).all()
    return render_template("detalle_abonos.html", abonos=abonos, fecha=f)

@app.route("/detalle_prestamos/<fecha>")
@login_required
def detalle_prestamos(fecha):
    try:
        f = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))
    prestamos = Prestamo.query.filter_by(fecha=f).all()
    return render_template("detalle_prestamos.html", prestamos=prestamos, fecha=f)


# -----------------------
# INICIALIZAR DB
# -----------------------
with app.app_context():
    db.create_all()

# -----------------------
# EJECUCIÓN
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)

