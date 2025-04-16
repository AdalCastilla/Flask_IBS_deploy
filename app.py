import os
import sys
from pathlib import Path
from flask_login import LoginManager
from ticket_system import create_app
from ticket_system.models import Usuario, db

# Configura rutas compatibles con ejecutables
def get_app_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS  # Ruta temporal al descomprimir el ejecutable
    return os.path.dirname(os.path.abspath(__file__))

# Ruta persistente para la base de datos (fuera del ejecutable)
def get_db_path():
    if getattr(sys, 'frozen', False):
        # En producción: usa AppData/Local (Windows) o ~/.local/share (Linux/Mac)
        from appdirs import user_data_dir
        app_data = user_data_dir("TicketSystem", "IBS")
        os.makedirs(app_data, exist_ok=True)
        return os.path.join(app_data, 'tickets.db')
    # En desarrollo: usa la carpeta instance
    return os.path.join(get_app_path(), 'instance', 'tickets.db')

app = create_app()

# Configuración de la base de datos
db_path = get_db_path()
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configura Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main.login'

@login_manager.user_loader
def load_user(user_id):
    with app.app_context():
        return Usuario.query.get(int(user_id))
# Configuración del servidor SMTP
app.config.update(
    
    SMTP_SERVER='198.59.144.159',  
    SMTP_PORT=587,                        
    EMAIL_ADDRESS='marketing@informatikbs.mx',
    EMAIL_PASSWORD='iQfQa?*+)Ud6',       
    DEFAULT_SENDER='marketing@informatikbs.mx',
    SMTP_USE_TLS=True,

    # Configuración de Archivos
    UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads'),
    MAX_CONTENT_LENGTH= 100 * 1024 * 1024,  # 100MB
    ALLOWED_EXTENSIONS={'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
)

# Inicialización segura
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()

if __name__ == '__main__': 
    app.run(debug=True)