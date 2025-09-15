from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "clave_super_secreta"

# Usuario y contraseña definidos
USUARIO = "mjesus40"
CLAVE = "198409"


# =========================
# Rutas principales
# =========================
@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("inicio"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Página de inicio de sesión"""
    if request.method == "POST":
        usuario = request.form.get("username")
        clave = request.form.get("password")

        if usuario == USUARIO and clave == CLAVE:
            session["user"] = usuario
            flash("Bienvenido, sesión iniciada correctamente", "success")
            return redirect(url_for("inicio"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Cerrar sesión"""
    session.clear()
    flash("Has cerrado sesión", "info")
    return redirect(url_for("login"))


# =========================
# Vistas del sistema
# =========================
@app.route("/inicio")
def inicio():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("inicio.html", usuario=session["user"])


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")


@app.route("/nuevo_cliente", methods=["GET", "POST"])
def nuevo_cliente():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        # Aquí procesarías los datos del formulario
        nombre = request.form.get("nombre")
        direccion = request.form.get("direccion")
        orden = request.form.get("orden")
        flash(f"Cliente {nombre} creado con éxito", "success")
        return redirect(url_for("dashboard"))

    return render_template("nuevo_cliente.html")


@app.route("/editar_cliente", methods=["GET", "POST"])
def editar_cliente():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        flash("Cliente actualizado correctamente", "success")
        return redirect(url_for("dashboard"))

    return render_template("editar_cliente.html")


@app.route("/liquidacion")
def liquidacion():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("liquidacion.html")


@app.route("/lodging")
def lodging():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("lodging.html")


@app.route("/nuevo_credito", methods=["GET", "POST"])
def nuevo_credito():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        monto = request.form.get("monto")
        plazo = request.form.get("plazo")
        interes = request.form.get("interes")
        flash(f"Crédito creado: ${monto} - Plazo {plazo} días", "success")
        return redirect(url_for("dashboard"))

    return render_template("nuevo_credito.html")


# =========================
# Error handlers
# =========================
@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template("404.html"), 404


# =========================
# Inicialización
# =========================
if __name__ == "__main__":
    app.run(debug=True)
