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
from core.db import db_error_message, execute_query, fetch_all, fetch_one


def _fmt_int(value):
    try:
        return f"{int(value):,}".replace(',', '.')
    except (TypeError, ValueError):
        return '0'


def _fmt_money(value):
    try:
        return f"Rp {int(float(value)):,}".replace(',', '.')
    except (TypeError, ValueError):
        return 'Rp 0'


def _admin_dashboard_stats():
    row = fetch_one('''
        SELECT
            (SELECT COUNT(*)::int FROM USER_ACCOUNT) AS total_users,
            (SELECT COUNT(*)::int FROM EVENT) AS total_events,
            (SELECT COALESCE(SUM(total_amount), 0) FROM "ORDER" WHERE payment_status = 'Paid') AS total_revenue,
            (SELECT COUNT(*)::int FROM PROMOTION) AS total_promos,
            (SELECT COUNT(*)::int FROM VENUE) AS total_venues,
            (SELECT COUNT(*)::int FROM VENUE v WHERE EXISTS (SELECT 1 FROM SEAT s WHERE s.venue_id = v.venue_id)) AS reserved_venues,
            (SELECT COALESCE(MAX(capacity), 0) FROM VENUE) AS max_capacity,
            (SELECT COUNT(*)::int FROM PROMOTION WHERE discount_type = 'PERCENTAGE') AS promo_percentage,
            (SELECT COUNT(*)::int FROM PROMOTION WHERE discount_type = 'NOMINAL') AS promo_nominal,
            (SELECT COUNT(*)::int FROM ORDER_PROMOTION) AS promo_usage
    ''') or {}
    row['revenue_display'] = _fmt_money(row.get('total_revenue', 0))
    row['max_capacity_display'] = _fmt_int(row.get('max_capacity', 0))
    return row


def _organizer_dashboard_stats(organizer_id):
    if not organizer_id:
        return {'active_events': 0, 'total_tickets': 0, 'revenue_display': 'Rp 0', 'venue_partners': 0, 'events': []}
    row = fetch_one('''
        SELECT
            (SELECT COUNT(*)::int FROM EVENT WHERE organizer_id = %s AND event_datetime >= NOW()) AS active_events,
            (
                SELECT COUNT(*)::int FROM TICKET t
                JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
                JOIN EVENT e ON e.event_id = tc.tevent_id
                WHERE e.organizer_id = %s
            ) AS total_tickets,
            (
                SELECT COALESCE(SUM(o.total_amount), 0)
                FROM "ORDER" o
                WHERE o.payment_status = 'Paid'
                  AND o.order_id IN (
                      SELECT DISTINCT t.torder_id FROM TICKET t
                      JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
                      JOIN EVENT e ON e.event_id = tc.tevent_id
                      WHERE e.organizer_id = %s
                  )
            ) AS total_revenue,
            (SELECT COUNT(DISTINCT e.venue_id)::int FROM EVENT e WHERE e.organizer_id = %s) AS venue_partners
    ''', [organizer_id, organizer_id, organizer_id, organizer_id]) or {}
    row['revenue_display'] = _fmt_money(row.get('total_revenue', 0))
    row['events'] = fetch_all('''
        SELECT e.event_id::text, e.event_title, e.event_datetime::text AS event_datetime, v.venue_name
        FROM EVENT e JOIN VENUE v ON v.venue_id = e.venue_id
        WHERE e.organizer_id = %s
        ORDER BY e.event_datetime ASC LIMIT 5
    ''', [organizer_id])
    return row


def _customer_dashboard_stats(customer_id):
    if not customer_id:
        return {'active_tickets': 0, 'total_tickets': 0, 'available_promos': 0, 'spending_display': 'Rp 0', 'events': []}
    row = fetch_one('''
        SELECT
            (
                SELECT COUNT(*)::int FROM TICKET t
                JOIN "ORDER" o ON o.order_id = t.torder_id
                JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
                JOIN EVENT e ON e.event_id = tc.tevent_id
                WHERE o.customer_id = %s AND o.payment_status = 'Paid' AND e.event_datetime >= NOW()
            ) AS active_tickets,
            (
                SELECT COUNT(*)::int FROM TICKET t
                JOIN "ORDER" o ON o.order_id = t.torder_id
                WHERE o.customer_id = %s
            ) AS total_tickets,
            (SELECT COUNT(*)::int FROM PROMOTION WHERE end_date >= CURRENT_DATE) AS available_promos,
            (SELECT COALESCE(SUM(total_amount), 0) FROM "ORDER" WHERE customer_id = %s AND payment_status = 'Paid') AS total_spending
    ''', [customer_id, customer_id, customer_id]) or {}
    row['spending_display'] = _fmt_money(row.get('total_spending', 0))
    row['events'] = fetch_all('''
        SELECT DISTINCT e.event_id::text, e.event_title, e.event_datetime::text AS event_datetime, v.venue_name
        FROM TICKET t
        JOIN "ORDER" o ON o.order_id = t.torder_id
        JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
        JOIN EVENT e ON e.event_id = tc.tevent_id
        JOIN VENUE v ON v.venue_id = e.venue_id
        WHERE o.customer_id = %s AND e.event_datetime >= NOW()
        ORDER BY e.event_datetime ASC LIMIT 5
    ''', [customer_id])
    return row


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
        return render(request, 'accounts/dashboard_admin.html', {'user': user, 'stats': _admin_dashboard_stats()})
    if user['role'] == 'organizer':
        return render(request, 'accounts/dashboard_organizer.html', {'user': user, 'stats': _organizer_dashboard_stats(user.get('organizer_id'))})
    return render(request, 'accounts/dashboard_customer.html', {'user': user, 'stats': _customer_dashboard_stats(user.get('customer_id'))})


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
