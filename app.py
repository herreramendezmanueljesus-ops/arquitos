import os
import random
from datetime import datetime, date, timedelta, time
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func

# ---------------------------
# CONFIGURACIÓN APP
# ---------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "clave_secreta_local_cámbiala")

# ---------------------------
# BASE DE DATOS
# ---------------------------
DB_DEFAULT = "postgresql+psycopg2://neondb_owner:npg_cvzpsy7uDj5A@ep-holy-cherry-ad45d0mv-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
DATABASE_URL = os.getenv("DATABASE_URL", DB_DEFAULT)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ---------------------------
# LOGIN
# ---------------------------
VALID_USER = "mjesus40"
VALID_PASS = "198409"

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# ---------------------------
# MODELOS
# ---------------------------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    direccion = db.Column(db.String(255))
    telefono = db.Column(db.String(50))
    orden = db.Column(db.Integer)
    fecha_creacion = db.Column(db.Date, default=date.today)
    cancelado = db.Column(db.Boolean, default=False)
    prestamos = db.relationship("Prestamo", backref="cliente", lazy=True)

    def saldo_total(self):
        return sum(float(p.saldo or 0) for p in self.prestamos)

    def capital_total(self):
        return sum(float(p.monto or 0) for p in self.prestamos)

class Prestamo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    saldo = db.Column(db.Float, nullable=False)
    interes = db.Column(db.Float, default=0.0)
    plazo = db.Column(db.Integer)
    fecha = db.Column(db.Date, default=date.today)
    entregado = db.Column(db.Boolean, default=True)

class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey("prestamo.id"), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)
    prestamo = db.relationship("Prestamo", backref=db.backref("abonos", lazy=True))

class MovimientoCaja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(255))
    fecha = db.Column(db.DateTime, default=datetime.now)

class Liquidacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, unique=True, nullable=False)
    entradas = db.Column(db.Float, default=0.0)
    salidas = db.Column(db.Float, default=0.0)
    gastos = db.Column(db.Float, default=0.0)
    caja = db.Column(db.Float, default=0.0)
    caja_manual = db.Column(db.Float, default=0.0)
    prestamos_hoy = db.Column(db.Float, default=0.0)  # 🏦 Nuevo campo

    @property
    def total_abonos(self):
        return self.entradas or 0.0

    @property
    def total_prestamos(self):
        return self.salidas or 0.0

    @property
    def total_caja(self):
        return self.caja or 0.0

    @property
    def total_gastos(self):
        return self.gastos or 0.0

# ---------------------------
# FUNCIONES AUXILIARES
# ---------------------------
def day_range(fecha: date):
    start = datetime.combine(fecha, time.min)
    end = start + timedelta(days=1)
    return start, end

def generar_codigo_cliente():
    code = ''.join(random.choices('0123456789', k=6))
    while Cliente.query.filter_by(codigo=code).first():
        code = ''.join(random.choices('0123456789', k=6))
    return code

def crear_liquidacion_para_fecha(fecha):
    liq = Liquidacion.query.filter_by(fecha=fecha).first()
    if not liq:
        liq = Liquidacion(fecha=fecha)
        db.session.add(liq)
        db.session.commit()
    return liq

def obtener_resumen_total():
    total_entradas = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.tipo == 'entrada').scalar() or 0.0
    total_salidas = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.tipo == 'salida').scalar() or 0.0
    total_gastos = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.tipo == 'gasto').scalar() or 0.0

    caja_total = total_entradas - total_salidas - total_gastos
    cartera_total = float(db.session.query(func.coalesce(func.sum(Prestamo.saldo), 0)).scalar() or 0.0)
    return {'caja_total': caja_total, 'cartera_total': cartera_total}

def actualizar_liquidacion_por_movimiento(fecha: date):
    start, end = day_range(fecha)

    # 💰 Abonos hechos por clientes (los verdaderos ingresos)
    entradas_abonos = db.session.query(func.coalesce(func.sum(Abono.monto), 0))\
        .join(Prestamo, Abono.prestamo_id == Prestamo.id)\
        .filter(Abono.fecha >= start, Abono.fecha < end).scalar() or 0.0

    # 💵 Movimientos de caja manuales (entradas, salidas y gastos)
    movimientos_entradas = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.tipo == 'entrada',
                MovimientoCaja.fecha >= start,
                MovimientoCaja.fecha < end).scalar() or 0.0

    movimientos_salidas = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.tipo == 'salida',
                MovimientoCaja.fecha >= start,
                MovimientoCaja.fecha < end).scalar() or 0.0

    gastos = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0))\
        .filter(MovimientoCaja.tipo == 'gasto',
                MovimientoCaja.fecha >= start,
                MovimientoCaja.fecha < end).scalar() or 0.0

    # 🏦 Préstamos entregados ese día
    prestamos_entregados = db.session.query(func.coalesce(func.sum(Prestamo.monto), 0))\
        .filter(Prestamo.fecha >= start, Prestamo.fecha < end).scalar() or 0.0

    # 🔁 Obtener la liquidación anterior (para saber cuánto había en caja)
    liq_anterior = Liquidacion.query.filter(Liquidacion.fecha < fecha)\
        .order_by(Liquidacion.fecha.desc()).first()

    caja_anterior = liq_anterior.caja if liq_anterior else 0.0

    # ✅ Entradas totales SOLO de abonos
    entradas_totales = entradas_abonos

    # ✅ Salidas: préstamos + salidas manuales
    salidas_totales = prestamos_entregados + movimientos_salidas

    # 💼 Calcular la caja del día:
    # caja anterior + entradas manuales + abonos - salidas - gastos
    caja_actual = caja_anterior + (movimientos_entradas + entradas_abonos - salidas_totales - gastos)

    # Crear o actualizar la liquidación del día
    liq = crear_liquidacion_para_fecha(fecha)
    liq.entradas = entradas_abonos            # 💰 SOLO abonos
    liq.salidas = salidas_totales
    liq.gastos = gastos
    liq.prestamos_hoy = prestamos_entregados
    liq.caja = caja_actual
    liq.caja_manual = caja_anterior

    db.session.commit()
    return liq

# ---------------------------
# RUTAS
# ---------------------------
@app.route('/')
@login_required
def index():
    clientes = Cliente.query.order_by(Cliente.orden.asc().nullsfirst(), Cliente.id.asc()).all()
    for idx, c in enumerate(clientes, start=1):
        if not c.orden or c.orden != idx:
            c.orden = idx
    db.session.commit()
    resumen = obtener_resumen_total()
    hoy = date.today()
    return render_template('index.html', clientes=clientes, resumen=resumen, hoy=hoy)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario','').strip()
        clave = request.form.get('clave','').strip()
        if usuario == VALID_USER and clave == VALID_PASS:
            session['usuario'] = usuario
            flash('Inicio de sesión correcto','success')
            return redirect(url_for('index'))
        flash('Usuario o clave incorrectos','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    flash('Sesión cerrada','info')
    return redirect(url_for('login'))

@app.route('/clientes_cancelados')
@login_required
def clientes_cancelados_view():
    clientes = Cliente.query.filter_by(cancelado=True).all()
    return render_template('clientes_cancelados.html', clientes=clientes)

# ---------------------------
# RUTAS DE PRÉSTAMOS Y ABONOS
# ---------------------------
@app.route('/otorgar_prestamo/<int:cliente_id>', methods=['POST'])
@login_required
def otorgar_prestamo(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    try:
        monto = float(request.form.get('monto', 0))
        interes = float(request.form.get('interes', 0))
        plazo = int(request.form.get('plazo') or 0)
    except ValueError:
        flash('Valores de préstamo inválidos', 'danger')
        return redirect(url_for('index'))

    if monto <= 0:
        flash('El monto debe ser mayor a 0', 'warning')
        return redirect(url_for('index'))

    # ✅ Cálculo correcto del saldo con interés
    saldo_con_interes = monto + (monto * (interes / 100.0))
    prestamo = Prestamo(
        cliente_id=cliente.id,
        monto=monto,
        interes=interes,
        plazo=plazo,
        fecha=date.today(),
        saldo=saldo_con_interes
    )
    db.session.add(prestamo)

    # Registrar salida en caja (préstamo entregado)
    mov = MovimientoCaja(
        tipo='salida',
        monto=monto,
        descripcion=f'Préstamo a {cliente.nombre}',
        fecha=datetime.now()
    )
    db.session.add(mov)
    db.session.commit()

    # ✅ Actualizamos la liquidación del día
    actualizar_liquidacion_por_movimiento(date.today())

    flash(f'Préstamo de {monto:.2f} otorgado a {cliente.nombre}', 'success')
    return redirect(url_for('index'))

@app.route('/registrar_abono_por_codigo', methods=['POST'])
@login_required
def registrar_abono_por_codigo():
    codigo = request.form.get('codigo','').strip()
    monto = float(request.form.get('monto') or 0)
    if monto <= 0:
        flash('Monto inválido', 'danger')
        return redirect(url_for('liquidacion'))
    cliente = Cliente.query.filter_by(codigo=codigo).first()
    if not cliente:
        flash('Código no encontrado', 'danger')
        return redirect(url_for('liquidacion'))

    prestamo = Prestamo.query.filter(Prestamo.cliente_id==cliente.id, Prestamo.saldo>0).order_by(Prestamo.fecha.desc()).first()
    if not prestamo:
        flash('Cliente sin préstamos pendientes', 'warning')
        return redirect(url_for('liquidacion'))

    abono = Abono(prestamo_id=prestamo.id, monto=monto, fecha=datetime.now())
    db.session.add(abono)
    prestamo.saldo = max(0.0, (prestamo.saldo or 0) - monto)
    mov = MovimientoCaja(tipo='entrada', monto=monto, descripcion=f'Abono de {cliente.nombre}', fecha=datetime.now())
    db.session.add(mov)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    flash(f'Abono de {monto:.2f} registrado para {cliente.nombre}', 'success')
    return redirect(url_for('liquidacion'))

@app.route('/historial_abonos/<int:cliente_id>')
@login_required
def historial_abonos(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    items = []
    for p in cliente.prestamos:
        for a in p.abonos:
            items.append({
                'id': a.id,
                'fecha_dt': a.fecha,
                'fecha': a.fecha.strftime("%d/%m/%Y"),
                'hora': a.fecha.strftime("%H:%M"),
                'nombre': cliente.nombre,
                'monto': float(a.monto)
            })
    items.sort(key=lambda x: x['fecha_dt'], reverse=True)
    for it in items:
        it.pop('fecha_dt', None)
    return jsonify({'abonos': items})

# ---------------------------
# CAJA
# ---------------------------
@app.route('/caja/<tipo>', methods=['POST'])
@login_required
def caja_movimiento(tipo):
    if tipo not in ['entrada','salida','gasto']:
        flash('Tipo inválido','danger')
        return redirect(url_for('liquidacion'))
    monto = float(request.form.get('monto',0))
    if monto <= 0:
        flash('Monto inválido','warning')
        return redirect(url_for('liquidacion'))
    descripcion = request.form.get('descripcion', f'{tipo.capitalize()} manual')
    mov = MovimientoCaja(tipo=tipo, monto=monto, descripcion=descripcion, fecha=datetime.now())
    db.session.add(mov)
    db.session.commit()
    actualizar_liquidacion_por_movimiento(date.today())
    flash(f'{tipo.capitalize()} registrada en caja','success')
    return redirect(url_for('liquidacion'))

@app.route('/caja_entrada', methods=['POST'])
@login_required
def caja_entrada():
    return caja_movimiento('entrada')

@app.route('/caja_salida', methods=['POST'])
@login_required
def caja_salida():
    return caja_movimiento('salida')

# ---------------------------
# LIQUIDACIÓN
# ---------------------------
@app.route('/liquidacion')
@login_required
def liquidacion():
    hoy = date.today()
    liq_hoy = Liquidacion.query.filter_by(fecha=hoy).first()
    if not liq_hoy:
        liq_hoy = Liquidacion(fecha=hoy)
        db.session.add(liq_hoy)
        db.session.commit()

    # Actualizar valores del día
    actualizar_liquidacion_por_movimiento(hoy)
    liq = Liquidacion.query.filter_by(fecha=hoy).first()
    resumen = obtener_resumen_total()

    return render_template(
        'liquidacion.html',
        liq=liq,
        hoy=hoy,
        total_caja=resumen['caja_total'],
        cartera_total=resumen['cartera_total']
    )


# ---------------------------
# HISTORIAL DE LIQUIDACIONES Y ABONOS POR DÍA
# ---------------------------
@app.route('/liquidaciones', methods=['GET', 'POST'])
@login_required
def liquidaciones():
    fecha_desde = request.args.get('desde')
    fecha_hasta = request.args.get('hasta')

    query = Liquidacion.query

    # Si el usuario busca por rango de fechas
    if fecha_desde and fecha_hasta:
        try:
            desde = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
            hasta = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
            query = query.filter(Liquidacion.fecha >= desde, Liquidacion.fecha <= hasta)
        except ValueError:
            flash("Formato de fecha inválido. Use YYYY-MM-DD", "danger")
            return redirect(url_for('liquidaciones'))
    else:
        # ✅ Cambiamos el orden: primero ordenamos, luego limitamos
        query = query.order_by(Liquidacion.fecha.desc()).limit(10)

    # Si ya hay limit, no volvemos a hacer order_by
    if not fecha_desde or not fecha_hasta:
        liquidaciones = query.all()
    else:
        liquidaciones = query.order_by(Liquidacion.fecha.asc()).all()

    # Calcular totales del rango
    total_entradas = sum(l.entradas or 0 for l in liquidaciones)
    total_prestamos = sum(l.prestamos_hoy or 0 for l in liquidaciones)
    total_salidas = sum(l.salidas or 0 for l in liquidaciones)
    total_gastos = sum(l.gastos or 0 for l in liquidaciones)
    total_caja = sum(l.caja or 0 for l in liquidaciones)

    resumen = obtener_resumen_total()

    return render_template(
        'liquidaciones.html',
        liquidaciones=liquidaciones,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        total_entradas=total_entradas,
        total_prestamos=total_prestamos,
        total_salidas=total_salidas,
        total_gastos=total_gastos,
        total_caja=total_caja,
        resumen=resumen
    )


@app.route('/movimientos_por_dia/<tipo>/<fecha>')
@login_required
def movimientos_por_dia(tipo, fecha):
    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    start, end = day_range(fecha_obj)

    movimientos = (
        MovimientoCaja.query
        .filter(MovimientoCaja.tipo == tipo,
                MovimientoCaja.fecha >= start,
                MovimientoCaja.fecha < end)
        .order_by(MovimientoCaja.fecha.desc())
        .all()
    )

    total = sum(m.monto for m in movimientos)

    # Determinar título descriptivo
    if tipo == 'entrada':
        titulo = "Entradas de Caja"
    elif tipo == 'salida':
        titulo = "Salidas de Caja"
    elif tipo == 'gasto':
        titulo = "Gastos"
    else:
        titulo = "Movimientos"

    return render_template('movimientos_por_dia.html',
                           movimientos=movimientos,
                           tipo=tipo,
                           fecha=fecha_obj,
                           total=total,
                           titulo=titulo)

# ---------------------------
# DETALLES DE MOVIMIENTOS POR DÍA
# ---------------------------

@app.route('/prestamos_por_dia/<fecha>')
@login_required
def prestamos_por_dia(fecha):
    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    start, end = day_range(fecha_obj)

    prestamos = (
        Prestamo.query
        .filter(Prestamo.fecha >= start, Prestamo.fecha < end)
        .join(Cliente, Prestamo.cliente_id == Cliente.id)
        .add_columns(Cliente.nombre, Prestamo.monto, Prestamo.fecha)
        .order_by(Prestamo.fecha.desc())
        .all()
    )

    total_prestamos = sum(p.monto for p in prestamos)

    return render_template('prestamos_por_dia.html', prestamos=prestamos, fecha=fecha_obj, total_prestamos=total_prestamos)


@app.route('/salidas_por_dia/<fecha>')
@login_required
def salidas_por_dia(fecha):
    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    start, end = day_range(fecha_obj)

    salidas = (
        MovimientoCaja.query
        .filter(MovimientoCaja.tipo == 'salida',
                MovimientoCaja.fecha >= start,
                MovimientoCaja.fecha < end)
        .order_by(MovimientoCaja.fecha.desc())
        .all()
    )

    total_salidas = sum(s.monto for s in salidas)

    return render_template('salidas_por_dia.html', salidas=salidas, fecha=fecha_obj, total_salidas=total_salidas)


@app.route('/gastos_por_dia/<fecha>')
@login_required
def gastos_por_dia(fecha):
    fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    start, end = day_range(fecha_obj)

    gastos = (
        MovimientoCaja.query
        .filter(MovimientoCaja.tipo == 'gasto',
                MovimientoCaja.fecha >= start,
                MovimientoCaja.fecha < end)
        .order_by(MovimientoCaja.fecha.desc())
        .all()
    )

    total_gastos = sum(g.monto for g in gastos)

    return render_template('gastos_por_dia.html', gastos=gastos, fecha=fecha_obj, total_gastos=total_gastos)

# ---------------------------
# CRUD CLIENTE
# ---------------------------
@app.route('/nuevo_cliente', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        codigo = request.form.get('codigo')
        direccion = request.form.get('direccion')
        telefono = request.form.get('telefono')
        monto = request.form.get('monto', type=float)
        if not nombre or not codigo:
            flash("Debe ingresar nombre y código.", "warning")
            return redirect(url_for('nuevo_cliente'))
        cliente = Cliente(nombre=nombre, codigo=codigo, direccion=direccion, telefono=telefono)
        db.session.add(cliente)
        db.session.commit()
        if monto and monto > 0:
            prestamo = Prestamo(cliente_id=cliente.id, monto=monto, saldo=monto, fecha=date.today())
            db.session.add(prestamo)
            mov = MovimientoCaja(tipo='salida', monto=monto, descripcion=f'Préstamo inicial a {nombre}', fecha=datetime.now())
            db.session.add(mov)
            db.session.commit()
            actualizar_liquidacion_por_movimiento(date.today())
        flash(f"Cliente {nombre} creado correctamente.", "success")
        return redirect(url_for('nuevo_cliente'))
    codigo_sugerido = generar_codigo_cliente()
    return render_template("nuevo_cliente.html", codigo_sugerido=codigo_sugerido)

@app.route('/reactivar_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def reactivar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.cancelado = False
    db.session.commit()
    flash(f'Cliente {cliente.nombre} reactivado correctamente.', 'success')
    return redirect(url_for('clientes_cancelados_view'))

@app.route('/actualizar_orden/<int:cliente_id>', methods=['POST'])
@login_required
def actualizar_orden(cliente_id):
    nueva_orden = request.form.get('orden', type=int)
    if nueva_orden is None:
        flash("Debe ingresar un número de orden válido.", "warning")
        return redirect(url_for('index'))

    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.orden = nueva_orden
    db.session.commit()

    flash(f"Orden del cliente {cliente.nombre} actualizada a {nueva_orden}.", "success")
    return redirect(url_for('index'))

@app.route('/eliminar_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def eliminar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    for p in cliente.prestamos:
        Abono.query.filter_by(prestamo_id=p.id).delete()
        db.session.delete(p)
    db.session.delete(cliente)
    db.session.commit()
    flash(f"Cliente {cliente.nombre} eliminado correctamente.", "success")
    return redirect(url_for('index'))

# ---------------------------
# ERRORES E INICIALIZACIÓN
# ---------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
