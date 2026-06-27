from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, login_required, logout_user
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

# --- CONFIGURACIÓN DE BASE DE DATOS MEJORADA ---
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Ajuste necesario para que SQLAlchemy entienda la URL de PostgreSQL de Render
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Si estamos en local, usamos SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///foro.db'
# --- FIN DE CONFIGURACIÓN ---

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
# Lista de visitantes
visitantes = []

# Cámbialo por esto:
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    ultimo_cambio_password = db.Column(db.DateTime, default=datetime.utcnow)
    # Asegúrate de que TODOS estos existan:
    nombre = db.Column(db.String(100))
    apellido = db.Column(db.String(100))
    ciudad = db.Column(db.String(100))
    nacionalidad = db.Column(db.String(100)) # <--- ESTE ES EL QUE FALTABA
    genero = db.Column(db.String(50))
    signo = db.Column(db.String(50))
    pregunta_seguridad = db.Column(db.String(150), nullable=True) # La pregunta (ej: ¿Nombre de tu mascota?)
    respuesta_seguridad = db.Column(db.String(150), nullable=True) # La respuesta encriptada

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False) # <--- Cambiamos 'author' por 'username'
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    es_editado = db.Column(db.Boolean, default=False)

from sqlalchemy import text

# ... (todo tu código anterior)

with app.app_context():
    db.drop_all()
    # BORRAMOS LA TABLA VIEJA PARA QUE SE CREE LA NUEVA CON TODAS LAS COLUMNAS
    db.create_all()
    print("Base de datos recreada con todos los campos.")
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
            
            # --- LÓGICA DE ROLES ---
            # Definimos si es Owner o Admin basándonos en el username
            if user.username == 'maximo':
                session['es_owner'] = True
                session['es_admin'] = True # El owner también es admin
            elif user.username == 'gabriel':
                session['es_owner'] = False
                session['es_admin'] = True
            else:
                session['es_owner'] = False
                session['es_admin'] = False
            # -----------------------
            
            flash("¡Bienvenido!")
            return redirect(url_for('index'))
        else:
            flash("Usuario o contraseña incorrectos.")
            
    return render_template("login.html")

@app.route('/enviar_mensaje', methods=['POST'])
@login_requerido
def enviar_mensaje():
    user_lower = current_user.username.lower().strip()
    # Usamos el username directamente
    nombre_para_mostrar = current_user.username 
    
    if user_lower == 'maximo':
        nombre_para_mostrar += " (Owner)"
    elif user_lower == 'gabriel':
        nombre_para_mostrar += " (Admin)"
        
    contenido = request.form.get('contenido')
    
    # Gestión de la hora
    arg_tz = timezone('America/Argentina/Buenos_Aires')
    hora_arg = datetime.now(arg_tz)
    
    # Guardamos en la base de datos
    nuevo_mensaje = Message(username=nombre_para_mostrar, content=contenido, timestamp=hora_arg)
    
    db.session.add(nuevo_mensaje)
    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/debug-usuario')
@login_required
def debug():
    return f"Username actual: '{current_user.username}' | Es admin: {session.get('es_admin')}"

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



@app.route('/registrar', methods=['POST'])
def registrar():
    username = request.form.get('username')
    password = request.form.get('password')
    pregunta = request.form.get('pregunta')
    respuesta = request.form.get('respuesta') # Capturamos la respuesta
    # Capturamos los otros campos
    nombre = request.form.get('nombre')
    apellido = request.form.get('apellido')
    nacionalidad = request.form.get('nacionalidad')
    ciudad = request.form.get('ciudad')
    signo = request.form.get('signo')
    genero = request.form.get('genero')
    if username and password:
        usuario_existente = User.query.filter_by(username=username).first()
        if not usuario_existente:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            nuevo_usuario = User(
                username=username, 
                password_hash=hashed_pw,
                nombre=nombre,
                apellido=apellido,
                ciudad=ciudad,
                nacionalidad=nacionalidad,
                genero=genero,
                signo=signo,
                pregunta_seguridad=pregunta,
                respuesta_seguridad=bcrypt.generate_password_hash(respuesta).decode('utf-8')
            )
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
    if nombre.lower() == 'maximo' and apellido.lower() == 'dippolito':
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

# Esta función es el "botón de pánico" que borra todo y te desconecta
@app.route('/logout')
def logout():
    session.clear()      # Borra la "lista del portero" (Admin, Owner, etc.)
    logout_user()        # Te saca del club
    flash("Has cerrado sesión.")
    return redirect(url_for('login_ruta'))

@app.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        # 1. Primero, verificamos el tiempo
        hace_7_dias = datetime.utcnow() - timedelta(days=7)
        
        if current_user.ultimo_cambio_password and current_user.ultimo_cambio_password > hace_7_dias:
            flash("Debes esperar 7 días desde tu último cambio de contraseña.")
            return redirect(url_for('mi_cuenta'))

        # 2. Ahora, validamos las contraseñas
        nueva_pass = request.form.get('new_password')
        confirm_pass = request.form.get('confirm_password')

        if nueva_pass != confirm_pass:
            flash("Las contraseñas no coinciden.")
            return redirect(url_for('cambiar_password'))

        # 3. Si todo está OK, encriptamos y guardamos
        current_user.password = bcrypt.generate_password_hash(nueva_pass).decode('utf-8')
        current_user.ultimo_cambio_password = datetime.utcnow()
        db.session.commit()
        
        flash("Contraseña actualizada con éxito.")
        return redirect(url_for('mi_cuenta'))
        
    return render_template("cambiar_password.html")

@app.route('/recuperar-password', methods=['GET', 'POST'])
def recuperar_password():
    if request.method == 'POST':
        # Paso 1: Buscar usuario
        if 'buscar_usuario' in request.form:
            username = request.form.get('username')
            user = User.query.filter_by(username=username).first()
            if user:
                # Guardamos el usuario en la sesión para usarlo después
                session['recuperar_user_id'] = user.id
                return render_template('recuperar_password.html', pregunta=user.pregunta_seguridad, username=username)
            else:
                flash("Usuario no encontrado.")
        
        # Paso 2: Verificar respuesta y cambiar contraseña
        elif 'verificar_y_cambiar' in request.form:
            user_id = session.get('recuperar_user_id')
            user = User.query.get(user_id)
            respuesta_ingresada = request.form.get('respuesta')
            
            # Verificamos la respuesta (usando check_password_hash porque está encriptada)
            if user and bcrypt.check_password_hash(user.respuesta_seguridad, respuesta_ingresada):
                nueva_pass = request.form.get('new_password')
                user.password_hash = bcrypt.generate_password_hash(nueva_pass).decode('utf-8')
                db.session.commit()
                flash("Contraseña restablecida con éxito.")
                return redirect(url_for('login_ruta')) # Asumiendo que tu ruta de login se llama así
            else:
                flash("Respuesta incorrecta.")
                
    return render_template('recuperar_password.html')

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

@app.route('/ver-usuarios')
def ver_usuarios():
    # Te lista todos los usuarios para ver si tienes duplicados
    lista = User.query.all()
    return "<br>".join([f"User: {u.username} | Nombre: {u.nombre}" for u in lista])



@app.route('/ver-sesion')
def ver_sesion():
    # Te dice qué sabe el servidor de tu sesión actual
    return f"Datos en sesión: {dict(session)}"
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)# Comentario de prueba para forzar cambio