from django.shortcuts import render, redirect
from django.contrib import messages
from core.auth import login_required, role_required, has_role, get_current_user
from core.db import fetch_all, fetch_one, execute_query
import uuid


def ticket_category_list(request):
    categories = fetch_all("""
        SELECT tc.*, e.event_title FROM ticket_category tc
        JOIN event e ON tc.tevent_id = e.event_id
        ORDER BY e.event_title, tc.category_name
    """)
    return render(request, 'tickets/ticket_category_list.html', {'categories': categories})


def ticket_category_partial(request):
    categories = fetch_all("""
        SELECT tc.*, e.event_title FROM ticket_category tc
        JOIN event e ON tc.tevent_id = e.event_id
        ORDER BY e.event_title, tc.category_name
    """)
    return render(request, 'tickets/partials/ticket_category_table.html', {'categories': categories})


@role_required('administrator', 'organizer')
def ticket_category_create(request):
    events = fetch_all("SELECT * FROM event ORDER BY event_title")
    if request.method == 'POST':
        name = request.POST.get('category_name', '').strip()
        quota = request.POST.get('quota', '').strip()
        price = request.POST.get('price', '').strip()
        event_id = request.POST.get('tevent_id')
        if not all([name, quota, price, event_id]):
            messages.error(request, 'Semua field wajib diisi.')
        else:
            execute_query(
                "INSERT INTO ticket_category (category_id, category_name, quota, price, tevent_id) VALUES (gen_random_uuid(), %s, %s, %s, %s)",
                [name, int(quota), float(price), event_id]
            )
            messages.success(request, 'Kategori tiket berhasil ditambahkan.')
            return redirect('ticket_category_list')
    return render(request, 'tickets/ticket_category_form.html', {'action': 'create', 'events': events})


@role_required('administrator', 'organizer')
def ticket_category_edit(request, category_id):
    category = fetch_one("SELECT * FROM ticket_category WHERE category_id = %s", [category_id])
    events = fetch_all("SELECT * FROM event ORDER BY event_title")
    if not category:
        return redirect('ticket_category_list')
    if request.method == 'POST':
        name = request.POST.get('category_name', '').strip()
        quota = request.POST.get('quota', '').strip()
        price = request.POST.get('price', '').strip()
        execute_query(
            "UPDATE ticket_category SET category_name=%s, quota=%s, price=%s WHERE category_id=%s",
            [name, int(quota), float(price), category_id]
        )
        messages.success(request, 'Kategori tiket berhasil diperbarui.')
        return redirect('ticket_category_list')
    return render(request, 'tickets/ticket_category_form.html', {'action': 'edit', 'category': category, 'events': events})


@role_required('administrator', 'organizer')
def ticket_category_delete(request, category_id):
    category = fetch_one("SELECT * FROM ticket_category WHERE category_id = %s", [category_id])
    if not category:
        return redirect('ticket_category_list')
    if request.method == 'POST':
        execute_query("DELETE FROM ticket_category WHERE category_id = %s", [category_id])
        messages.success(request, 'Kategori tiket berhasil dihapus.')
        return redirect('ticket_category_list')
    return render(request, 'tickets/ticket_category_confirm_delete.html', {'category': category})


@login_required
def ticket_list(request):
    user = get_current_user(request)
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if has_role(request, 'administrator'):
        sql = """
            SELECT t.*, tc.category_name, e.event_title, c.full_name AS customer_name,
                   o.payment_status
            FROM ticket t
            JOIN ticket_category tc ON t.tcategory_id = tc.category_id
            JOIN event e ON tc.tevent_id = e.event_id
            JOIN "order" o ON t.torder_id = o.order_id
            JOIN customer c ON o.customer_id = c.customer_id
            WHERE 1=1
        """
        params = []
    elif has_role(request, 'organizer'):
        org = fetch_one("SELECT organizer_id FROM organizer WHERE user_id = %s", [user['user_id']])
        sql = """
            SELECT t.*, tc.category_name, e.event_title, c.full_name AS customer_name,
                   o.payment_status
            FROM ticket t
            JOIN ticket_category tc ON t.tcategory_id = tc.category_id
            JOIN event e ON tc.tevent_id = e.event_id
            JOIN "order" o ON t.torder_id = o.order_id
            JOIN customer c ON o.customer_id = c.customer_id
            WHERE e.organizer_id = %s
        """
        params = [org['organizer_id']] if org else []
    else:
        cust = fetch_one("SELECT customer_id FROM customer WHERE user_id = %s", [user['user_id']])
        sql = """
            SELECT t.*, tc.category_name, e.event_title, o.payment_status
            FROM ticket t
            JOIN ticket_category tc ON t.tcategory_id = tc.category_id
            JOIN event e ON tc.tevent_id = e.event_id
            JOIN "order" o ON t.torder_id = o.order_id
            WHERE o.customer_id = %s
        """
        params = [cust['customer_id']] if cust else []

    if search:
        sql += " AND (t.ticket_code ILIKE %s OR e.event_title ILIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    if status_filter:
        sql += " AND o.payment_status = %s"
        params.append(status_filter)

    sql += " ORDER BY t.ticket_code"
    tickets = fetch_all(sql, params)
    return render(request, 'tickets/ticket_list.html', {'tickets': tickets, 'search': search, 'status_filter': status_filter})


def ticket_partial(request):
    tickets = fetch_all("""
        SELECT t.*, tc.category_name, e.event_title FROM ticket t
        JOIN ticket_category tc ON t.tcategory_id = tc.category_id
        JOIN event e ON tc.tevent_id = e.event_id ORDER BY t.ticket_code
    """)
    return render(request, 'tickets/partials/ticket_cards.html', {'tickets': tickets})


@role_required('administrator', 'organizer')
def ticket_create(request):
    orders = fetch_all("""
        SELECT o.order_id, o.payment_status, c.full_name, e.event_title
        FROM "order" o
        JOIN customer c ON o.customer_id = c.customer_id
        JOIN ticket t ON t.torder_id = o.order_id
        JOIN ticket_category tc ON t.tcategory_id = tc.category_id
        JOIN event e ON tc.tevent_id = e.event_id
        GROUP BY o.order_id, c.full_name, e.event_title, o.payment_status
        ORDER BY c.full_name
    """)
    if request.method == 'POST':
        order_id = request.POST.get('torder_id')
        category_id = request.POST.get('tcategory_id')
        seat_id = request.POST.get('seat_id') or None
        ticket_id = str(uuid.uuid4())
        code = f'TTT-{ticket_id[:8].upper()}'
        execute_query(
            "INSERT INTO ticket (ticket_id, ticket_code, tcategory_id, torder_id) VALUES (%s, %s, %s, %s)",
            [ticket_id, code, category_id, order_id]
        )
        if seat_id:
            execute_query(
                "INSERT INTO has_relationship (seat_id, ticket_id) VALUES (%s, %s)",
                [seat_id, ticket_id]
            )
        messages.success(request, f'Tiket {code} berhasil dibuat.')
        return redirect('ticket_list')
    return render(request, 'tickets/ticket_form.html', {'action': 'create', 'orders': orders})


@role_required('administrator')
def ticket_edit(request, ticket_id):
    ticket = fetch_one("SELECT * FROM ticket WHERE ticket_id = %s", [ticket_id])
    seats = fetch_all("""
        SELECT s.*, v.venue_name FROM seat s JOIN venue v ON s.venue_id = v.venue_id
        WHERE s.seat_id NOT IN (SELECT seat_id FROM has_relationship WHERE ticket_id != %s)
        ORDER BY v.venue_name, s.section, s.row_number
    """, [ticket_id])
    current_seat = fetch_one("SELECT seat_id FROM has_relationship WHERE ticket_id = %s", [ticket_id])
    if not ticket:
        return redirect('ticket_list')
    if request.method == 'POST':
        seat_id = request.POST.get('seat_id') or None
        execute_query("DELETE FROM has_relationship WHERE ticket_id = %s", [ticket_id])
        if seat_id:
            execute_query(
                "INSERT INTO has_relationship (seat_id, ticket_id) VALUES (%s, %s)",
                [seat_id, ticket_id]
            )
        messages.success(request, 'Tiket berhasil diperbarui.')
        return redirect('ticket_list')
    return render(request, 'tickets/ticket_form.html', {
        'action': 'edit', 'ticket': ticket, 'seats': seats, 'current_seat': current_seat
    })


@role_required('administrator')
def ticket_delete(request, ticket_id):
    ticket = fetch_one("SELECT * FROM ticket WHERE ticket_id = %s", [ticket_id])
    if not ticket:
        return redirect('ticket_list')
    if request.method == 'POST':
        execute_query("DELETE FROM has_relationship WHERE ticket_id = %s", [ticket_id])
        execute_query("DELETE FROM ticket WHERE ticket_id = %s", [ticket_id])
        messages.success(request, 'Tiket berhasil dihapus.')
        return redirect('ticket_list')
    return render(request, 'tickets/ticket_confirm_delete.html', {'ticket': ticket})
