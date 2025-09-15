import sqlite3
import random
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

DB = "database.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE,
                    nombre TEXT,
                    direccion TEXT,
                    orden INTEGER
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS prestamos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    monto REAL,
                    interes REAL,
                    plazo INTEGER,
                    fecha TEXT,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
                )""")
    c.execute("""CREATE TABLE IF NOT EXISTS abonos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    monto REAL,
                    fecha TEXT,
                    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
                )""")
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""SELECT cl.id, cl.codigo, cl.nombre, cl.direccion, cl.orden,
                        IFNULL(SUM(pr.monto),0) as credito,
                        IFNULL(SUM(ab.monto),0) as abonos,
                        IFNULL(SUM(pr.monto),0) - IFNULL(SUM(ab.monto),0) as saldo
                 FROM clientes cl
                 LEFT JOIN prestamos pr ON cl.id = pr.cliente_id
                 LEFT JOIN abonos ab ON cl.id = ab.cliente_id
                 GROUP BY cl.id
                 ORDER BY cl.orden ASC""")
    clientes = c.fetchall()
    conn.close()
    return render_template("index.html", clientes=clientes)

@app.route("/nuevo_cliente", methods=["POST"])
def nuevo_cliente():
    nombre = request.form["nombre"]
    direccion = request.form["direccion"]
    codigo = str(random.randint(10000, 99999))
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO clientes (codigo, nombre, direccion, orden) VALUES (?,?,?,?)",
              (codigo, nombre, direccion, 9999))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/nuevo_prestamo/<codigo>", methods=["POST"])
def nuevo_prestamo(codigo):
    monto = request.form["monto"]
    interes = request.form["interes"]
    plazo = request.form["plazo"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id FROM clientes WHERE codigo=?",(codigo,))
    cliente_id = c.fetchone()[0]
    c.execute("INSERT INTO prestamos (cliente_id, monto, interes, plazo, fecha) VALUES (?,?,?,?,date('now'))",
              (cliente_id, monto, interes, plazo))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/abono/<codigo>", methods=["POST"])
def abono(codigo):
    monto = request.form["monto"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id FROM clientes WHERE codigo=?",(codigo,))
    cliente_id = c.fetchone()[0]
    c.execute("INSERT INTO abonos (cliente_id, monto, fecha) VALUES (?,?,date('now'))",
              (cliente_id, monto))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/eliminar/<tabla>/<int:id>", methods=["POST"])
def eliminar(tabla, id):
    if tabla not in ("prestamos","abonos","clientes"):
        return "No permitido", 400
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(f"DELETE FROM {tabla} WHERE id=?",(id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/liquidacion", methods=["GET","POST"])
def liquidacion():
    fecha1 = request.form.get("fecha1")
    fecha2 = request.form.get("fecha2")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if fecha1 and fecha2:
        c.execute("""SELECT fecha,
                            (SELECT IFNULL(SUM(monto),0) FROM prestamos WHERE date(fecha)=d.fecha) as total_prestamos,
                            (SELECT IFNULL(SUM(monto),0) FROM abonos WHERE date(fecha)=d.fecha) as total_abonos,
                            (SELECT IFNULL(SUM(monto),0) FROM prestamos WHERE date(fecha)=d.fecha) -
                            (SELECT IFNULL(SUM(monto),0) FROM abonos WHERE date(fecha)=d.fecha) as suma_paquete
                     FROM (SELECT date(fecha) as fecha FROM prestamos
                           UNION
                           SELECT date(fecha) FROM abonos) d
                     WHERE fecha BETWEEN ? AND ?
                     ORDER BY fecha DESC""",(fecha1,fecha2))
    else:
        c.execute("""SELECT fecha,
                            (SELECT IFNULL(SUM(monto),0) FROM prestamos WHERE date(fecha)=d.fecha) as total_prestamos,
                            (SELECT IFNULL(SUM(monto),0) FROM abonos WHERE date(fecha)=d.fecha) as total_abonos,
                            (SELECT IFNULL(SUM(monto),0) FROM prestamos WHERE date(fecha)=d.fecha) -
                            (SELECT IFNULL(SUM(monto),0) FROM abonos WHERE date(fecha)=d.fecha) as suma_paquete
                     FROM (SELECT date(fecha) as fecha FROM prestamos
                           UNION
                           SELECT date(fecha) FROM abonos) d
                     ORDER BY fecha DESC
                     LIMIT 10""")
    registros = c.fetchall()
    conn.close()
    return render_template("liquidacion.html", registros=registros)

@app.route("/detalle/<tipo>")
def detalle(tipo):
    fecha = request.args.get("fecha")
    if tipo not in ("prestamos","abonos"):
        return jsonify([])
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(f"""SELECT cl.nombre, {tipo}.monto, {tipo}.id
                  FROM {tipo}
                  JOIN clientes cl ON cl.id = {tipo}.cliente_id
                  WHERE date({tipo}.fecha)=?""",(fecha,))
    data = [{"nombre":n,"monto":m,"id":i} for n,m,i in c.fetchall()]
    conn.close()
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
