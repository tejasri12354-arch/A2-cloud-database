from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'administrator':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'dbmanager':
            return redirect(url_for('dbmanager.dashboard'))
        else:
            return redirect(url_for('user.dashboard'))
    return render_template('index.html')
