# caja.py
from datetime import datetime, date, time, timedelta
from sqlalchemy import func, cast
from modelos import db, Cliente, Abono, Prestamo, MovimientoCaja, Paquete

# ---------------------------------
# Funciones de Caja
# ---------------------------------

def day_range(fecha: date):
    """
    Devuelve inicio y fin del día para consultas de SQLAlchemy.
    start = 00:00:00
    end = 23:59:59
    """
    start = datetime.combine(fecha, time.min)
    end = datetime.combine(fecha, time.max)
    return start, end


def movimientos_caja_totales_para_dia(fecha: date):
    """
    Calcula total de entradas, salidas y gastos para un día.
    Devuelve siempre float.
    """
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
    """Suma total de abonos realizados en un día."""
    start, end = day_range(fecha)
    total = db.session.query(func.coalesce(func.sum(Abono.monto), 0)).filter(
        Abono.fecha >= start,
        Abono.fecha <= end
    ).scalar() or 0.0
    return float(total)


def total_prestamos_para_dia(fecha: date):
    """Suma total de préstamos realizados en un día."""
    start, end = day_range(fecha)
    total = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0)).filter(
        Prestamo.fecha >= start,
        Prestamo.fecha <= end
    ).scalar() or 0.0
    return float(total)


def total_paquetes_para_dia(fecha: date):
    """Suma de paquetes activos en un día."""
    total = db.session.query(func.coalesce(func.sum(Paquete.valor), 0)).filter(
        Paquete.fecha == fecha
    ).scalar() or 0.0
    return float(total)


def caja_anterior(fecha: date):
    """
    Devuelve el saldo de caja del día anterior.
    Si no hay liquidación anterior, devuelve 0.0
    """
    from modelos import Liquidacion
    dia_anterior = fecha - timedelta(days=1)
    liq = Liquidacion.query.filter_by(fecha=dia_anterior).first()
    return float(liq.total_caja) if liq else 0.0


def calcular_total_caja(fecha: date):
    """
    Calcula la caja total del día.
    total_caja = caja_anterior + abonos - prestamos + entradas - salidas - gastos
    Retorna un diccionario con todos los totales desglosados.
    """
    abonos = total_abonos_para_dia(fecha)
    prestamos = total_prestamos_para_dia(fecha)
    entrada, salida, gasto = movimientos_caja_totales_para_dia(fecha)
    total_paquetes = total_paquetes_para_dia(fecha)
    anterior = caja_anterior(fecha)

    total_caja = anterior + abonos - prestamos + entrada - salida - gasto

    # Asegurar que el total no sea None ni negativo inesperadamente
    total_caja = max(float(total_caja), 0.0)

    return {
        "caja_anterior": float(anterior),
        "total_abonos": float(abonos),
        "total_prestamos": float(prestamos),
        "entrada_efectivo": float(entrada),
        "salida_efectivo": float(salida),
        "gastos": float(gasto),
        "total_paquetes": float(total_paquetes),
        "total_caja": total_caja
    }
