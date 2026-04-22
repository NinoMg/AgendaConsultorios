from flask import Flask, render_template, request, redirect, flash, session
import psycopg2
import os
import urllib.parse
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE_URL = os.environ.get("DATABASE_URL")

# Credenciales del médico (se pueden mover a variables de entorno)
MEDICO_USUARIO = os.environ.get("MEDICO_USUARIO", "admin")
MEDICO_PASSWORD = os.environ.get("MEDICO_PASSWORD", "admin123")
MEDICO_WHATSAPP = os.environ.get("MEDICO_WHATSAPP", "5492604693013")
NOMBRE_CONSULTORIO = os.environ.get("NOMBRE_CONSULTORIO", "Consultorio Médico")


# 🔌 Conexión a PostgreSQL
def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')


# 🧱 Crear tabla si no existe
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
        c.execute("""
            ALTER TABLE turnos
            ADD CONSTRAINT unique_turno UNIQUE (fecha, hora)
        """)
    except:
        pass
    conn.commit()
    conn.close()


with app.app_context():
    init_db()


# 🔐 Decorador de login requerido
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('medico_logueado'):
            flash("Necesitás iniciar sesión para acceder al panel.", "warning")
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


# 🏠 Página principal (pacientes sacan turno)
@app.route('/')
def index():
    return render_template('index.html', nombre_consultorio=NOMBRE_CONSULTORIO)


# 📅 Agregar turno (lo hace el paciente)
@app.route('/agregar', methods=['POST'])
def agregar():
    nombre = request.form.get('nombre', '').strip()
    fecha = request.form.get('fecha', '').strip()
    hora = request.form.get('hora', '').strip()
    telefono = request.form.get('telefono', '').strip()
    motivo = request.form.get('motivo', '').strip()
    obra_social = request.form.get('obra_social', '').strip()

    if not nombre or not fecha or not hora or not telefono:
        flash("Completá todos los campos obligatorios.", 'warning')
        return redirect('/')

    if not telefono.isdigit():
        flash("El teléfono debe tener solo números.", 'warning')
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
            """INSERT INTO turnos (nombre, fecha, hora, telefono, motivo, obra_social)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (nombre, fecha, hora, telefono, motivo, obra_social)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        flash("Ese horario ya está ocupado. Por favor elegí otro.", 'danger')
        return redirect('/')

    conn.close()

    # 📲 Redirigir a WhatsApp para confirmar
    mensaje = f"Hola! Quiero confirmar mi turno:\n👤 Nombre: {nombre}\n📅 Fecha: {fecha}\n⏰ Hora: {hora}\n📱 Tel: {telefono}\n🏥 Motivo: {motivo or 'No especificado'}\n💊 Obra Social: {obra_social or 'Particular'}"
    mensaje_encoded = urllib.parse.quote(mensaje)
    url_whatsapp = f"https://wa.me/{MEDICO_WHATSAPP}?text={mensaje_encoded}"

    return redirect(url_whatsapp)


# 🔐 Login del médico
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        if usuario == MEDICO_USUARIO and password == MEDICO_PASSWORD:
            session['medico_logueado'] = True
            return redirect('/panel')
        else:
            flash("Usuario o contraseña incorrectos.", 'danger')
    return render_template('login.html', nombre_consultorio=NOMBRE_CONSULTORIO)


# 🚪 Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# 📋 Panel del médico
@app.route('/panel')
@login_required
def panel():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, nombre, fecha, hora, telefono, motivo, obra_social
        FROM turnos
        WHERE cancelado = FALSE
        ORDER BY fecha, hora
    """)
    turnos = c.fetchall()
    conn.close()
    return render_template('panel.html', turnos=turnos, nombre_consultorio=NOMBRE_CONSULTORIO)


# ❌ Cancelar turno (solo el médico)
@app.route('/cancelar/<int:id>')
@login_required
def cancelar(id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE turnos SET cancelado = TRUE WHERE id = %s", (id,))
    conn.commit()

    # Buscar el teléfono para notificar al paciente
    c.execute("SELECT nombre, telefono, fecha, hora FROM turnos WHERE id = %s", (id,))
    turno = c.fetchone()
    conn.close()

    if turno:
        nombre, telefono, fecha, hora = turno
        mensaje = f"Hola {nombre}, lamentablemente tu turno del {fecha} a las {hora} fue cancelado. Comunicate con el consultorio para reprogramarlo."
        mensaje_encoded = urllib.parse.quote(mensaje)
        flash(f"Turno de {nombre} cancelado. <a href='https://wa.me/549{telefono}?text={mensaje_encoded}' target='_blank'>Notificar por WhatsApp</a>", 'info')

    return redirect('/panel')


# 🗑️ Eliminar turno permanentemente
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
