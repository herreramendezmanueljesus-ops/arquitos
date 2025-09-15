from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Necesario para flash messages
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    fecha = db.Column(db.Date, default=datetime.utcnow)
    monto = db.Column(db.Float, default=0.0)

class Prestamo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    fecha = db.Column(db.Date, default=datetime.utcnow)
    monto = db.Column(db.Float, default=0.0)

# ============== INICIALIZACIÓN =====================
with app.app_context():
    db.create_all()
    # Crear usuario inicial si no existe
    if not User.query.filter_by(username="mjesus40").first():
        u = User(username="mjesus40", password_hash=generate_password_hash("198409"))
        db.session.add(u)
        db.session.commit()

# ============== RUTAS ==============================
@app.route('/')
def index():
    clientes = Cliente.query.order_by(Cliente.orden).all()
    return render_template('index.html', clientes=clientes)

@app.route('/editar_orden', methods=['POST'])
def editar_orden():
    cliente_id = request.form['cliente_id']
    orden = int(request.form['orden'])
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        flash("Cliente no encontrado", "danger")
        return redirect(url_for('index'))
    cliente.orden = orden
    db.session.commit()
    flash("Orden actualizada correctamente", "success")
    return redirect(url_for('index'))

@app.route('/agregar_abono', methods=['POST'])
def agregar_abono():
    cliente_id = request.form['cliente_id']
    monto = float(request.form['monto'])
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        flash("Cliente no encontrado", "danger")
        return redirect(url_for('index'))
    ab = Abono(cliente_id=cliente.id, monto=monto)
    db.session.add(ab)
    cliente.saldo -= monto
    db.session.commit()
    flash(f"Abono de ${monto:.2f} agregado a {cliente.nombre}", "success")
    return redirect(url_for('index'))

@app.route('/liquidacion')
def liquidacion():
    # Obtener últimas 10 fechas con movimientos
    fechas = db.session.query(Prestamo.fecha).distinct().order_by(Prestamo.fecha.desc()).limit(10)
    registros = []
    for f in fechas:
        total_prestamos = sum(p.monto for p in Prestamo.query.filter_by(fecha=f[0]).all())
        total_abonos = sum(a.monto for a in Abono.query.filter_by(fecha=f[0]).all())
        suma_paquete = sum(c.saldo for c in Cliente.query.all())
        registros.append({
            'fecha': f[0].strftime("%d-%m-%Y"),
            'total_prestamos': total_prestamos,
            'total_abonos': total_abonos,
            'suma_paquete': suma_paquete
        })
    return render_template('liquidacion.html', registros=registros)

@app.route('/detalle/<tipo>')
def detalle(tipo):
    fecha_str = request.args.get('fecha')
    fecha = datetime.strptime(fecha_str, "%d-%m-%Y").date()
    detalles = []
    if tipo == 'prestamos':
        prestamos = Prestamo.query.filter_by(fecha=fecha).all()
        for p in prestamos:
            cliente = Cliente.query.get(p.cliente_id)
            if cliente:
                detalles.append({'nombre': cliente.nombre, 'monto': p.monto})
    elif tipo == 'abonos':
        abonos = Abono.query.filter_by(fecha=fecha).all()
        for a in abonos:
            cliente = Cliente.query.get(a.cliente_id)
            if cliente:
                detalles.append({'nombre': cliente.nombre, 'monto': a.monto})
    return jsonify(detalles)

# ================= LOGIN =====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        u = User.query.filter_by(username=usuario).first()
        if u and check_password_hash(u.password_hash, password):
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for('index'))
        else:
            flash("Usuario o contraseña incorrectos", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
