import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from database import (
    get_all_fees, get_fee_by_id, create_payment, get_payments_by_user,
    create_complaint, get_complaints_by_user,
    get_files_by_owner, create_file_record, get_file_by_id, get_all_files,
    create_secret, get_secrets_for_role, get_all_secrets,
    create_audit_log, get_user_keys, store_user_keys
)
from encryption import encrypt_file_hybrid, decrypt_file_hybrid, generate_rsa_keypair

user_bp = Blueprint('user', __name__)


def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'user':
            flash('Access denied. User privileges required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@user_bp.route('/dashboard')
@login_required
@user_required
def dashboard():
    payments = get_payments_by_user(current_user.id)
    complaints = get_complaints_by_user(current_user.id)
    files = get_files_by_owner(current_user.id)
    
    stats = {
        'total_payments': len(payments),
        'total_spent': sum(p.get('amount', 0) for p in payments),
        'active_complaints': len([c for c in complaints if c.get('status') != 'Resolved']),
        'total_files': len(files)
    }
    return render_template('user/dashboard.html', stats=stats)


@user_bp.route('/fees')
@login_required
@user_required
def fee_payment():
    fees = get_all_fees()
    payments = get_payments_by_user(current_user.id)

    # Find fees already paid by this user
    paid_fee_ids = {
        str(payment.get('fee_id'))
        for payment in payments
        if payment.get('status') == 'Completed'
    }

    # Remove already-paid fees from Available Fees
    fees = [
        fee for fee in fees
        if str(fee.doc_id) not in paid_fee_ids
    ]

    return render_template(
        'user/fees.html',
        fees=fees,
        payments=payments
    )


@user_bp.route('/fees/<fee_id>/pay', methods=['POST'])
@login_required
@user_required
def pay_fee(fee_id):
    fee = get_fee_by_id(fee_id)
    if fee:
        create_payment(
            current_user.id,
            current_user.username,
            fee_id,
            fee.get('name'),
            fee.get('amount')
        )
        create_audit_log(current_user.id, current_user.username, 'Payment Made', f'Paid fee: {fee.get("name")}')
        flash('Payment successful!', 'success')
    else:
        flash('Fee not found.', 'error')
    return redirect(url_for('user.fee_payment'))


@user_bp.route('/complaints')
@login_required
@user_required
def complaints():
    complaints = get_complaints_by_user(current_user.id)
    return render_template('user/complaints.html', complaints=complaints)


@user_bp.route('/complaints/submit', methods=['POST'])
@login_required
@user_required
def submit_complaint():
    category = request.form.get('category', '').strip()
    priority = request.form.get('priority', 'Medium')
    subject = request.form.get('subject', '').strip()
    description = request.form.get('description', '').strip()
    
    if category and subject and description:
        create_complaint(
            current_user.id,
            current_user.username,
            category,
            priority,
            subject,
            description
        )
        create_audit_log(current_user.id, current_user.username, 'Complaint Submitted', f'Submitted complaint: {subject}')
        flash('Complaint submitted successfully.', 'success')
    else:
        flash('Please fill in all required fields.', 'error')
    
    return redirect(url_for('user.complaints'))


@user_bp.route('/upload')
@login_required
@user_required
def file_upload():
    files = get_files_by_owner(current_user.id)
    return render_template('user/upload.html', files=files)


@user_bp.route('/upload/file', methods=['POST'])
@login_required
@user_required
def upload_file():
    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('user.file_upload'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('user.file_upload'))
    
    if file:
        original_filename = secure_filename(file.filename)
        file_data = file.read()
        file_size = len(file_data)
        
        keys = get_user_keys(current_user.id)
        if not keys:
            public_key, private_key = generate_rsa_keypair()
            store_user_keys(current_user.id, public_key, private_key)
            keys = {'public_key': public_key, 'private_key': private_key}
        
        encrypted_data = encrypt_file_hybrid(file_data, keys['public_key'])
        filename = f"user_{current_user.id}_{original_filename}"
        filepath = os.path.join('uploads/encrypted', filename)
        
        with open(filepath, 'wb') as f:
            f.write(encrypted_data)
        
        create_file_record(filename, original_filename, current_user.id, 'user', True, file_size)
        create_audit_log(current_user.id, current_user.username, 'File Encrypted', f'Encrypted and uploaded: {original_filename}')
        
        flash('File encrypted and uploaded successfully.', 'success')
    
    return redirect(url_for('user.file_upload'))


@user_bp.route('/download')
@login_required
@user_required
def file_download():
    my_files = get_files_by_owner(current_user.id)
    all_files = get_all_files()
    shared_files = [f for f in all_files if f.get('owner_role') == 'dbmanager']
    return render_template('user/download.html', my_files=my_files, shared_files=shared_files)


@user_bp.route('/download/<file_id>/encrypted')
@login_required
@user_required
def download_encrypted(file_id):
    file_record = get_file_by_id(file_id)
    if not file_record:
        flash('File not found.', 'error')
        return redirect(url_for('user.file_download'))
    
    filename = file_record.get('filename')
    if file_record.get('encrypted'):
        filepath = os.path.join('uploads/encrypted', filename)
    else:
        filepath = os.path.join('uploads/decrypted', filename)
    
    if os.path.exists(filepath):
        create_audit_log(current_user.id, current_user.username, 'File Downloaded', f'Downloaded encrypted: {filename}')
        return send_file(filepath, as_attachment=True, download_name=f"encrypted_{file_record.get('original_filename')}")
    
    flash('File not found on server.', 'error')
    return redirect(url_for('user.file_download'))


@user_bp.route('/download/<file_id>/decrypted')
@login_required
@user_required
def download_decrypted(file_id):
    file_record = get_file_by_id(file_id)
    if not file_record:
        flash('File not found.', 'error')
        return redirect(url_for('user.file_download'))
    
    filename = file_record.get('filename')
    
    if file_record.get('encrypted'):
        filepath = os.path.join('uploads/encrypted', filename)
        
        if not os.path.exists(filepath):
            flash('File not found on server.', 'error')
            return redirect(url_for('user.file_download'))
        
        owner_id = file_record.get('owner_id')
        keys = get_user_keys(str(owner_id))
        
        if not keys:
            flash('Encryption keys not found. You may not have permission to decrypt this file.', 'error')
            return redirect(url_for('user.file_download'))
        
        with open(filepath, 'rb') as f:
            encrypted_data = f.read()
        
        try:
            decrypted_data = decrypt_file_hybrid(encrypted_data, keys['private_key'])
            
            temp_filepath = os.path.join('uploads/decrypted', f"temp_user_{file_record.get('original_filename')}")
            with open(temp_filepath, 'wb') as f:
                f.write(decrypted_data)
            
            create_audit_log(current_user.id, current_user.username, 'File Decrypted', f'Downloaded decrypted: {filename}')
            
            return send_file(temp_filepath, as_attachment=True, download_name=file_record.get('original_filename'))
        except Exception as e:
            flash(f'Decryption failed: {str(e)}', 'error')
            return redirect(url_for('user.file_download'))
    else:
        filepath = os.path.join('uploads/decrypted', filename)
        if os.path.exists(filepath):
            create_audit_log(current_user.id, current_user.username, 'File Downloaded', f'Downloaded: {filename}')
            return send_file(filepath, as_attachment=True, download_name=file_record.get('original_filename'))
    
    flash('File not found on server.', 'error')
    return redirect(url_for('user.file_download'))


@user_bp.route('/history')
@login_required
@user_required
def service_history():
    payments = get_payments_by_user(current_user.id)
    complaints = get_complaints_by_user(current_user.id)
    files = get_files_by_owner(current_user.id)
    
    history = []
    
    for p in payments:
        history.append({
            'type': 'Payment',
            'description': f"Paid {p.get('fee_name')}: ${p.get('amount')}",
            'date': p.get('created_at', ''),
            'status': p.get('status', 'Completed')
        })
    
    for c in complaints:
        history.append({
            'type': 'Complaint',
            'description': f"{c.get('subject')}",
            'date': c.get('created_at', ''),
            'status': c.get('status', 'Pending')
        })
    
    for f in files:
        history.append({
            'type': 'File',
            'description': f"Uploaded: {f.get('original_filename')}",
            'date': f.get('created_at', ''),
            'status': 'Encrypted' if f.get('encrypted') else 'Plain'
        })
    
    history = sorted(history, key=lambda x: x.get('date', ''), reverse=True)
    
    return render_template('user/history.html', history=history)


@user_bp.route('/secrets')
@login_required
@user_required
def secrets():
    my_secrets = get_secrets_for_role('user')
    all_secrets = get_all_secrets()
    return render_template('user/secrets.html', my_secrets=my_secrets, all_secrets=all_secrets)


@user_bp.route('/secrets/share', methods=['POST'])
@login_required
@user_required
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
    return redirect(url_for('user.secrets'))
