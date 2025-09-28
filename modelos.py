
# modelos.py - Versión completa Liquidación dinámica
from extensions import db
from datetime import datetime, date

# ---------------------------
# MODELO CLIENTE
# ---------------------------
class Cliente(db.Model):
    __tablename__ = "clientes"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    orden = db.Column(db.Integer, nullable=False, default=1)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    monto = db.Column(db.Float, nullable=False, default=0.0)
    plazo = db.Column(db.Integer, nullable=False, default=30)
    interes = db.Column(db.Float, nullable=False, default=0.0)
    saldo = db.Column(db.Float, nullable=False, default=0.0)
    fecha_creacion = db.Column(db.Date, default=date.today)
    ultimo_abono_fecha = db.Column(db.Date, nullable=True)
    cancelado = db.Column(db.Boolean, default=False)
    frecuencia = db.Column(db.String(20), default='diario')

    abonos = db.relationship("Abono", backref="cliente", lazy=True)
    prestamos = db.relationship("Prestamo", backref="cliente", lazy=True)

    # --- NUEVO MÉTODO ---
    def calcular_cuotas(self):
        if self.frecuencia == 'diario':
            num_cuotas = self.plazo
        elif self.frecuencia == 'semanal':
            num_cuotas = self.plazo // 7
        elif self.frecuencia == 'quincenal':
            num_cuotas = self.plazo // 15
        elif self.frecuencia == 'mensual':
            num_cuotas = self.plazo // 30
        else:
            num_cuotas = 0

        valor_cuota = self.monto / num_cuotas if num_cuotas > 0 else 0
        return num_cuotas, valor_cuota

# ---------------------------
# MODELO ABONO
# ---------------------------
class Abono(db.Model):
    __tablename__ = "abonos"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    movimiento_id = db.Column(db.Integer, db.ForeignKey("movimientos_caja.id"), nullable=True)


# ---------------------------
# MODELO PRÉSTAMO
# ---------------------------
class Prestamo(db.Model):
    __tablename__ = "prestamos"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    descripcion = db.Column(db.String(200), nullable=True)
    movimiento_id = db.Column(db.Integer, db.ForeignKey("movimientos_caja.id"), nullable=True)



# ---------------------------
# MODELO MOVIMIENTO DE CAJA
# ---------------------------
class MovimientoCaja(db.Model):
    __tablename__ = "movimientos_caja"
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # entrada, salida
    categoria = db.Column(db.String(20), nullable=False, default="general")  
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------
# MODELO PAQUETE
# ---------------------------
class Paquete(db.Model):
    __tablename__ = "paquetes"
    id = db.Column(db.Integer, primary_key=True)
    valor = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=date.today)


# ---------------------------
# MODELO LIQUIDACIÓN
# ---------------------------
class Liquidacion(db.Model):
    __tablename__ = "liquidaciones"
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, unique=True)
    total_abonos = db.Column(db.Float, default=0.0)
    total_prestamos = db.Column(db.Float, default=0.0)
    total_caja = db.Column(db.Float, default=0.0)
    total_paquetes = db.Column(db.Float, default=0.0)
    entrada_efectivo = db.Column(db.Float, default=0.0)
    salida_efectivo = db.Column(db.Float, default=0.0)
    gastos = db.Column(db.Float, default=0.0)
    saldo_previo = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f"<Liquidacion {self.fecha} | Caja: {self.total_caja:.2f} | Abonos: {self.total_abonos:.2f}>"

# ---------------------------
# HELPERS / UTILIDADES CORREGIDOS
# ---------------------------
from datetime import datetime, date, time, timedelta
from sqlalchemy import func, cast, Date
from modelos import Abono, Prestamo, MovimientoCaja, Cliente, Liquidacion
from extensions import db

def day_range(fecha: date):
    """Devuelve el rango completo del día (inicio y fin)."""
    start = datetime.combine(fecha, time.min)
    end = datetime.combine(fecha, time.max)
    return start, end

def paquete_total_actual():
    """
    Total acumulado de paquetes.
    Solo suma clientes activos con saldo positivo (igual que el proyecto antiguo).
    """
    s = db.session.query(
        func.coalesce(func.sum(Cliente.saldo), 0)
    ).filter(Cliente.cancelado == False, Cliente.saldo > 0).scalar()
    return float(s or 0.0)

def movimientos_caja_totales_para_dia(fecha: date):
    """Totales de entradas, salidas y gastos de caja para un día específico."""
    start, end = day_range(fecha)
    entrada = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha >= start, MovimientoCaja.fecha <= end, MovimientoCaja.tipo == "entrada"
    ).scalar() or 0.0
    salida = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha >= start, MovimientoCaja.fecha <= end, MovimientoCaja.tipo == "salida"
    ).scalar() or 0.0
    gasto = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.fecha >= start, MovimientoCaja.fecha <= end, MovimientoCaja.tipo == "gasto"
    ).scalar() or 0.0
    return float(entrada), float(salida), float(gasto)

def crear_liquidacion_para_fecha(fecha: date):
    """Crea o devuelve la liquidación de una fecha específica."""
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if liq:
        return liq
    liq = Liquidacion(fecha=fecha, total_abonos=0.0, total_prestamos=0.0, caja=0.0, paquete=0.0)
    db.session.add(liq)
    db.session.commit()
    return liq

def actualizar_liquidacion_por_movimiento(fecha: date):
    """Recalcula los totales de la liquidación para la fecha dada."""
    fecha = fecha if isinstance(fecha, date) else fecha.date()
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if not liq:
        liq = crear_liquidacion_para_fecha(fecha)

    start, end = day_range(fecha)

    tot_abonos = float(
        db.session.query(func.coalesce(func.sum(Abono.monto), 0))
        .filter(Abono.fecha >= start, Abono.fecha <= end).scalar() or 0.0
    )
    tot_prestamos = float(
        db.session.query(func.coalesce(func.sum(Prestamo.monto), 0))
        .filter(Prestamo.fecha >= start, Prestamo.fecha <= end).scalar() or 0.0
    )
    paquete_actual = paquete_total_actual()

    anterior = Liquidacion.query.filter(Liquidacion.fecha < fecha).order_by(Liquidacion.fecha.desc()).first()
    caja_anterior = float(anterior.caja) if anterior else 0.0

    mov_entrada, mov_salida, mov_gasto = movimientos_caja_totales_para_dia(fecha)
    caja = caja_anterior + mov_entrada - mov_salida - mov_gasto

    liq.total_abonos = tot_abonos
    liq.total_prestamos = tot_prestamos
    liq.caja = caja
    total = liq.total_paquetes = paquete_actual

    db.session.commit()
    return liq

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
