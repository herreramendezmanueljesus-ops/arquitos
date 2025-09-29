# helpers.py
from datetime import datetime, date, time, timedelta
from sqlalchemy import func, cast, Date
from extensions import db
from modelos import Cliente, Abono, Prestamo, MovimientoCaja, Liquidacion
import random

# ---------------------------
# UTILIDADES DE FECHAS
# ---------------------------
def day_range(fecha: date):
    """Devuelve el rango completo del día (inicio y fin)."""
    start = datetime.combine(fecha, time.min)
    end = datetime.combine(fecha, time.max)
    return start, end

# ---------------------------
# FUNCIONES DE CLIENTES
# ---------------------------
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

# ---------------------------
# CUOTAS
# ---------------------------
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

def calcular_cuotas_objeto(obj):
    if obj.frecuencia == 'diario':
        num_cuotas = obj.plazo
    elif obj.frecuencia == 'semanal':
        num_cuotas = max(1, obj.plazo // 7)
    elif obj.frecuencia == 'quincenal':
        num_cuotas = max(1, obj.plazo // 15)
    elif obj.frecuencia == 'mensual':
        num_cuotas = max(1, obj.plazo // 30)
    else:
        num_cuotas = 1
    valor_cuota = obj.monto / num_cuotas if num_cuotas > 0 else 0
    return num_cuotas, round(valor_cuota, 2)

# ---------------------------
# FUNCIONES DE LIQUIDACIÓN Y PAQUETE
# ---------------------------
def paquete_total_actual():
    s = db.session.query(func.coalesce(func.sum(Cliente.saldo), 0))\
        .filter(Cliente.cancelado == False, Cliente.saldo > 0).scalar()
    return float(s or 0.0)

def movimientos_caja_totales_para_dia(fecha: date):
    start, end = day_range(fecha)
    entrada = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.fecha.between(start, end), MovimientoCaja.tipo == "entrada").scalar() or 0.0
    salida = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.fecha.between(start, end), MovimientoCaja.tipo == "salida").scalar() or 0.0
    gasto = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.fecha.between(start, end), MovimientoCaja.tipo == "gasto").scalar() or 0.0
    return float(entrada), float(salida), float(gasto)

def crear_liquidacion_para_fecha(fecha: date):
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if liq:
        return liq
    liq = Liquidacion(
        fecha=fecha,
        total_abonos=0.0,
        total_prestamos=0.0,
        total_caja=0.0,
        total_paquetes=0.0
    )
    db.session.add(liq)
    db.session.commit()
    return liq

def actualizar_liquidacion_por_movimiento(fecha: date):
    """Recalcula la liquidación de un día, considerando abonos, préstamos y caja acumulada."""
    fecha = fecha if isinstance(fecha, date) else fecha.date()
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if not liq:
        liq = crear_liquidacion_para_fecha(fecha)

    start, end = day_range(fecha)

    tot_abonos = float(db.session.query(func.coalesce(func.sum(Abono.monto), 0))
                       .filter(Abono.fecha.between(start, end)).scalar() or 0.0)
    tot_prestamos = float(db.session.query(func.coalesce(func.sum(Prestamo.monto), 0))
                           .filter(Prestamo.fecha.between(start, end)).scalar() or 0.0)
    paquete_actual = paquete_total_actual()

    anterior = Liquidacion.query.filter(Liquidacion.fecha < fecha)\
        .order_by(Liquidacion.fecha.desc()).first()
    caja_anterior = float(anterior.total_caja) if anterior else 0.0

    mov_entrada, mov_salida, mov_gasto = movimientos_caja_totales_para_dia(fecha)
    caja = caja_anterior + mov_entrada - mov_salida - mov_gasto - tot_prestamos

    liq.total_abonos = tot_abonos
    liq.total_prestamos = tot_prestamos
    liq.total_caja = caja
    liq.total_paquetes = paquete_actual

    db.session.commit()
    return liq

def asegurar_liquidaciones_contiguas():
    hoy = date.today()
    ultima = Liquidacion.query.order_by(Liquidacion.fecha.desc()).first()
    if not ultima:
        crear_liquidacion_para_fecha(hoy)
        return
    dia = ultima.fecha + timedelta(days=1)
    while dia <= hoy:
        crear_liquidacion_para_fecha(dia)
        dia += timedelta(days=1)

# ---------------------------
# FUNCIONES AUTOMÁTICAS DE REGISTRO
# ---------------------------
def registrar_abono_y_actualizar_caja(abono: Abono):
    db.session.add(abono)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(abono.fecha)

def registrar_prestamo_y_actualizar_caja(prestamo: Prestamo):
    db.session.add(prestamo)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(prestamo.fecha)

def registrar_movimiento_caja_y_actualizar_caja(movimiento: MovimientoCaja):
    db.session.add(movimiento)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(movimiento.fecha)

# ---------------------------
# FUNCIONES DE CONSULTA
# ---------------------------
def calcular_total_caja(fecha):
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    start, end = day_range(fecha)

    total_abonos = db.session.query(func.coalesce(func.sum(Abono.monto), 0))\
        .filter(cast(Abono.fecha, Date) == fecha).scalar() or 0.0
    total_prestamos = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0))\
        .filter(cast(Prestamo.fecha, Date) == fecha).scalar() or 0.0
    entrada_efectivo, salida_efectivo, gastos = movimientos_caja_totales_para_dia(fecha)

    anterior = Liquidacion.query.filter(Liquidacion.fecha < fecha)\
        .order_by(Liquidacion.fecha.desc()).first()
    caja_anterior = float(anterior.total_caja) if anterior else 0.0

    total_caja = caja_anterior + entrada_efectivo - salida_efectivo - gastos - total_prestamos
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

def paquete_total_para_fecha(fecha):
    fecha = fecha if isinstance(fecha, date) else fecha.date()
    clientes = Cliente.query.filter(Cliente.cancelado == False).all()
    total = 0.0
    detalles = []

    for c in clientes:
        prestamos_hasta_fecha = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0))\
            .filter(Prestamo.cliente_id == c.id, func.date(Prestamo.fecha) <= fecha).scalar() or 0.0
        abonos_hasta_fecha = db.session.query(func.coalesce(func.sum(Abono.monto), 0))\
            .filter(Abono.cliente_id == c.id, func.date(Abono.fecha) <= fecha).scalar() or 0.0
        saldo_historico = prestamos_hasta_fecha - abonos_hasta_fecha
        if saldo_historico > 0:
            total += saldo_historico
            detalles.append({"cliente": c.nombre, "saldo": saldo_historico})

    return total, detalles
