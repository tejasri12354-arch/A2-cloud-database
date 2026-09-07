from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from database import (
    get_all_users, update_user, delete_user, 
    get_all_fees, create_fee, update_fee, delete_fee, get_fee_by_id,
    get_all_complaints, update_complaint,
    get_all_payments, get_all_audit_logs,
    create_secret, get_all_secrets, create_audit_log
)

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'administrator':
            flash('Access denied. Administrator privileges required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    users = get_all_users()
    complaints = get_all_complaints()
    payments = get_all_payments()
    
    stats = {
        'total_users': len(users),
        'pending_complaints': len([c for c in complaints if c.get('status') == 'Pending']),
        'total_payments': len(payments),
        'total_revenue': sum(p.get('amount', 0) for p in payments)
    }
    return render_template('admin/dashboard.html', stats=stats)


@admin_bp.route('/users')
@login_required
@admin_required
def user_management():
    users = get_all_users()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<user_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    role = request.form.get('role')
    if role in ['administrator', 'dbmanager', 'user']:
        update_user(user_id, {'role': role})
        create_audit_log(current_user.id, current_user.username, 'User Update', f'Updated user {user_id} role to {role}')
        flash('User updated successfully.', 'success')
    return redirect(url_for('admin.user_management'))


@admin_bp.route('/users/<user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user_route(user_id):
    if user_id != current_user.id:
        delete_user(user_id)
        create_audit_log(current_user.id, current_user.username, 'User Delete', f'Deleted user {user_id}')
        flash('User deleted successfully.', 'success')
    else:
        flash('Cannot delete your own account.', 'error')
    return redirect(url_for('admin.user_management'))


@admin_bp.route('/fees')
@login_required
@admin_required
def fee_configuration():
    fees = get_all_fees()
    return render_template('admin/fees.html', fees=fees)


@admin_bp.route('/fees/create', methods=['POST'])
@login_required
@admin_required
def create_fee_route():
    name = request.form.get('name', '').strip()
    amount = float(request.form.get('amount', 0))
    description = request.form.get('description', '').strip()
    due_date = request.form.get('due_date', '')
    
    if name and amount > 0:
        create_fee(name, amount, description, due_date, current_user.username)
        create_audit_log(current_user.id, current_user.username, 'Fee Created', f'Created fee: {name}')
        flash('Fee created successfully.', 'success')
    else:
        flash('Please provide valid fee details.', 'error')
    return redirect(url_for('admin.fee_configuration'))


@admin_bp.route('/fees/<fee_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_fee(fee_id):
    name = request.form.get('name', '').strip()
    amount = float(request.form.get('amount', 0))
    description = request.form.get('description', '').strip()
    due_date = request.form.get('due_date', '')
    
    if name and amount > 0:
        update_fee(fee_id, {
            'name': name,
            'amount': amount,
            'description': description,
            'due_date': due_date
        })
        create_audit_log(current_user.id, current_user.username, 'Fee Updated', f'Updated fee: {name}')
        flash('Fee updated successfully.', 'success')
    return redirect(url_for('admin.fee_configuration'))


@admin_bp.route('/fees/<fee_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_fee_route(fee_id):
    delete_fee(fee_id)
    create_audit_log(current_user.id, current_user.username, 'Fee Deleted', f'Deleted fee {fee_id}')
    flash('Fee deleted successfully.', 'success')
    return redirect(url_for('admin.fee_configuration'))


@admin_bp.route('/complaints')
@login_required
@admin_required
def complaint_review():
    complaints = get_all_complaints()
    return render_template('admin/complaints.html', complaints=complaints)


@admin_bp.route('/complaints/<complaint_id>/update', methods=['POST'])
@login_required
@admin_required
def update_complaint_route(complaint_id):
    status = request.form.get('status')
    response = request.form.get('response', '').strip()
    
    if status in ['Pending', 'In Review', 'Resolved']:
        update_complaint(complaint_id, {
            'status': status,
            'admin_response': response
        })
        create_audit_log(current_user.id, current_user.username, 'Complaint Updated', f'Updated complaint {complaint_id} status to {status}')
        flash('Complaint updated successfully.', 'success')
    return redirect(url_for('admin.complaint_review'))


@admin_bp.route('/reports')
@login_required
@admin_required
def system_reports():
    users = get_all_users()
    payments = get_all_payments()
    complaints = get_all_complaints()
    
    stats = {
        'users_by_role': {
            'administrator': len([u for u in users if u.role == 'administrator']),
            'dbmanager': len([u for u in users if u.role == 'dbmanager']),
            'user': len([u for u in users if u.role == 'user'])
        },
        'complaints_by_status': {
            'Pending': len([c for c in complaints if c.get('status') == 'Pending']),
            'In Review': len([c for c in complaints if c.get('status') == 'In Review']),
            'Resolved': len([c for c in complaints if c.get('status') == 'Resolved'])
        },
        'total_revenue': sum(p.get('amount', 0) for p in payments),
        'total_payments': len(payments)
    }
    return render_template('admin/reports.html', stats=stats)


@admin_bp.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    logs = get_all_audit_logs()
    logs = sorted(logs, key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('admin/audit_logs.html', logs=logs)


@admin_bp.route('/secrets')
@login_required
@admin_required
def secrets():
    all_secrets = get_all_secrets()
    return render_template('admin/secrets.html', secrets=all_secrets)


@admin_bp.route('/secrets/share', methods=['POST'])
@login_required
@admin_required
def share_secret():
    recipient_role = request.form.get('recipient_role')
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    
    if recipient_role and title and content:
        create_secret(
            current_user.id,
            current_user.username,
            current_user.role,
            recipient_role,
            title,
            content
        )
        create_audit_log(current_user.id, current_user.username, 'Secret Shared', f'Shared secret to {recipient_role}')
        flash('Secret shared successfully.', 'success')
    else:
        flash('Please fill in all fields.', 'error')
    return redirect(url_for('admin.secrets'))
