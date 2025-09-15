from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "cámbiala_por_una_muy_secreta"  # ⚠️ cámbiala en producción
db = SQLAlchemy(app)

# ================= MODELOS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    orden = db.Column(db.Integer, default=0)
    credito = db.Column(db.Float, default=0.0)
    saldo = db.Column(db.Float, default=0.0)

class Abono(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    fecha = db.Column(db.Date, default=lambda: datetime.utcnow().date())
    monto = db.Column(db.Float, default=0.0)

class Prestamo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    fecha = db.Column(db.Date, default=lambda: datetime.utcnow().date())
    monto = db.Column(db.Float, default=0.0)


# ============== HELPERS =====================
from functools import wraps
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ============== INICIALIZACIÓN =====================
with app.app_context():
    db.create_all()
    # Crear usuario inicial si no existe (usuario: mjesus40, pwd: 198409) - hash seguro
    if not User.query.filter_by(username="mjesus40").first():
        u = User(username="mjesus40", password_hash=generate_password_hash("198409"))
        db.session.add(u)
        db.session.commit()


# ============== RUTAS =====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        u = User.query.filter_by(username=usuario).first()
        if u and check_password_hash(u.password_hash, password):
            session["usuario"] = u.username
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for('index'))
        flash("Usuario o contraseña incorrectos", "danger")
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop("usuario", None)
    flash("Sesión cerrada", "info")
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template('index.html', clientes=clientes)


@app.route('/nuevo_cliente', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        nombre = request.form['nombre'].strip()
        credito = float(request.form.get('credito', 0) or 0)
        cliente = Cliente(nombre=nombre, credito=credito, saldo=credito)
        db.session.add(cliente)
        db.session.commit()
        flash(f"Cliente '{nombre}' creado", "success")
        return redirect(url_for('index'))
    return render_template('nuevo_cliente.html')


@app.route('/editar_cliente/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if request.method == 'POST':
        cliente.nombre = request.form['nombre']
        cliente.credito = float(request.form.get('credito', cliente.credito))
        cliente.saldo = float(request.form.get('saldo', cliente.saldo))
        db.session.commit()
        flash("Cliente actualizado", "success")
        return redirect(url_for('index'))
    return render_template('editar_cliente.html', cliente=cliente)


@app.route('/eliminar_cliente', methods=['POST'])
@login_required
def eliminar_cliente():
    cid = request.form.get('cliente_id')
    cliente = Cliente.query.get(cid)
    if not cliente:
        flash("Cliente no encontrado", "danger")
        return redirect(url_for('index'))
    # Borra también préstamos y abonos asociados
    Abono.query.filter_by(cliente_id=cliente.id).delete()
    Prestamo.query.filter_by(cliente_id=cliente.id).delete()
    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente y movimientos asociados eliminados", "success")
    return redirect(url_for('index'))


@app.route('/editar_orden', methods=['POST'])
@login_required
def editar_orden():
    cliente_id = request.form['cliente_id']
    orden = int(request.form.get('orden', 0))
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        flash("Cliente no encontrado", "danger")
        return redirect(url_for('index'))
    cliente.orden = orden
    db.session.commit()
    flash("Orden actualizada", "success")
    return redirect(url_for('index'))


@app.route('/agregar_abono', methods=['POST'])
@login_required
def agregar_abono():
    cliente_id = request.form['cliente_id']
    monto = float(request.form.get('monto', 0) or 0)
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        flash("Cliente no encontrado", "danger")
        return redirect(url_for('index'))
    ab = Abono(cliente_id=cliente.id, monto=monto, fecha=datetime.utcnow().date())
    db.session.add(ab)
    cliente.saldo -= monto
    db.session.commit()
    flash(f"Abono ${monto:.2f} agregado a {cliente.nombre}", "success")
    return redirect(url_for('index'))


@app.route('/agregar_prestamo', methods=['POST'])
@login_required
def agregar_prestamo():
    cliente_id = request.form['cliente_id']
    monto = float(request.form.get('monto', 0) or 0)
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        flash("Cliente no encontrado", "danger")
        return redirect(url_for('index'))
    p = Prestamo(cliente_id=cliente.id, monto=monto, fecha=datetime.utcnow().date())
    db.session.add(p)
    cliente.saldo += monto
    db.session.commit()
    flash(f"Préstamo ${monto:.2f} registrado para {cliente.nombre}", "success")
    return redirect(url_for('index'))


# ==== Liquidación: últimas 10 fechas o por rango ====
def _dates_union_ordered_desc(limit=10):
    # Tomar fechas de ambos modelos, unificarlas, ordenar desc y limitar
    fechas_p = [r[0] for r in db.session.query(Prestamo.fecha).distinct()]
    fechas_a = [r[0] for r in db.session.query(Abono.fecha).distinct()]
    union = sorted(set(fechas_p + fechas_a), reverse=True)
    return union[:limit]

@app.route('/liquidacion', methods=['GET'])
@login_required
def liquidacion():
    start = request.args.get('start')  # formato yyyy-mm-dd
    end = request.args.get('end')
    registros = []

    if start and end:
        try:
            dstart = datetime.strptime(start, "%Y-%m-%d").date()
            dend = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            flash("Formato de fecha inválido. Usa yyyy-mm-dd.", "danger")
            return redirect(url_for('liquidacion'))
        # generar lista de fechas entre start y end inclusive
        days = []
        current = dstart
        while current <= dend:
            days.append(current)
            current += timedelta(days=1)
        fechas = days
    else:
        # últimas 10 fechas con movimientos
        fechas = _dates_union_ordered_desc(limit=10)

    for f in fechas:
        total_prestamos = sum(p.monto for p in Prestamo.query.filter_by(fecha=f).all())
        total_abonos = sum(a.monto for a in Abono.query.filter_by(fecha=f).all())
        suma_paquete = sum(c.saldo for c in Cliente.query.all())
        registros.append({
            'fecha': f.strftime("%d-%m-%Y"),
            'fecha_iso': f.strftime("%Y-%m-%d"),
            'total_prestamos': total_prestamos,
            'total_abonos': total_abonos,
            'suma_paquete': suma_paquete
        })
    return render_template('liquidacion.html', registros=registros, start=start, end=end)


# ==== Detalle (JSON) para AJAX ====
@app.route('/detalle/<tipo>')
@login_required
def detalle(tipo):
    fecha_str = request.args.get('fecha')
    if not fecha_str:
        return jsonify([])

    # aceptar fecha dd-mm-yyyy o yyyy-mm-dd
    try:
        if "-" in fecha_str and len(fecha_str.split("-")[0]) == 4:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        else:
            fecha = datetime.strptime(fecha_str, "%d-%m-%Y").date()
    except ValueError:
        return jsonify([])

    detalles = []
    if tipo == 'prestamos':
        items = Prestamo.query.filter_by(fecha=fecha).all()
        for p in items:
            cliente = Cliente.query.get(p.cliente_id)
            detalles.append({'id': p.id, 'cliente_id': p.cliente_id, 'nombre': cliente.nombre if cliente else "N/A", 'monto': p.monto})
    elif tipo == 'abonos':
        items = Abono.query.filter_by(fecha=fecha).all()
        for a in items:
            cliente = Cliente.query.get(a.cliente_id)
            detalles.append({'id': a.id, 'cliente_id': a.cliente_id, 'nombre': cliente.nombre if cliente else "N/A", 'monto': a.monto})
    return jsonify(detalles)


# ==== Borrar abono / prestamo (AJAX) ====
@app.route('/delete_abono/<int:abono_id>', methods=['POST'])
@login_required
def delete_abono(abono_id):
    a = Abono.query.get(abono_id)
    if not a:
        return jsonify({'ok': False, 'msg': 'Abono no encontrado'}), 404
    cliente = Cliente.query.get(a.cliente_id)
    if cliente:
        cliente.saldo += a.monto  # revertir
    db.session.delete(a)
    db.session.commit()
    return jsonify({'ok': True})

@app.route('/delete_prestamo/<int:prestamo_id>', methods=['POST'])
@login_required
def delete_prestamo(prestamo_id):
    p = Prestamo.query.get(prestamo_id)
    if not p:
        return jsonify({'ok': False, 'msg': 'Préstamo no encontrado'}), 404
    cliente = Cliente.query.get(p.cliente_id)
    if cliente:
        cliente.saldo -= p.monto  # revertir
    db.session.delete(p)
    db.session.commit()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
