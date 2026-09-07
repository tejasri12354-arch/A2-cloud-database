import os
import logging
from flask import Flask
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET","secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

from database import get_user_by_id

@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)

from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.dbmanager import dbmanager_bp
from routes.user import user_bp
from routes.main import main_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(dbmanager_bp, url_prefix='/dbmanager')
app.register_blueprint(user_bp, url_prefix='/user')
if __name__ == "__main__":
    app.run(debug=True)