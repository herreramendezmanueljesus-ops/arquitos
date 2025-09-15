from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os

# =====================
# CONFIGURACIÓN
# =====================
app = Flask(__name__)
app.secret_key = "clave_super_secreta"  # Necesaria para sesiones y mensajes flash

# Base de datos SQLite en un archivo local (database.db)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "database.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =====================
# MODELO DE USUARIOS
# =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)       # ID autoincremental
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

# Crear tablas automáticamente al arrancar
with app.app_context():
    db.create_all()
    # Crear usuario por defecto si no existe
    if not User.query.filter_by(username="mjesus40").first():
        user = User(username="mjesus40", password="198409")
        db.session.add(user)
        db.session.commit()

# =====================
# RUTAS
# =====================

# Redirige a login si no hay sesión
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Buscar usuario en la base de datos
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user"] = user.username
            flash("Has iniciado sesión correctamente.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")

# PANEL PRINCIPAL (solo si hay sesión activa)
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"])

# LOGOUT
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("login"))

# =====================
# ARRANQUE LOCAL
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
