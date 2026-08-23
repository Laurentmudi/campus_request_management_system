import csv
import io
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Request as ServiceRequest

main = Blueprint('main', __name__)

REQUEST_CATEGORIES = ['Venue Booking', 'School Bus', 'Equipment Maintenance', 'Electrical Issue', 'Other']
STATUS_OPTIONS = ['Pending', 'Assigned', 'In Progress', 'Resolved']


@main.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))
    return render_template('home.html')


@main.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'student')

        if not full_name or not email or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('main.register'))

        if role not in ('student', 'staff'):
            role = 'student'

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('main.register'))

        user = User(full_name=full_name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html')


@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return redirect(url_for('main.login'))

        login_user(user)

        if user.role == 'admin':
            return redirect(url_for('main.admin_dashboard'))
        return redirect(url_for('main.dashboard'))

    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.login'))


@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('main.admin_dashboard'))

    my_requests = ServiceRequest.query.filter_by(user_id=current_user.id) \
        .order_by(ServiceRequest.date_created.desc()).all()
    return render_template('student_dashboard.html', requests=my_requests)


@main.route('/request/new', methods=['GET', 'POST'])
@login_required
def new_request():
    if current_user.role == 'admin':
        flash('Admins do not submit requests.', 'error')
        return redirect(url_for('main.admin_dashboard'))

    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()

        if not category or not description:
            flash('Category and description are required.', 'error')
            return redirect(url_for('main.new_request'))

        new_req = ServiceRequest(
            user_id=current_user.id,
            category=category,
            description=description,
            location=location
        )
        db.session.add(new_req)
        db.session.commit()

        flash('Request submitted successfully.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('new_request.html', categories=REQUEST_CATEGORIES)


@main.route('/request/<int:req_id>/delete', methods=['POST'])
@login_required
def delete_request(req_id):
    req = ServiceRequest.query.get_or_404(req_id)

    if req.user_id != current_user.id:
        flash('You can only delete your own requests.', 'error')
        return redirect(url_for('main.dashboard'))

    if req.status != 'Pending':
        flash('This request is already being handled and can no longer be deleted.', 'error')
        return redirect(url_for('main.dashboard'))

    db.session.delete(req)
    db.session.commit()

    flash(f'Request #{req_id} deleted.', 'success')
    return redirect(url_for('main.dashboard'))


@main.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('You are not authorized to view that page.', 'error')
        return redirect(url_for('main.dashboard'))

    all_requests = ServiceRequest.query.order_by(ServiceRequest.date_created.desc()).all()
    return render_template('admin_dashboard.html', requests=all_requests, statuses=STATUS_OPTIONS)


@main.route('/admin/request/<int:req_id>/update', methods=['POST'])
@login_required
def update_request(req_id):
    if current_user.role != 'admin':
        flash('You are not authorized to do that.', 'error')
        return redirect(url_for('main.dashboard'))

    req = ServiceRequest.query.get_or_404(req_id)
    req.status = request.form.get('status', req.status)
    req.assigned_to = request.form.get('assigned_to', req.assigned_to)
    db.session.commit()

    flash(f'Request #{req.id} updated.', 'success')
    return redirect(url_for('main.admin_dashboard'))


@main.route('/admin/requests/export')
@login_required
def export_requests():
    if current_user.role != 'admin':
        flash('You are not authorized to do that.', 'error')
        return redirect(url_for('main.dashboard'))

    all_requests = ServiceRequest.query.order_by(ServiceRequest.date_created.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Requested By', 'Role', 'Category', 'Description',
                      'Location', 'Status', 'Assigned To', 'Date Submitted'])

    for r in all_requests:
        writer.writerow([
            r.id,
            r.requester.full_name,
            r.requester.role,
            r.category,
            r.description,
            r.location or '',
            r.status,
            r.assigned_to or '',
            r.date_created.strftime('%Y-%m-%d %H:%M')
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=crms_requests.csv'}
    )