from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tu_clave_secreta_aqui')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///arquitos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# =================== MODELOS ===================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(200))

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True)
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    credit = db.Column(db.Float, default=0)
    balance = db.Column(db.Float, default=0)
    due_days = db.Column(db.Integer, default=0)
    last_payment = db.Column(db.DateTime, default=None)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    type = db.Column(db.String(20))  # ABONO, PRESTAMO
    amount = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =================== UTIL ===================
def generate_client_code():
    last = Client.query.order_by(Client.id.desc()).first()
    return f"C{(last.id + 1) if last else 1:04d}"

def get_color(client):
    today = datetime.utcnow().date()
    if client.last_payment and client.last_payment.date() == today:
        return "table-success"  # verde
    if client.last_payment and client.due_days:
        due_date = client.last_payment.date() + timedelta(days=client.due_days)
        if today > due_date and today <= due_date + timedelta(days=20):
            return "table-warning"  # naranja
        elif today > due_date + timedelta(days=20):
            return "table-danger"   # rojo
    return ""  # normal blanco

# =================== RUTAS ===================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrecta')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    clients = Client.query.all()
    client_data = []
    for c in clients:
        client_data.append({
            'id': c.id,
            'code': c.code,
            'name': c.name,
            'credit': c.credit,
            'balance': c.balance,
            'color': get_color(c)
        })
    return render_template('dashboard.html', clients=client_data)

@app.route('/add_client', methods=['POST'])
def add_client():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    name = request.form['name']
    credit = float(request.form['credit'])
    due_days = int(request.form['due_days'])
    code = generate_client_code()
    client = Client(name=name, credit=credit, balance=credit, due_days=due_days)
    client.code = code
    db.session.add(client)
    db.session.commit()
    flash(f'Cliente {name} agregado con código {code}')
    return redirect(url_for('dashboard'))

@app.route('/add_abono', methods=['POST'])
def add_abono():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    client_id = int(request.form['client_id'])
    amount = float(request.form['amount'])
    client = Client.query.get(client_id)
    if client:
        client.balance -= amount
        client.last_payment = datetime.utcnow()
        tx = Transaction(client_id=client.id, type='ABONO', amount=amount)
        db.session.add(tx)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/liquidacion', methods=['GET', 'POST'])
def liquidacion():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    query = Transaction.query
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(Transaction.created_at >= start)
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        query = query.filter(Transaction.created_at < end)
    txs = query.all()
    total_abonos = sum([t.amount for t in txs if t.type=='ABONO'])
    total_prestamos = sum([t.amount for t in txs if t.type=='PRESTAMO'])
    return render_template('liquidacion.html', txs=txs, total_abonos=total_abonos, total_prestamos=total_prestamos)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =================== INICIO ===================
if __name__ == "__main__":
    db.create_all()  # Crear todas las tablas

    # Crear usuario inicial si no existe
    if not User.query.filter_by(username="mjesus40").first():
        user = User(username="mjesus40", password_hash=generate_password_hash("198409"))
        db.session.add(user)
        db.session.commit()
        print("Usuario inicial creado: mjesus40 / 198409")

    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
