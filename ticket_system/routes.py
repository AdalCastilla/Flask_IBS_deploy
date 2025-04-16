from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import Usuario, Ticket
from . import db
from .utils import enviar_correo, enviar_notificaciones_ticket, secure_file_upload
from datetime import datetime
from sqlalchemy import text
import os
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
# Crear un Blueprint para las rutas
main_bp = Blueprint('main', __name__)

#Configuración de archivos
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
UPLOAD_FOLDER = 'static/uploads'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Ruta de inicio de sesión
@main_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            nombre_usuario = request.form.get('username')  # Mejor usar .get() para evitar KeyError
            contraseña = request.form.get('password')
            
            if not nombre_usuario or not contraseña:
                flash('Por favor ingrese usuario y contraseña', 'error')
                return redirect(url_for('main.login'))

            usuario = Usuario.query.filter_by(nombre_usuario=nombre_usuario).first()
            
            if not usuario:
                flash('Usuario no encontrado', 'error')
                return redirect(url_for('main.login'))
                
            if not check_password_hash(usuario.contraseña, contraseña):
                flash('Contraseña incorrecta', 'error')
                return redirect(url_for('main.login'))
                
            login_user(usuario)
            session['tipo_usuario'] = usuario.tipo_usuario
            flash(f'Bienvenido {usuario.nombre_usuario}!', 'success')
            
            # Redirección según tipo de usuario
            if usuario.tipo_usuario == 'cliente':
                return redirect(url_for('main.cliente'))
            elif usuario.tipo_usuario == 'tecnico':
                return redirect(url_for('main.tecnico'))
            elif usuario.tipo_usuario == 'admin':
                return redirect(url_for('main.admin'))
                
        except Exception as e:
            flash('Error interno al procesar la solicitud', 'error')
            # Opcional: registrar el error en logs
            print(f"Error en login: {str(e)}")
            return redirect(url_for('main.login'))
    
    return render_template('login.html')

# Ruta de cierre de sesión
@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('main.login'))

# Ruta del panel del cliente
@main_bp.route('/cliente', methods=['GET', 'POST'])
@login_required
def cliente():
    if current_user.tipo_usuario != 'cliente':
        flash('Acceso denegado', 'error')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        # Validación de campos obligatorios
        titulo = request.form.get('ticket-title', '').strip()
        descripcion = request.form.get('ticket-description', '').strip()
        
        if not titulo:
            flash('El título del ticket es obligatorio', 'error')
            return redirect(url_for('main.cliente'))
        if not descripcion:
            flash('La descripción no puede estar vacía', 'error')
            return redirect(url_for('main.cliente'))

        # Procesar archivo adjunto
        archivo_nombre, archivo_ruta = secure_file_upload(request.files.get('archivo'))
        if request.files.get('archivo') and not archivo_nombre:
            flash('Tipo de archivo no permitido o error al subir', 'error')
            return redirect(url_for('main.cliente'))

        try:
            # Crear ticket
            nuevo_ticket = Ticket(
                titulo=titulo,
                descripcion=descripcion,
                cliente_id=current_user.id,
                archivo_nombre=archivo_nombre,
                archivo_ruta=archivo_ruta
            )
            db.session.add(nuevo_ticket)
            db.session.commit()

            enviar_notificaciones_ticket(nuevo_ticket, current_user)
            flash('Ticket creado exitosamente', 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creando ticket: {str(e)}")
            flash('Error al crear el ticket', 'error')

        return redirect(url_for('main.cliente'))

    # GET request
    tickets = Ticket.query.filter_by(cliente_id=current_user.id).all()
    return render_template('cliente.html', tickets=tickets)
# Ruta del panel del técnico
@main_bp.route('/tecnico')
@login_required
def tecnico():
    if current_user.tipo_usuario != 'tecnico':
        flash('No tienes permiso para acceder a esta página', 'error')
        return redirect(url_for('main.login'))

    tickets = Ticket.query.filter_by(estado='pendiente').all()
    return render_template('tecnico.html', tickets=tickets)

# Ruta para responder un ticket (técnico)
@main_bp.route('/responder_ticket/<int:ticket_id>', methods=['POST'])
@login_required
def responder_ticket(ticket_id):
    if current_user.tipo_usuario != 'tecnico':
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('main.login'))

    respuesta = request.form['respuesta']
    archivo = request.files.get('archivo')
    archivo_nombre = None
    archivo_ruta = None
    
    if archivo and archivo.filename != '':
        if allowed_file(archivo.filename):
            filename = secure_filename(archivo.filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            archivo.save(filepath)
            archivo_nombre = filename
            archivo_ruta = filepath
        else:
            flash('Tipo de archivo no permitido', 'error')
            return redirect(url_for('main.tecnico'))

    ticket = Ticket.query.get(ticket_id)
    if ticket:
        ticket.estado = 'resuelto'
        ticket.tecnico_id = current_user.id
        db.session.commit()

        cliente = Usuario.query.get(ticket.cliente_id) #enviar correo al cliente
        enviar_correo(
            cliente.correo,
            f'Ticket Resuelto (#{ticket.id})',
            f"""Tu ticket ha sido resuelto por {current_user.nombre_usuario}:
            Título: {ticket.titulo}
            Solución: {respuesta}""",
            archivo_path=archivo_ruta
        )

        admin = Usuario.query.filter_by(tipo_usuario='admin').first()#Enviar correo al administrador
        if admin:
            enviar_correo(
                admin.correo,
                f'Ticket Resuelto (#{ticket.id})',
                f"""El técnico {current_user.nombre_usuario} ha resuelto el ticket:
                Cliente: {ticket.cliente.nombre_usuario}
                Título: {ticket.titulo}
                Descripción original: {ticket.descripcion}
                Solución: {respuesta}
                Tiempo de resolución: {(datetime.utcnow() - ticket.fecha_creacion)}""",
                archivo_path=archivo_ruta
            )

        flash('Ticket marcado como resuelto y notificación enviada', 'success')
    return redirect(url_for('main.tecnico'))

# Ruta del panel del administrador
@main_bp.route('/admin')
@login_required
def admin():
    if current_user.tipo_usuario != 'admin':
        flash('No tienes permiso para acceder a esta página', 'error')
        return redirect(url_for('main.login'))

    usuarios = Usuario.query.all()
    tickets = Ticket.query.order_by(Ticket.fecha_creacion.desc()).all()  # Todos los tickets ordenados por fecha
    return render_template('admin.html', usuarios=usuarios, tickets=tickets)

# Ruta para crear un usuario (administrador)
@main_bp.route('/crear_usuario', methods=['POST'])
@login_required
def crear_usuario():
    if current_user.tipo_usuario != 'admin':
        flash('No tienes permiso para realizar esta acción', 'error')
        return redirect(url_for('main.login'))

    try:
        nombre_usuario = request.form['nombre_usuario']
        correo = request.form['correo'].strip().lower()  # Normaliza el correo
        contraseña = request.form['contraseña']
        tipo_usuario = request.form['tipo_usuario']

        # Validación 1: Nombre de usuario único
        if Usuario.query.filter_by(nombre_usuario=nombre_usuario).first():
            flash('El nombre de usuario ya existe', 'error')
            return redirect(url_for('main.admin'))

        # Validación 2: Correo electrónico único
        if Usuario.query.filter_by(correo=correo).first():
            flash('El correo electrónico ya está registrado', 'error')
            return redirect(url_for('main.admin'))


        # Creación del usuario
        nuevo_usuario = Usuario(
            nombre_usuario=nombre_usuario,
            correo=correo,
            tipo_usuario=tipo_usuario
        )
        nuevo_usuario.set_password(contraseña)
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        flash('Usuario creado exitosamente', 'success')
        return redirect(url_for('main.admin'))

    except IntegrityError as e:
        db.session.rollback()
        if 'usuario.correo' in str(e):
            flash('El correo electrónico ya está registrado', 'error')
        elif 'usuario.nombre_usuario' in str(e):
            flash('El nombre de usuario ya existe', 'error')
        else:
            flash('Error de integridad en la base de datos', 'error')
        return redirect(url_for('main.admin'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error al crear usuario: {str(e)}')
        flash('Error inesperado al crear el usuario', 'error')
        return redirect(url_for('main.admin'))

# Ruta para eliminar un usuario (administrador)
@main_bp.route('/eliminar_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def eliminar_usuario(usuario_id):
    if current_user.tipo_usuario != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('main.login'))

    try:
        # Configuración automática para SQLite
        if 'sqlite' in db.engine.url.drivername:
            db.session.execute(text('PRAGMA foreign_keys = ON'))
        
        usuario = Usuario.query.get_or_404(usuario_id)
        
        # Verificación para último admin
        if usuario.tipo_usuario == 'admin' and \
           Usuario.query.filter(Usuario.tipo_usuario == 'admin', 
                               Usuario.id != usuario.id).count() == 0:
            flash('Debe haber al menos un administrador', 'error')
            return redirect(url_for('main.admin'))

        # Eliminación con manejo explícito de relaciones
        if usuario.tickets_creados:
            for ticket in usuario.tickets_creados:
                db.session.delete(ticket)
        
        db.session.delete(usuario)
        db.session.commit()
        
        flash('Usuario y sus tickets asociados eliminados', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
        current_app.logger.exception(f"Error eliminando usuario {usuario_id}")
    
    return redirect(url_for('main.admin'))

@main_bp.route('/eliminar_ticket/<int:ticket_id>', methods=['POST'])
@login_required
def eliminar_ticket(ticket_id):
    if current_user.tipo_usuario != 'admin':  # Solo admin puede eliminar
        flash('No tienes permisos para esta acción', 'error')
        return redirect(url_for('main.admin'))

    ticket = Ticket.query.get_or_404(ticket_id)
    
    try:
        # Eliminar archivos adjuntos si existen
        if ticket.archivo_ruta and os.path.exists(ticket.archivo_ruta):
            os.remove(ticket.archivo_ruta)
        
        db.session.delete(ticket)
        db.session.commit()
        flash('Ticket eliminado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar ticket: {str(e)}', 'error')
        current_app.logger.error(f"Error eliminando ticket {ticket_id}: {str(e)}")
    
    return redirect(url_for('main.admin'))