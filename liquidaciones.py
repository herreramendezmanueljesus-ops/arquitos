
# liquidaciones.py
from datetime import datetime, date, time, timedelta
from sqlalchemy import func
from modelos import db, Cliente, Abono, Prestamo, MovimientoCaja, Paquete, Liquidacion

# ---------------------------
# Funciones auxiliares
# ---------------------------

def day_range(fecha: date):
    """Devuelve inicio y fin del día (00:00:00 y 23:59:59)."""
    start = datetime.combine(fecha, time.min)
    end = datetime.combine(fecha, time.max)
    return start, end

def movimientos_caja_totales_para_dia(fecha: date):
    """Calcula totales de entrada, salida y gasto de caja para un día."""
    start, end = day_range(fecha)

    entrada = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha >= start,
        MovimientoCaja.fecha <= end,
        MovimientoCaja.tipo == "entrada"
    ).scalar() or 0.0

    salida = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha >= start,
        MovimientoCaja.fecha <= end,
        MovimientoCaja.tipo == "salida"
    ).scalar() or 0.0

    gasto = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha >= start,
        MovimientoCaja.fecha <= end,
        MovimientoCaja.tipo == "gasto"
    ).scalar() or 0.0

    return float(entrada), float(salida), float(gasto)

def total_abonos_para_dia(fecha: date):
    start, end = day_range(fecha)
    total = db.session.query(func.coalesce(func.sum(Abono.monto), 0)).filter(
        Abono.fecha >= start,
        Abono.fecha <= end
    ).scalar() or 0.0
    return float(total)

def total_prestamos_para_dia(fecha: date):
    start, end = day_range(fecha)
    total = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0)).filter(
        Prestamo.fecha >= start,
        Prestamo.fecha <= end
    ).scalar() or 0.0
    return float(total)

def total_paquetes_para_dia(fecha: date):
    total = db.session.query(func.coalesce(func.sum(Paquete.valor), 0)).filter(
        Paquete.fecha == fecha
    ).scalar() or 0.0
    return float(total)

def caja_anterior(fecha: date):
    """Trae la caja total del día anterior como saldo previo."""
    dia_anterior = fecha - timedelta(days=1)
    liq = Liquidacion.query.filter_by(fecha=dia_anterior).first()
    return liq.total_caja if liq else 0.0

# ---------------------------
# Función principal a importar
# ---------------------------

def actualizar_liquidacion_por_movimiento(fecha=None):
    """
    Actualiza la liquidación de un día según abonos, préstamos,
    movimientos de caja, gastos y paquetes.
    """
    fecha = fecha or date.today()

    abonos = total_abonos_para_dia(fecha)
    prestamos = total_prestamos_para_dia(fecha)
    entrada, salida, gasto = movimientos_caja_totales_para_dia(fecha)
    total_paquetes = total_paquetes_para_dia(fecha)
    saldo_prev = caja_anterior(fecha)

    total_caja = saldo_prev + abonos - prestamos + entrada - salida - gasto

    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if not liq:
        liq = Liquidacion(fecha=fecha)
        db.session.add(liq)

    liq.saldo_previo = saldo_prev
    liq.total_abonos = abonos
    liq.total_prestamos = prestamos
    liq.entrada_efectivo = entrada
    liq.salida_efectivo = salida
    liq.gastos = gasto
    liq.total_paquetes = total_paquetes
    liq.total_caja = total_caja

    db.session.commit()

    return {
        "fecha": fecha,
        "caja_anterior": saldo_prev,
        "total_abonos": abonos,
        "total_prestamos": prestamos,
        "entrada_efectivo": entrada,
        "salida_efectivo": salida,
        "gastos": gasto,
        "total_paquetes": total_paquetes,
        "total_caja": total_caja
    }
