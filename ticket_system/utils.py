import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from flask import current_app
from .models import Usuario
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
UPLOAD_FOLDER = 'static/uploads'

def enviar_correo(destinatario, asunto, mensaje, archivo_path=None):
    """
    Envía un correo electrónico utilizando SMTP.

    Parámetros:
        destinatario (str): Correo electrónico del destinatario.
        asunto (str): Asunto del correo.
        mensaje (str): Cuerpo del correo.
        archivo_path (str, opcional): Ruta del archivo a adjuntar

    Retorna:
        bool: True si el correo se envió correctamente, False en caso contrario.
    """
    try:
        # Configuración del servidor SMTP
        smtp_server = current_app.config.get('SMTP_SERVER')
        smtp_port = current_app.config.get('SMTP_PORT')
        email_address = current_app.config.get('EMAIL_ADDRESS')
        email_password = current_app.config.get('EMAIL_PASSWORD')

        # Crear el mensaje
        msg = MIMEMultipart()
        msg['From'] = email_address
        msg['To'] = destinatario
        msg['Subject'] = asunto

        # Agregar el cuerpo del mensaje
        msg.attach(MIMEText(mensaje, 'plain'))

        
        # Adjuntar archivo si existe
        if archivo_path and os.path.exists(archivo_path):
            with open(archivo_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                
                # Usar el nombre base del archivo para el adjunto
                filename = os.path.basename(archivo_path)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
                msg.attach(part)

        # Conectar al servidor SMTP y enviar el correo
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Habilitar cifrado TLS
            server.login(email_address, email_password)  # Iniciar sesión en el servidor
            server.send_message(msg)  # Enviar el correo

        current_app.logger.info(f"Correo enviado exitosamente a: {destinatario}")
        return True

    except smtplib.SMTPException as e:
        current_app.logger.error(f"Error SMTP al enviar a {destinatario}: {str(e)}")
    except IOError as e:
        current_app.logger.error(f"Error con archivo adjunto: {str(e)}")
    except Exception as e:
        current_app.logger.error(f"Error inesperado al enviar correo: {str(e)}")
    
    return False

def enviar_notificaciones_ticket(ticket, cliente):
    """Envía notificaciones por correo sobre un nuevo ticket"""
    cuerpo_base = f"""
    Ticket #{ticket.id}
    Título: {ticket.titulo}
    Cliente: {cliente.nombre_usuario}
    Descripción: {ticket.descripcion}
    Fecha: {ticket.fecha_creacion}
    """
    
    # Enviar al cliente
    enviar_correo(
        cliente.correo,
        f'Ticket Creado (#{ticket.id})',
        f"Has creado un nuevo ticket:\n{cuerpo_base}",
        archivo_path=ticket.archivo_ruta
    )
    
    # Enviar a técnicos
    tecnicos = Usuario.query.filter_by(tipo_usuario='tecnico').all()
    for tecnico in tecnicos:
        enviar_correo(
            tecnico.correo,
            f'Nuevo Ticket (#{ticket.id}) - {ticket.titulo}',
            f"Nuevo ticket asignado:\n{cuerpo_base}",
            archivo_path=ticket.archivo_ruta
        )
    
    # Enviar a admin
    admin = Usuario.query.filter_by(tipo_usuario='admin').first()
    if admin:
        enviar_correo(
            admin.correo,
            f'[Admin] Nuevo Ticket (#{ticket.id})',
            f"Resumen del ticket:\n{cuerpo_base}",
            archivo_path=ticket.archivo_ruta
        )

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def secure_file_upload(file):
    """Guarda un archivo subido de forma segura y devuelve (nombre_archivo, ruta_archivo)"""
    if file and file.filename and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            return filename, filepath
        except Exception as e:
            current_app.logger.error(f"Error subiendo archivo: {str(e)}")
            return None, None
    return None, None