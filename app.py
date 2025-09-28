# app.py - Versión unificada y completa (manejo consistente de caja y liquidaciones)
import os
import random
from datetime import date, datetime, timedelta, time
from functools import wraps
from liquidaciones import actualizar_liquidacion_por_movimiento
from caja import calcular_total_caja
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_migrate import Migrate
from sqlalchemy import cast, Date, func

from extensions import db
from modelos import Cliente, Abono, Prestamo, Liquidacion, Paquete, MovimientoCaja
from liquidaciones import actualizar_liquidacion_por_movimiento  # función robusta de liquidación
from caja import movimientos_caja_totales_para_dia  # funciones de caja
from helpers import (
    crear_liquidacion_para_fecha,
    asegurar_liquidaciones_contiguas,
    calcular_total_caja,
    paquete_total_actual,
    paquete_total_para_fecha,
    actualizar_liquidacion_por_movimiento
)


app = Flask(__name__)
app.secret_key = "MiSuperClaveSecreta123456!"

# ---------------------------
# Configuración de SQLAlchemy (Postgres en Neon)
# ---------------------------
DB_DEFAULT = "postgresql://neondb_owner:npg_YDr98JviPLhU@ep-summer-credit-ad0ysr5b-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
uri = os.getenv("DATABASE_URL", DB_DEFAULT)
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)

# ---------------------------
# Credenciales simples para login
# ---------------------------
VALID_USER = "mjesus40"
VALID_PASS = "198409"

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            flash("Debes iniciar sesión para continuar", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# ---------------------------
# RUTAS: LOGIN
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "").strip()
        if usuario == VALID_USER and clave == VALID_PASS:
            session["usuario"] = usuario
            flash("Inicio de sesión correcto", "success")
            return redirect(url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.pop("usuario", None)
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for("login"))

# ---------------------------
# Funciones de Clientes y Códigos
# ---------------------------
def asegurar_liquidaciones_contiguas():
    """Crea liquidaciones para los días faltantes hasta hoy."""
    hoy = date.today()
    ultima = Liquidacion.query.order_by(Liquidacion.fecha.desc()).first()
    if not ultima:
        crear_liquidacion_para_fecha(hoy)
        return
    dia = ultima.fecha + timedelta(days=1)
    while dia <= hoy:
        crear_liquidacion_para_fecha(dia)
        dia += timedelta(days=1)

def calcular_total_caja(fecha):
    """Devuelve totales diarios incluyendo abonos, préstamos, caja y paquetes."""
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    start, end = day_range(fecha)

    total_abonos = db.session.query(func.coalesce(func.sum(Abono.monto), 0))\
        .filter(cast(Abono.fecha, Date) == fecha).scalar() or 0.0
    total_prestamos = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0))\
        .filter(cast(Prestamo.fecha, Date) == fecha).scalar() or 0.0
    entrada_efectivo, salida_efectivo, gastos = movimientos_caja_totales_para_dia(fecha)
    total_caja = entrada_efectivo - salida_efectivo - gastos
    total_paquetes = paquete_total_actual()

    return {
        "total_abonos": float(total_abonos),
        "total_prestamos": float(total_prestamos),
        "entrada_efectivo": float(entrada_efectivo),
        "salida_efectivo": float(salida_efectivo),
        "gastos": float(gastos),
        "total_caja": float(total_caja),
        "total_paquetes": float(total_paquetes)
    }

from sqlalchemy import func

def paquete_total_para_fecha(fecha):
    """
    Devuelve el total de paquetes (saldos de clientes) hasta una fecha específica.
    Solo incluye clientes activos (cancelado=False).
    """
    fecha = fecha if isinstance(fecha, date) else fecha.date()
    
    clientes = Cliente.query.filter(Cliente.cancelado == False).all()
    total = 0.0
    detalles = []

    for c in clientes:
        # Total de préstamos hasta esa fecha
        prestamos_hasta_fecha = db.session.query(
            func.coalesce(func.sum(Prestamo.monto), 0)
        ).filter(
            Prestamo.cliente_id == c.id,
            func.date(Prestamo.fecha) <= fecha
        ).scalar() or 0.0

        # Total de abonos hasta esa fecha
        abonos_hasta_fecha = db.session.query(
            func.coalesce(func.sum(Abono.monto), 0)
        ).filter(
            Abono.cliente_id == c.id,
            func.date(Abono.fecha) <= fecha
        ).scalar() or 0.0

        saldo_historico = prestamos_hasta_fecha - abonos_hasta_fecha
        if saldo_historico > 0:
            total += saldo_historico
            detalles.append({"cliente": c.nombre, "saldo": saldo_historico})

    return total, detalles


def generar_codigo_numerico():
    code = ''.join(random.choices("0123456789", k=6))
    while Cliente.query.filter_by(codigo=code).first():
        code = ''.join(random.choices("0123456789", k=6))
    return code

def cliente_existente_por_codigo(codigo):
    return Cliente.query.filter_by(codigo=codigo).first()

def cliente_estado_class(cliente: Cliente):
    try:
        hoy = date.today()
        venc = cliente.fecha_creacion + timedelta(days=cliente.plazo)
        if cliente.saldo <= 0:
            return "table-success"
        if cliente.ultimo_abono_fecha == hoy:
            return ""
        if hoy > venc + timedelta(days=30):
            return "table-danger"
        if hoy > venc:
            return "table-warning"
        return ""
    except Exception:
        return ""

def actualizar_estado_cliente(cliente_id):
    cliente = Cliente.query.get(cliente_id)
    if cliente:
        cliente.cancelado = cliente.saldo <= 0
        db.session.commit()

def calcular_cuotas(monto, plazo_dias, frecuencia="diario"):
    if plazo_dias <= 0:
        return 0
    if frecuencia == "diario":
        cuotas = plazo_dias
    elif frecuencia == "semanal":
        cuotas = max(1, plazo_dias // 7)
    elif frecuencia == "quincenal":
        cuotas = max(1, plazo_dias // 15)
    elif frecuencia == "mensual":
        cuotas = max(1, plazo_dias // 30)
    else:
        cuotas = 1
    valor_cuota = monto / cuotas if cuotas else monto
    return round(valor_cuota, 2)

# ---------------------------
# RUTAS: CLIENTES
# ---------------------------
@app.route("/nuevo_cliente", methods=["GET", "POST"])
@login_required
def nuevo_cliente():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        nombre = request.form.get("nombre", "").strip()
        direccion = request.form.get("direccion", "").strip()
        frecuencia = request.form.get("frecuencia", "diario").strip()
        try:
            monto = float(request.form.get("monto", 0) or 0)
            plazo = int(request.form.get("plazo", 0) or 0)
            interes = float(request.form.get("interes", 0) or 0)
            orden = int(request.form.get("orden", 0) or 0)
        except (ValueError, TypeError):
            flash("Monto, plazo, interés y orden deben ser numéricos ❌", "danger")
            return redirect(url_for("nuevo_cliente"))

        if not codigo:
            flash("Debes ingresar un código de cliente ❌", "warning")
            return redirect(url_for("nuevo_cliente"))
        if monto <= 0 or plazo <= 0 or interes < 0 or orden <= 0:
            flash("Por favor ingresa valores válidos para monto, plazo, interés y orden ❌", "warning")
            return redirect(url_for("nuevo_cliente"))

        try:
            cliente_existente = Cliente.query.filter_by(codigo=codigo).first()
            if cliente_existente:
                # actualizar cliente existente
                cliente_existente.monto = monto
                cliente_existente.plazo = plazo
                cliente_existente.interes = interes
                cliente_existente.orden = orden
                cliente_existente.frecuencia = frecuencia
                cliente_existente.saldo = monto + (monto * (interes / 100.0))
                cliente_existente.cancelado = False
                db.session.commit()
                cuota = calcular_cuotas(monto, plazo, frecuencia)
                flash(f"Cliente {cliente_existente.nombre} actualizado correctamente ✅ | Cuota: {cuota}", "success")
            else:
                if not nombre or not direccion:
                    flash("Código no existe. Debes ingresar Nombre y Dirección ❌", "danger")
                    return redirect(url_for("nuevo_cliente"))
                saldo_total = monto + (monto * (interes / 100.0))
                cliente = Cliente(
                    codigo=codigo,
                    nombre=nombre,
                    direccion=direccion,
                    monto=monto,
                    plazo=plazo,
                    interes=interes,
                    orden=orden,
                    frecuencia=frecuencia,
                    saldo=saldo_total,
                    fecha_creacion=date.today(),
                    cancelado=False
                )
                db.session.add(cliente)
                db.session.flush()  # Para obtener el ID del cliente antes de commit

                # --- Crear préstamo automáticamente ---
                prestamo = Prestamo(
                    cliente_id=cliente.id,
                    monto=monto
                )
                db.session.add(prestamo)
                db.session.flush()

                # --- Crear movimiento de caja asociado ---
                mov = MovimientoCaja(
                    tipo="entrada",
                    monto=monto,
                    descripcion=f"Préstamo inicial de {nombre}"
                )
                db.session.add(mov)
                db.session.flush()

                prestamo.movimiento_id = mov.id

                db.session.commit()
                cuota = calcular_cuotas(monto, plazo, frecuencia)
                flash(f"Cliente {nombre} creado correctamente ✅ | Cuota: {cuota}", "success")

            # Actualizar liquidación del día
            actualizar_liquidacion_por_movimiento(date.today())
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()
            import traceback; traceback.print_exc()
            flash(f"Error al guardar cliente: {str(e)} ❌", "danger")
            return redirect(url_for("nuevo_cliente"))

    return render_template("nuevo_cliente.html")


@app.route("/diagnostico_liquidacion")
@login_required
def diagnostico_liquidacion():
    from sqlalchemy import cast, Date

    hoy = date.today()
    # Buscar la liquidación de hoy
    liq = Liquidacion.query.filter_by(fecha=hoy).first()

    total_liq = liq.total_prestamos if liq else 0.0

    # Sumar directamente los préstamos del día
    start = datetime.combine(hoy, datetime.min.time())
    end = datetime.combine(hoy, datetime.max.time())
    prestamos_hoy = Prestamo.query.filter(Prestamo.fecha >= start, Prestamo.fecha <= end).all()
    total_prestamos_real = sum(p.monto for p in prestamos_hoy)

    # Preparar detalles
    prestamos_detalle = [
        {"id": p.id, "cliente": p.cliente.nombre, "monto": p.monto, "fecha": p.fecha, "movimiento_id": p.movimiento_id}
        for p in prestamos_hoy
    ]

    resultado = {
        "fecha": str(hoy),
        "total_en_liquidacion": total_liq,
        "total_real_prestamos": total_prestamos_real,
        "prestamos_no_sumados": total_prestamos_real - total_liq,
        "detalle_prestamos": prestamos_detalle
    }

    return jsonify(resultado)


@app.route("/clientes/<int:cliente_id>/eliminar", methods=["POST"])
@login_required
def eliminar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        db.session.delete(cliente)
        db.session.commit()
        flash(f"Cliente {cliente.nombre} eliminado correctamente ✅", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"No se pudo eliminar al cliente: {str(e)}", "danger")
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
    if cliente in clientes:
        clientes.remove(cliente)
    insert_index = min(nuevo_orden - 1, len(clientes))
    clientes.insert(insert_index, cliente)
    for idx, c in enumerate(clientes, start=1):
        c.orden = idx
    db.session.commit()
    flash("Orden actualizado correctamente", "success")
    return redirect(url_for("index"))

@app.route("/api/cliente/<codigo>")
@login_required
def api_cliente(codigo):
    cliente = Cliente.query.filter_by(codigo=codigo.strip()).first()
    if cliente:
        return jsonify({
            "existe": True,
            "nombre": cliente.nombre,
            "direccion": cliente.direccion,
            "frecuencia": cliente.frecuencia,
            "plazo": cliente.plazo,
            "monto": cliente.monto,
            "interes": cliente.interes,
            "orden": cliente.orden
        })
    else:
        return jsonify({"existe": False})

# ---------------------------
# RUTAS: ABONOS
# ---------------------------
@app.route("/abonar/<int:cliente_id>", methods=["POST"])
@login_required
def abonar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if cliente.cancelado:
        return jsonify({"success": False, "mensaje": "Cliente cancelado"}), 400
    try:
        monto_abono = float(request.form.get("monto_abono", 0))
    except ValueError:
        return jsonify({"success": False, "mensaje": "Abono inválido"}), 400
    if monto_abono <= 0 or monto_abono > cliente.saldo:
        return jsonify({"success": False, "mensaje": "Abono inválido o mayor al saldo"}), 400

    cliente.saldo -= monto_abono
    cliente.ultimo_abono_fecha = date.today()

    ab = Abono(cliente_id=cliente.id, monto=monto_abono, fecha=datetime.utcnow())
    db.session.add(ab)

    mov = MovimientoCaja(
        tipo="entrada",
        monto=monto_abono,
        descripcion=f"Abono {cliente.nombre}",
        fecha=datetime.utcnow()
    )
    db.session.add(mov)
    db.session.flush()
    ab.movimiento_id = mov.id

    if cliente.saldo <= 0:
        cliente.saldo = 0.0
        cliente.cancelado = True

    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    return jsonify({"success": True, "nuevo_saldo": f"{cliente.saldo:.2f}", "cancelado": cliente.cancelado})

@app.route("/eliminar_abono/<int:abono_id>", methods=["POST"])
@login_required
def eliminar_abono(abono_id):
    abono = Abono.query.get_or_404(abono_id)
    cliente = abono.cliente
    fecha_dt = abono.fecha.date() if isinstance(abono.fecha, datetime) else abono.fecha
    if cliente:
        cliente.saldo += abono.monto
        if cliente.saldo > 0:
            cliente.cancelado = False
        if cliente.ultimo_abono_fecha == fecha_dt:
            otros = Abono.query.filter(
                Abono.cliente_id == cliente.id,
                db.func.date(Abono.fecha) == fecha_dt,
                Abono.id != abono.id
            ).count()
            if otros == 0:
                cliente.ultimo_abono_fecha = None
    if abono.movimiento_id:
        mov = MovimientoCaja.query.get(abono.movimiento_id)
        if mov:
            db.session.delete(mov)
    db.session.delete(abono)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(fecha_dt)
    flash("Abono eliminado, saldo repuesto y caja ajustada", "success")
    return redirect(url_for("liquidacion"))

@app.route("/historial_abonos/<int:cliente_id>")
@login_required
def historial_abonos(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    abonos = [{"id": a.id, "fecha": a.fecha.strftime("%d/%m/%Y"), "monto": a.monto} for a in cliente.abonos]
    return jsonify({"abonos": abonos})

@app.route("/detalle_abonos/<fecha>")
@login_required
def detalle_abonos(fecha):
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))
    abonos = Abono.query.filter(cast(Abono.fecha, Date) == fecha_obj).all()
    return render_template("detalle_abonos.html", abonos=abonos, fecha=fecha_obj)

# ---------------------------
# RUTAS: CAJA
# ---------------------------
@app.route("/caja")
def caja():
    movimientos = MovimientoCaja.query.order_by(MovimientoCaja.fecha.desc()).all()
    saldo = sum(m.monto if m.tipo == "entrada" else -m.monto for m in movimientos)
    return render_template("caja.html", movimientos=movimientos, saldo=saldo)

@app.route("/caja/entrada", methods=["GET", "POST"])
def caja_entrada():
    if request.method == "POST":
        try:
            monto = float(request.form.get("monto", 0))
            descripcion = request.form.get("descripcion", "").strip()
            if monto <= 0:
                flash("El monto debe ser mayor a 0", "danger")
            else:
                nuevo = MovimientoCaja(tipo="entrada", monto=monto, descripcion=descripcion)
                db.session.add(nuevo)
                db.session.commit()
                flash("Entrada registrada correctamente", "success")
                return redirect(url_for("caja"))
        except ValueError:
            flash("Monto inválido", "danger")
    return render_template("caja_entrada.html")

@app.route("/caja/salida", methods=["GET", "POST"])
def caja_salida():
    if request.method == "POST":
        try:
            monto = float(request.form.get("monto", 0))
            descripcion = request.form.get("descripcion", "").strip()
            if monto <= 0:
                flash("El monto debe ser mayor a 0", "danger")
            else:
                nuevo = MovimientoCaja(tipo="salida", monto=monto, descripcion=descripcion)
                db.session.add(nuevo)
                db.session.commit()
                flash("Salida registrada correctamente", "success")
                return redirect(url_for("caja"))
        except ValueError:
            flash("Monto inválido", "danger")
    return render_template("caja_salida.html")

@app.route("/caja/gasto", methods=["GET", "POST"])
def caja_gasto():
    if request.method == "POST":
        try:
            monto = float(request.form.get("monto", 0))
            descripcion = request.form.get("descripcion", "").strip()
            if monto <= 0:
                flash("El monto debe ser mayor a 0", "danger")
            else:
                nuevo = MovimientoCaja(tipo="gasto", monto=monto, descripcion=descripcion)
                db.session.add(nuevo)
                db.session.commit()
                flash("Gasto registrado correctamente", "success")
                return redirect(url_for("caja"))
        except ValueError:
            flash("Monto inválido", "danger")
    return render_template("caja_gasto.html")

@app.route("/entrada/detalle/<fecha>")
@login_required
def detalle_entrada(fecha):
    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))

    # Traer todos los movimientos de tipo "entrada" del día
    movimientos = MovimientoCaja.query.filter(
        cast(MovimientoCaja.fecha, Date) == fecha_obj,
        MovimientoCaja.tipo == "entrada"
    ).all()

    return render_template("detalle_entrada.html", movimientos=movimientos, fecha=fecha_obj)

@app.route("/salida/detalle/<fecha>")
@login_required
def detalle_salida(fecha):
    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))

    # Rango completo del día
    start = datetime.combine(fecha_obj, time.min)
    end = datetime.combine(fecha_obj, time.max)

    salidas = MovimientoCaja.query.filter(
        MovimientoCaja.tipo == "salida",
        MovimientoCaja.fecha >= start,
        MovimientoCaja.fecha <= end
    ).all()

    return render_template("detalle_salida.html", salidas=salidas, fecha=fecha_obj)


@app.route("/gasto/detalle/<fecha>")
@login_required
def detalle_gasto(fecha):
    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))
    gastos = MovimientoCaja.query.filter(
        cast(MovimientoCaja.fecha, Date) == fecha_obj,
        MovimientoCaja.tipo == "gasto"
    ).all()
    return render_template("detalle_gasto.html", gastos=gastos, fecha=fecha_obj)

@app.route("/prestamos/detalle/<fecha>")
@login_required
def detalle_prestamos(fecha):
    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))

    prestamos = Prestamo.query.filter(cast(Prestamo.fecha, Date) == fecha_obj).all()
    return render_template("detalle_prestamos.html", prestamos=prestamos, fecha=fecha_obj)

@app.route("/prestamo/eliminar/<int:prestamo_id>", methods=["POST"])
@login_required
def eliminar_prestamo(prestamo_id):
    prestamo = Prestamo.query.get_or_404(prestamo_id)
    fecha = request.args.get("fecha", date.today().isoformat())
    db.session.delete(prestamo)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(datetime.strptime(fecha, "%Y-%m-%d").date())
    flash("Préstamo eliminado", "success")
    return redirect(url_for("detalle_prestamos", fecha=fecha))


# ---------------------------
# RUTAS: LIQUIDACIÓN
# ---------------------------
@app.route("/liquidacion")
@login_required
def liquidacion():
    # Asegurar liquidaciones contiguas y crear la de hoy
    asegurar_liquidaciones_contiguas()
    liq_hoy = crear_liquidacion_para_fecha(date.today())

    hoy = date.today()
    fecha_inicio = request.args.get("fecha_inicio")
    fecha_fin = request.args.get("fecha_fin")

    query = db.session.query(Liquidacion.fecha).distinct().order_by(Liquidacion.fecha.desc())

    # Filtrar por rango de fechas si se especifica
    if fecha_inicio and fecha_fin:
        try:
            f_inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
            f_fin = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
            query = query.filter(Liquidacion.fecha >= f_inicio, Liquidacion.fecha <= f_fin)
        except ValueError:
            flash("Fechas inválidas", "warning")

    fechas_liquidacion = [f[0] for f in query.all()]
    liquidaciones = []

    for f in fechas_liquidacion:
        # Recalcular y actualizar los totales del día en la tabla Liquidacion
        liq = actualizar_liquidacion_por_movimiento(f)

        liquidaciones.append({
            "fecha": f,
            "total_abonos": liq.total_abonos,
            "total_prestamos": liq.total_prestamos,
            "entrada_efectivo": liq.entrada_efectivo,
            "salida_efectivo": liq.salida_efectivo,
            "gastos": liq.gastos,
            "total_caja": liq.total_caja,
            "total_paquetes": liq.total_paquetes,  # <-- aquí ya viene del modelo
        })

    return render_template("liquidacion.html", liquidaciones=liquidaciones, hoy=hoy, liq_hoy=liq_hoy)


@app.route("/detalle_caja/<fecha>")
@login_required
def detalle_caja(fecha):
    """
    Muestra el detalle completo de movimientos de caja de un día específico,
    calculando saldo correctamente, y evitando errores por fechas inválidas.
    """
    try:
        # Convertir string a fecha
        f = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida", "warning")
        return redirect(url_for("liquidacion"))

    # Definir rango completo del día
    start = datetime.combine(f, datetime.min.time())
    end = datetime.combine(f, datetime.max.time())

    # Traer todos los movimientos del día
    movimientos = MovimientoCaja.query.filter(
        MovimientoCaja.fecha >= start,
        MovimientoCaja.fecha <= end
    ).order_by(MovimientoCaja.fecha.asc()).all()

    # Calcular saldo acumulado del día
    saldo = 0.0
    for m in movimientos:
        if m.tipo == "entrada":
            saldo += m.monto
        elif m.tipo in ["salida", "gasto"]:
            saldo -= m.monto

    return render_template("caja.html", movimientos=movimientos, saldo=saldo, fecha=f)

@app.route("/detalle_paquete/<fecha>")
@login_required
def detalle_paquete(fecha):
    # Convertir string a date
    f = datetime.strptime(fecha, "%Y-%m-%d").date()
    
    # Traer la liquidación de esa fecha
    liq = Liquidacion.query.filter_by(fecha=f).first()
    
    paquetes = []
    total = 0.0

    if liq:
        # Usar total_paquetes del modelo
        total = liq.total_paquetes

        # Clientes activos con saldo > 0 actualmente
        clientes_con_saldo = Cliente.query.filter(Cliente.cancelado == False, Cliente.saldo > 0).all()
        paquetes = [{"cliente": c.nombre, "saldo": c.saldo} for c in clientes_con_saldo]

    return render_template("paquetes.html", paquetes=paquetes, total=total, fecha=f)


# ---------------------------
# RUTAS: DASHBOARD / INDEX
# ---------------------------
@app.route("/")
@login_required
def index():
    hoy = date.today()
    total_abonos = db.session.query(func.coalesce(func.sum(Abono.monto), 0)).scalar() or 0.0
    total_prestamos = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0)).scalar() or 0.0
    liquidaciones = db.session.query(Liquidacion).order_by(Liquidacion.fecha.desc()).limit(30).all()
    clientes = Cliente.query.filter_by(cancelado=False).all()
    return render_template("index.html", hoy=hoy, total_abonos=total_abonos, total_prestamos=total_prestamos, liquidaciones=liquidaciones, clientes=clientes)

@app.route("/dashboard")
@login_required
def dashboard():
    total_clientes = Cliente.query.count()
    total_abonos = db.session.query(func.coalesce(func.sum(Abono.monto), 0)).scalar() or 0.0
    total_prestamos = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0)).scalar() or 0.0
    return render_template("dashboard.html", usuario=session.get("usuario"), total_clientes=total_clientes, total_abonos=total_abonos, total_prestamos=total_prestamos)

@app.route("/clientes_cancelados")
@login_required
def clientes_cancelados_view():
    try:
        clientes = Cliente.query.all()
        for c in clientes:
            if c.saldo <= 0 and not c.cancelado:
                c.cancelado = True
        db.session.commit()
        cancelados = Cliente.query.filter_by(cancelado=True).all()
        return render_template("clientes_cancelados.html", clientes_cancelados=cancelados)
    except Exception as e:
        print("Error al cargar clientes cancelados:", e)
        return "Error al cargar clientes cancelados"

# ---------------------------
# ERRORES / INICIALIZACIÓN
# ---------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
