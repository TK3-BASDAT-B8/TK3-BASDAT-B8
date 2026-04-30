from django.shortcuts import render, redirect
from django.contrib import messages
from core.auth import (
    login_user, logout_user, register_user,
    login_required, role_required, get_current_user, has_role
)
from core.db import fetch_one, execute_query


def login_view(request):
    if request.session.get('user_id'):
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if login_user(request, username, password):
            return redirect('dashboard')
        messages.error(request, 'Username atau password salah.')
    return render(request, 'accounts/login.html')


def logout_view(request):
    if request.method == 'POST':
        logout_user(request)
    return redirect('login')


def register(request):
    return render(request, 'accounts/register.html')


def register_customer(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone_number', '').strip()

        if not username or not password or not full_name:
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'accounts/register_customer.html')

        existing = fetch_one("SELECT user_id FROM user_account WHERE username = %s", [username])
        if existing:
            messages.error(request, 'Username sudah digunakan.')
            return render(request, 'accounts/register_customer.html')

        register_user(username, password)
        user = fetch_one("SELECT user_id FROM user_account WHERE username = %s", [username])
        customer_role = fetch_one("SELECT role_id FROM role WHERE role_name = 'customer'")

        execute_query(
            "INSERT INTO customer (customer_id, full_name, phone_number, user_id) VALUES (gen_random_uuid(), %s, %s, %s)",
            [full_name, phone, user['user_id']]
        )
        execute_query(
            "INSERT INTO account_role (role_id, user_id) VALUES (%s, %s)",
            [customer_role['role_id'], user['user_id']]
        )
        messages.success(request, 'Akun berhasil dibuat. Silakan login.')
        return redirect('login')

    return render(request, 'accounts/register_customer.html')


def register_organizer(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        organizer_name = request.POST.get('organizer_name', '').strip()
        contact_email = request.POST.get('contact_email', '').strip()

        if not username or not password or not organizer_name:
            messages.error(request, 'Semua field wajib diisi.')
            return render(request, 'accounts/register_organizer.html')

        existing = fetch_one("SELECT user_id FROM user_account WHERE username = %s", [username])
        if existing:
            messages.error(request, 'Username sudah digunakan.')
            return render(request, 'accounts/register_organizer.html')

        register_user(username, password)
        user = fetch_one("SELECT user_id FROM user_account WHERE username = %s", [username])
        org_role = fetch_one("SELECT role_id FROM role WHERE role_name = 'organizer'")

        execute_query(
            "INSERT INTO organizer (organizer_id, organizer_name, contact_email, user_id) VALUES (gen_random_uuid(), %s, %s, %s)",
            [organizer_name, contact_email, user['user_id']]
        )
        execute_query(
            "INSERT INTO account_role (role_id, user_id) VALUES (%s, %s)",
            [org_role['role_id'], user['user_id']]
        )
        messages.success(request, 'Akun berhasil dibuat. Silakan login.')
        return redirect('login')

    return render(request, 'accounts/register_organizer.html')


@login_required
def dashboard(request):
    if has_role(request, 'administrator'):
        return render(request, 'accounts/dashboard_admin.html')
    elif has_role(request, 'organizer'):
        return render(request, 'accounts/dashboard_organizer.html')
    return render(request, 'accounts/dashboard_customer.html')


@login_required
def dashboard_stats(request):
    # htmx partial — returns stats fragment only
    if has_role(request, 'administrator'):
        return render(request, 'accounts/partials/dashboard_stats.html')
    return render(request, 'accounts/partials/dashboard_stats.html')


@login_required
def profile(request):
    user = get_current_user(request)
    extra = None
    if has_role(request, 'customer'):
        extra = fetch_one("SELECT * FROM customer WHERE user_id = %s", [user['user_id']])
    elif has_role(request, 'organizer'):
        extra = fetch_one("SELECT * FROM organizer WHERE user_id = %s", [user['user_id']])
    return render(request, 'accounts/profile.html', {'user': user, 'extra': extra})


@login_required
def profile_edit(request):
    user = get_current_user(request)
    if request.method == 'POST':
        if has_role(request, 'customer'):
            full_name = request.POST.get('full_name', '').strip()
            phone = request.POST.get('phone_number', '').strip()
            execute_query(
                "UPDATE customer SET full_name = %s, phone_number = %s WHERE user_id = %s",
                [full_name, phone, user['user_id']]
            )
        elif has_role(request, 'organizer'):
            org_name = request.POST.get('organizer_name', '').strip()
            email = request.POST.get('contact_email', '').strip()
            execute_query(
                "UPDATE organizer SET organizer_name = %s, contact_email = %s WHERE user_id = %s",
                [org_name, email, user['user_id']]
            )
        messages.success(request, 'Profil berhasil diperbarui.')
        return redirect('profile')

    extra = None
    if has_role(request, 'customer'):
        extra = fetch_one("SELECT * FROM customer WHERE user_id = %s", [user['user_id']])
    elif has_role(request, 'organizer'):
        extra = fetch_one("SELECT * FROM organizer WHERE user_id = %s", [user['user_id']])
    return render(request, 'accounts/profile_edit.html', {'user': user, 'extra': extra})


@login_required
def password_update(request):
    from django.contrib.auth.hashers import make_password, check_password
    user = get_current_user(request)
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new_pw = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        db_user = fetch_one("SELECT password FROM user_account WHERE user_id = %s", [user['user_id']])

        if not check_password(current, db_user['password']):
            messages.error(request, 'Password saat ini salah.')
        elif new_pw != confirm:
            messages.error(request, 'Konfirmasi password tidak cocok.')
        else:
            execute_query(
                "UPDATE user_account SET password = %s WHERE user_id = %s",
                [make_password(new_pw), user['user_id']]
            )
            messages.success(request, 'Password berhasil diperbarui.')
            return redirect('profile')

    return render(request, 'accounts/password_update.html')
