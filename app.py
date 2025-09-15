from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import random
import string

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Simulamos base de datos en memoria
clientes = {}
creditos = []

# --- Login ---
USUARIO = "admin"
CONTRASEÑA = "1234"

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["usuario"]
        pwd = request.form["password"]
        if user == USUARIO and pwd == CONTRASEÑA:
            session["usuario"] = user
            return redirect(url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- Dashboard ---
@app.route("/index")
def index():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", creditos=creditos)

# --- Nuevo Cliente ---
@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "usuario" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        nombre = request.form["nombre"]
        direccion = request.form["direccion"]
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        clientes[codigo] = {"nombre": nombre, "direccion": direccion}
        return redirect(url_for("nuevo_credito", codigo=codigo))
    return render_template("nuevo_cliente.html")

# --- Nuevo Crédito ---
@app.route("/nuevo_credito/<codigo>", methods=["GET", "POST"])
def nuevo_credito(codigo):
    if "usuario" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        orden = request.form["orden"]
        valor = float(request.form["valor"])
        interes = float(request.form["interes"])
        plazo = int(request.form["plazo"])
        fecha = datetime.now()

        credito = {
            "codigo": codigo,
            "orden": orden,
            "nombre": clientes[codigo]["nombre"],
            "valor": valor,
            "interes": interes,
            "plazo": plazo,
            "fecha": fecha,
            "abonos": [],
            "saldo": valor
        }
        creditos.append(credito)
        return redirect(url_for("index"))
    return render_template("nuevo_credito.html", cliente=clientes[codigo], codigo=codigo)

# --- Registrar Abono ---
@app.route("/abonar/<int:idx>", methods=["POST"])
def abonar(idx):
    monto = float(request.form["monto"])
    creditos[idx]["abonos"].append({"monto": monto, "fecha": datetime.now()})
    creditos[idx]["saldo"] -= monto
    return redirect(url_for("index"))

# --- Eliminar Crédito ---
@app.route("/eliminar/<int:idx>")
def eliminar(idx):
    creditos.pop(idx)
    return redirect(url_for("index"))

# --- Liquidación ---
@app.route("/liquidacion", methods=["GET", "POST"])
def liquidacion():
    if "usuario" not in session:
        return redirect(url_for("login"))

    resultados = []
    if request.method == "POST":
        desde = datetime.strptime(request.form["desde"], "%Y-%m-%d")
        hasta = datetime.strptime(request.form["hasta"], "%Y-%m-%d")
        resultados = [c for c in creditos if desde <= c["fecha"].date() <= hasta]

    ultimos = sorted(creditos, key=lambda x: x["fecha"], reverse=True)[:10]
    return render_template("liquidacion.html", ultimos=ultimos, resultados=resultados)

if __name__ == "__main__":
    app.run(debug=True)

