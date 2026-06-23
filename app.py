from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from pytz import timezone
import random
import os
from functools import wraps


def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Por favor, inicia sesión primero.")
            return redirect(url_for('login_ruta')) # Esta ruta la crearemos luego
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'una_clave_muy_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///foro.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
# Lista de visitantes que ya tenías
visitantes = []

# Cámbialo por esto:
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False) # <--- Cambiamos 'author' por 'username'
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)

with app.app_context():
    db.create_all()
#    if not User.query.filter_by(username='Admin').first():
#        admin = User(username='Admin', password='password123')
#        db.session.add(admin)
#        db.session.commit()
# --- RUTA DE REGISTRO (SIN EL ESCUDO) ---
@app.route('/')
def login():
    return render_template("login.html")

# --- RUTA DEL FORO (CON EL ESCUDO) ---
@app.route('/foro')
@login_requerido
def index():
    mensajes = Message.query.order_by(Message.timestamp.asc()).all()
    return render_template("index.html", mensajes=mensajes)
    # Ordenamos por fecha descendente (lo último primero)
    return render_template("index.html", mensajes=mensajes)

@app.route('/login', methods=['GET', 'POST'])
def login_ruta():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            flash("¡Bienvenido de nuevo!")
            return redirect(url_for('index'))
        else:
            flash("Usuario o contraseña incorrectos.")
            
    return render_template("login.html")

@app.route('/enviar_mensaje', methods=['POST'])
@login_requerido # Protegemos la ruta para asegurarnos de que tenemos un usuario logueado
def enviar_mensaje():
    # Obtenemos el username del usuario logueado en lugar de usar sesiones manuales
    nombre_usuario = current_user.username
    
    # Lógica de la etiqueta Owner: 
    # Si el nombre de usuario es 'maximo' (ajusta si usas mayúsculas), se marca como Owner
    if nombre_usuario.lower() == 'maximo':
        nombre_usuario += " (Owner)"
        
    contenido = request.form.get('contenido')
    
    # --- Gestión de la hora ---
    arg_tz = timezone('America/Argentina/Buenos_Aires')
    hora_arg = datetime.now(arg_tz)
    
    # Creamos el objeto del mensaje usando 'username' (ajustado al modelo que cambiaremos)
    # IMPORTANTE: Asegúrate de que en tu clase Message la columna se llame 'username'
    nuevo_mensaje = Message(username=nombre_usuario, content=contenido, timestamp=hora_arg)
    
    db.session.add(nuevo_mensaje)
    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/limpiar-foro', methods=['POST'])
@login_requerido
def limpiar_foro():
    codigo = request.form.get('codigo')
    
    # Verificación
    if codigo == "zero" and session.get('es_owner'):
        db.session.query(Message).delete()
        db.session.commit()
        # 2. Usamos 'flash' para que el mensaje aparezca dentro de tu diseño
        flash("¡Foro limpiado con éxito!") 
    else:
        # 3. También usamos 'flash' para el error
        flash("Acceso denegado. Código incorrecto o falta de permisos.")
        
    # 4. Redirigimos de vuelta al foro para que el usuario nunca vea una página en blanco
    return redirect(url_for('index'))

@app.route('/resgistrar', methods=['POST'])
def registrar():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username and password:
        usuario_existente = User.query.filter_by(username=username).first()
        if not usuario_existente:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            nuevo_usuario = User(username=username, password_hash=hashed_pw)
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash("Usuario registrado correctamente.")
        else:
            flash("El nombre de usuario ya existe.")
    # --- Fin del código nuevo ---
    session.permanent = True  # Para que la sesión dure 30 días
    
    # Capturamos todos los datos del formulario
    nombre = request.form.get('nombre')
    apellido = request.form.get('apellido')
    nacionalidad = request.form.get('nacionalidad')
    ciudad = request.form.get('ciudad')
    signo = request.form.get('signo')
    genero = request.form.get('genero')
    
    # Guardamos todo en la sesión para que "recuerde" quién eres
    session['nombre'] = nombre
    session['apellido'] = apellido
    session['nacionalidad'] = nacionalidad
    session['ciudad'] = ciudad
    session['genero'] = genero
    session['signo'] = signo
    # Lógica del Owner (Cambia 'tu_nombre' y 'tu_apellido' por los tuyos reales)
    if nombre.lower() == 'maximo' and apellido.lower() == 'brest':
        session['es_owner'] = True
    else:
        session['es_owner'] = False
    
    # Guardamos en la lista de visitantes
    visitantes.append({
        'nombre': nombre, 
        'apellido': apellido, 
        'nacionalidad': nacionalidad, 
        'ciudad': ciudad
    })
    
    # Lógica de Bienvenida
    bienvenida = "Bienvenido" if genero == "hombre" else "Bienvenida"
    
    if nacionalidad.lower().strip() == "argentina":
        flash(f"¡{bienvenida} {nombre}! Qué orgullo tener a alguien de mi país.")
    else:
        flash(f"¡{bienvenida} {nombre}! Qué lindo que nos visites desde {nacionalidad}.")
        
    return redirect(url_for('index'))

# --- Nueva ruta para ver el perfil ---
@app.route('/mi-cuenta')
@login_requerido
def mi_cuenta():
    return render_template("perfil.html")

@app.route('/juego', methods=['GET', 'POST'])
@login_requerido  # <--- Agrega esto también
def juego():
    limites = {'facil': 5, 'normal': 10, 'dificil': 15}
    if 'numero_secreto' not in session:
        session['dificultad'] = 'facil'
        session['rango'] = 10
        session['numero_secreto'] = random.randint(1, 10)
        session['intentos'] = 0
    
    limite_actual = limites.get(session.get('dificultad', 'facil'), 5)
    
    if request.method == 'POST':
        if 'dificultad' in request.form:
            dificultad = request.form.get('dificultad')
            session['dificultad'] = dificultad
            rango = {'facil': 10, 'normal': 20, 'dificil': 50}.get(dificultad, 10)
            session['rango'] = rango
            session['numero_secreto'] = random.randint(1, rango)
            session['intentos'] = 0
            flash(f"Dificultad cambiada a {dificultad}.")
        elif 'intento' in request.form:
            intentos_str = request.form.get('intento')
            if intentos_str and intentos_str.isdigit():
                session['intentos'] += 1
                intento = int(intentos_str)
                secret = session.get('numero_secreto')
                if intento == secret:
                    flash(f"¡GANASTE! Era el {secret}")
                    session['intentos'] = 0
                    session['numero_secreto'] = random.randint(1, session.get('rango', 10))
                elif session['intentos'] >= limite_actual:
                    flash(f"¡Perdiste! El número era {secret}")
                    session['intentos'] = 0
                    session['numero_secreto'] = random.randint(1, session.get('rango', 10))
                else:
                    pista = "¡Es más alto!" if intento < secret else "¡Es más bajo!"
                    flash(f"{pista} (Intento {session['intentos']}/{limite_actual})")
    
    return render_template("juego.html", 
                           rango=session.get('rango', 10), 
                           intentos=session.get('intentos', 0), 
                           limite=limite_actual)
@app.route('/visitantes')
def ver_visitantes():
    # Esto busca en tu lista 'visitantes' y la muestra
    return render_template("visitantes.html", lista=visitantes)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)# Comentario de prueba para forzar cambio