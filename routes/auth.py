from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from database import create_user, get_user_by_username, get_user_by_email, create_audit_log, store_user_keys
from encryption import generate_rsa_keypair

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = 'user'
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        
        if not username or not email or not password:
            flash('Please fill in all required fields.', 'error')
            return render_template('auth/signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/signup.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth/signup.html')
        
        if get_user_by_username(username):
            flash('Username already exists.', 'error')
            return render_template('auth/signup.html')
        
        if get_user_by_email(email):
            flash('Email already registered.', 'error')
            return render_template('auth/signup.html')
        
        user_id = create_user(username, email, password, role, full_name, phone, address)
        
        public_key, private_key = generate_rsa_keypair()
        store_user_keys(str(user_id), public_key, private_key)
        
        create_audit_log(str(user_id), username, 'User Registration', f'New {role} account created')
        
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter username and password.', 'error')
            return render_template('auth/login.html')
        
        user = get_user_by_username(username)
        
        if user and user.check_password(password):
            login_user(user)
            create_audit_log(user.id, user.username, 'Login', f'{user.role} logged in')
            
            if user.role == 'administrator':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'dbmanager':
                return redirect(url_for('dbmanager.dashboard'))
            else:
                return redirect(url_for('user.dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    create_audit_log(current_user.id, current_user.username, 'Logout', f'{current_user.role} logged out')
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))
