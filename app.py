from flask import Flask, render_template, request, redirect, flash, session, jsonify
import psycopg2
import os
import urllib.parse
from functools import wraps
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE_URL      = os.environ.get("DATABASE_URL")
MEDICO_USUARIO    = os.environ.get("MEDICO_USUARIO", "admin")
MEDICO_PASSWORD   = os.environ.get("MEDICO_PASSWORD", "admin123")
MEDICO_WHATSAPP   = os.environ.get("MEDICO_WHATSAPP", "5492604693013")
NOMBRE_CONSULTORIO = os.environ.get("NOMBRE_CONSULTORIO", "Consultorio Médico")

HORARIOS = [
    "08:00","08:30","09:00","09:30","10:00","10:30","11:00","11:30","12:00",
    "14:00","14:30","15:00","15:30","16:00","16:30","17:00","17:30","18:00"
]

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS turnos (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            telefono TEXT NOT NULL,
            motivo TEXT,
            obra_social TEXT,
            cancelado BOOLEAN DEFAULT FALSE
        )
    """)
    try:
        c.execute("ALTER TABLE turnos ADD CONSTRAINT unique_turno UNIQUE (fecha, hora)")
    except:
        pass
    conn.commit()
    conn.close()

with app.app_context():
    init_db()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('medico_logueado'):
            flash("Necesitás iniciar sesión para acceder al panel.", "warning")
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

# ── API: horarios disponibles por fecha ──────────────────────────────────
@app.route('/disponibilidad/<fecha>')
def disponibilidad(fecha):
    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Fecha inválida"}), 400

    if fecha_obj < date.today():
        return jsonify({"error": "Fecha pasada"}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT hora FROM turnos WHERE fecha = %s AND cancelado = FALSE",
        (fecha,)
    )
    ocupados = {row[0] for row in c.fetchall()}
    conn.close()

    ahora = datetime.now()
    resultado = []
    for h in HORARIOS:
        pasado = False
        if fecha_obj == date.today():
            hh, mm = map(int, h.split(":"))
            pasado = (hh * 60 + mm) <= (ahora.hour * 60 + ahora.minute)
        resultado.append({
            "hora": h,
            "disponible": h not in ocupados and not pasado
        })

    return jsonify(resultado)

# ── Página principal ─────────────────────────────────────────────────────
@app.route('/')
def index():
    # Disponibilidad próximos 14 días para el mini-calendario
    disponibilidad_dias = {}
    for i in range(14):
        dia = (date.today() + timedelta(days=i)).isoformat()
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT hora FROM turnos WHERE fecha = %s AND cancelado = FALSE", (dia,))
        ocupados = len(c.fetchall())
        conn.close()
        disponibilidad_dias[dia] = len(HORARIOS) - ocupados

    return render_template('index.html',
        nombre_consultorio=NOMBRE_CONSULTORIO,
        horarios=HORARIOS,
        disponibilidad=disponibilidad_dias,
        hoy=date.today().isoformat()
    )

# ── Agregar turno ────────────────────────────────────────────────────────
@app.route('/agregar', methods=['POST'])
def agregar():
    nombre     = request.form.get('nombre', '').strip()
    fecha      = request.form.get('fecha', '').strip()
    hora       = request.form.get('hora', '').strip()
    telefono   = request.form.get('telefono', '').strip()
    motivo     = request.form.get('motivo', '').strip()
    obra_social = request.form.get('obra_social', '').strip()

    if not nombre or not fecha or not hora or not telefono:
        flash("Completá todos los campos obligatorios.", 'warning')
        return redirect('/')

    if not telefono.isdigit():
        flash("El teléfono debe tener solo números.", 'warning')
        return redirect('/')

    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        flash("Fecha inválida.", 'warning')
        return redirect('/')

    if fecha_obj < date.today():
        flash("No podés reservar en una fecha pasada.", 'warning')
        return redirect('/')

    if hora not in HORARIOS:
        flash("Horario inválido.", 'warning')
        return redirect('/')

    if fecha_obj == date.today():
        hora_actual = datetime.now().strftime("%H:%M")
        if hora <= hora_actual:
            flash("Ese horario ya pasó para hoy.", 'warning')
            return redirect('/')

    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM turnos WHERE fecha = %s AND hora = %s AND cancelado = FALSE",
        (fecha, hora)
    )
    if c.fetchone():
        conn.close()
        flash("Ese horario ya está ocupado. Por favor elegí otro.", 'danger')
        return redirect('/')

    try:
        c.execute(
            "INSERT INTO turnos (nombre, fecha, hora, telefono, motivo, obra_social) VALUES (%s,%s,%s,%s,%s,%s)",
            (nombre, fecha, hora, telefono, motivo, obra_social)
        )
        conn.commit()
    except Exception:
        conn.close()
        flash("Ese horario ya está ocupado. Por favor elegí otro.", 'danger')
        return redirect('/')
    conn.close()

    mensaje = (
        f"Hola! Quiero confirmar mi turno en {NOMBRE_CONSULTORIO} 🏥\n\n"
        f"👤 Nombre: {nombre}\n"
        f"📅 Fecha: {fecha_obj.strftime('%d/%m/%Y')}\n"
        f"⏰ Hora: {hora}\n"
        f"📱 Tel: {telefono}\n"
        f"🏥 Motivo: {motivo or 'No especificado'}\n"
        f"💊 Obra Social: {obra_social or 'Particular'}\n\n"
        f"¡Muchas gracias!"
    )
    url_whatsapp = f"https://wa.me/{MEDICO_WHATSAPP}?text={urllib.parse.quote(mensaje)}"
    return redirect(url_whatsapp)

# ── Login / Logout ───────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario  = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        if usuario == MEDICO_USUARIO and password == MEDICO_PASSWORD:
            session['medico_logueado'] = True
            return redirect('/panel')
        flash("Usuario o contraseña incorrectos.", 'danger')
    return render_template('login.html', nombre_consultorio=NOMBRE_CONSULTORIO)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ── Panel del médico ─────────────────────────────────────────────────────
@app.route('/panel')
@login_required
def panel():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, nombre, fecha, hora, telefono, motivo, obra_social
        FROM turnos WHERE cancelado = FALSE
        ORDER BY fecha, hora
    """)
    turnos = c.fetchall()
    conn.close()
    return render_template('panel.html', turnos=turnos, nombre_consultorio=NOMBRE_CONSULTORIO)

# ── Cancelar / Eliminar ──────────────────────────────────────────────────
@app.route('/cancelar/<int:id>')
@login_required
def cancelar(id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE turnos SET cancelado = TRUE WHERE id = %s", (id,))
    conn.commit()
    c.execute("SELECT nombre, telefono, fecha, hora FROM turnos WHERE id = %s", (id,))
    turno = c.fetchone()
    conn.close()
    if turno:
        nombre, telefono, fecha, hora = turno
        mensaje = f"Hola {nombre}, lamentablemente tu turno del {fecha} a las {hora} fue cancelado. Comunicate con el consultorio para reprogramarlo."
        url = f"https://wa.me/549{telefono}?text={urllib.parse.quote(mensaje)}"
        flash(f"Turno cancelado. <a href='{url}' target='_blank'>Notificar por WhatsApp</a>", 'info')
    return redirect('/panel')

@app.route('/eliminar/<int:id>')
@login_required
def eliminar(id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM turnos WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    flash("Turno eliminado.", 'success')
    return redirect('/panel')

if __name__ == '__main__':
    app.run(debug=True)
