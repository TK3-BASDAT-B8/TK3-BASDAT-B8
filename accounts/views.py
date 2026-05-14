import uuid

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import redirect, render

from core.auth import (
    authenticate_user,
    get_current_user,
    login_required,
    login_user,
    logout_user,
    refresh_login_user,
)
from core.db import db_error_message, execute_query, fetch_one


def login_view(request):
    if get_current_user(request):
        return redirect('accounts:dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate_user(username, password)
        if user:
            login_user(request, user)
            return redirect('accounts:dashboard')
        error = 'Username atau password salah.'
    return render(request, 'accounts/login.html', {'error': error})


def logout_view(request):
    logout_user(request)
    return redirect('accounts:login')


def register_view(request):
    return render(request, 'accounts/register.html')


def _role_id(role_name):
    row = fetch_one('SELECT role_id::text FROM ROLE WHERE role_name = %s', [role_name])
    if not row:
        raise ValueError(f'Role {role_name} belum tersedia di tabel ROLE.')
    return row['role_id']


def _validate_register(username, password, confirm, extra_required=None):
    if not username or not password or not confirm:
        return 'Username, password, dan konfirmasi password wajib diisi.'
    if password != confirm:
        return 'Password dan konfirmasi password tidak cocok.'
    for label, value in (extra_required or []):
        if not value:
            return f'{label} wajib diisi.'
    return None


def register_customer_view(request):
    error = None
    form = {}
    if request.method == 'POST':
        form = request.POST
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        error = _validate_register(username, password, confirm, [('Nama lengkap', full_name)])
        if not error:
            try:
                user_id = str(uuid.uuid4())
                customer_id = str(uuid.uuid4())
                with transaction.atomic():
                    execute_query(
                        'INSERT INTO USER_ACCOUNT (user_id, username, password) VALUES (%s, %s, %s)',
                        [user_id, username, password],
                    )
                    execute_query('INSERT INTO ACCOUNT_ROLE (role_id, user_id) VALUES (%s, %s)', [_role_id('customer'), user_id])
                    execute_query(
                        'INSERT INTO CUSTOMER (customer_id, full_name, phone_number, user_id) VALUES (%s, %s, %s, %s)',
                        [customer_id, full_name, phone_number, user_id],
                    )
                messages.success(request, 'Registrasi customer berhasil. Silakan login.')
                return redirect('accounts:login')
            except (DatabaseError, ValueError) as exc:
                error = db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc)
    return render(request, 'accounts/register_customer.html', {'error': error, 'form': form})


def register_organizer_view(request):
    error = None
    form = {}
    if request.method == 'POST':
        form = request.POST
        organizer_name = request.POST.get('organizer_name', '').strip()
        contact_email = request.POST.get('contact_email', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        error = _validate_register(
            username,
            password,
            confirm,
            [('Nama organizer', organizer_name), ('Email kontak', contact_email)],
        )
        if not error:
            try:
                user_id = str(uuid.uuid4())
                organizer_id = str(uuid.uuid4())
                with transaction.atomic():
                    execute_query(
                        'INSERT INTO USER_ACCOUNT (user_id, username, password) VALUES (%s, %s, %s)',
                        [user_id, username, password],
                    )
                    execute_query('INSERT INTO ACCOUNT_ROLE (role_id, user_id) VALUES (%s, %s)', [_role_id('organizer'), user_id])
                    execute_query(
                        'INSERT INTO ORGANIZER (organizer_id, organizer_name, contact_email, user_id) VALUES (%s, %s, %s, %s)',
                        [organizer_id, organizer_name, contact_email, user_id],
                    )
                messages.success(request, 'Registrasi organizer berhasil. Silakan login.')
                return redirect('accounts:login')
            except (DatabaseError, ValueError) as exc:
                error = db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc)
    return render(request, 'accounts/register_organizer.html', {'error': error, 'form': form})


def register_admin_view(request):
    error = None
    form = {}
    if request.method == 'POST':
        form = request.POST
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        error = _validate_register(username, password, confirm)
        if not error:
            try:
                user_id = str(uuid.uuid4())
                with transaction.atomic():
                    execute_query(
                        'INSERT INTO USER_ACCOUNT (user_id, username, password) VALUES (%s, %s, %s)',
                        [user_id, username, password],
                    )
                    execute_query('INSERT INTO ACCOUNT_ROLE (role_id, user_id) VALUES (%s, %s)', [_role_id('administrator'), user_id])
                messages.success(request, 'Registrasi admin berhasil. Silakan login.')
                return redirect('accounts:login')
            except (DatabaseError, ValueError) as exc:
                error = db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc)
    return render(request, 'accounts/register_admin.html', {'error': error, 'form': form})


@login_required
def dashboard_view(request):
    user = get_current_user(request)
    if user['role'] == 'administrator':
        return render(request, 'accounts/dashboard_admin.html', {'user': user})
    if user['role'] == 'organizer':
        return render(request, 'accounts/dashboard_organizer.html', {'user': user})
    return render(request, 'accounts/dashboard_customer.html', {'user': user})


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': get_current_user(request)})


@login_required
def profile_edit_view(request):
    user = get_current_user(request)
    if user['role'] == 'administrator':
        messages.info(request, 'Admin tidak memiliki data profil tambahan yang dapat diubah.')
        return redirect('accounts:profile')

    if request.method == 'POST':
        try:
            if user['role'] == 'customer':
                full_name = request.POST.get('full_name', '').strip()
                phone_number = request.POST.get('phone_number', '').strip()
                if not full_name:
                    raise ValueError('Nama lengkap wajib diisi.')
                execute_query(
                    'UPDATE CUSTOMER SET full_name=%s, phone_number=%s WHERE customer_id=%s',
                    [full_name, phone_number, user.get('customer_id')],
                )
            elif user['role'] == 'organizer':
                organizer_name = request.POST.get('organizer_name', '').strip()
                contact_email = request.POST.get('contact_email', '').strip()
                if not organizer_name or not contact_email:
                    raise ValueError('Nama organizer dan email kontak wajib diisi.')
                execute_query(
                    'UPDATE ORGANIZER SET organizer_name=%s, contact_email=%s WHERE organizer_id=%s',
                    [organizer_name, contact_email, user.get('organizer_id')],
                )
            refresh_login_user(request)
            messages.success(request, 'Profil berhasil diperbarui.')
            return redirect('accounts:profile')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    return render(request, 'accounts/profile_edit.html', {'user': get_current_user(request)})


@login_required
def password_update_view(request):
    if request.method == 'POST':
        user = get_current_user(request)
        old_password = request.POST.get('old_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        if not authenticate_user(user['username'], old_password):
            messages.error(request, 'Password lama salah.')
        elif not new_password or new_password != confirm_password:
            messages.error(request, 'Password baru dan konfirmasi password tidak cocok.')
        else:
            execute_query('UPDATE USER_ACCOUNT SET password=%s WHERE user_id=%s', [new_password, user['user_id']])
            refresh_login_user(request)
            messages.success(request, 'Password berhasil diperbarui.')
            return redirect('accounts:profile')
    return render(request, 'accounts/password_update.html', {'user': get_current_user(request)})
