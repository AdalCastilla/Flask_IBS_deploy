from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import os

# Inicialización de extensiones
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    """Factory principal de la aplicación"""
    app = Flask(__name__)
    
    # Configuración Básica
    app.config.from_mapping(
        SECRET_KEY='Empresa_IBS',  
        SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(app.instance_path, 'tickets.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=100 * 1024 * 1024  # 100MB
    )
    
    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Configuración de Login
    login_manager.login_view = 'main.login'
    
    # Registrar Blueprints
    from .routes import main_bp
    app.register_blueprint(main_bp)
    
    return app