import uuid

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import redirect, render

from core.auth import login_required, page_role, role_required
from core.db import db_error_message, execute_query, fetch_all, fetch_one

PAYMENT_STATUSES = ['Paid', 'Pending', 'Cancelled']
STATUS_LABELS = {'Paid': 'Lunas', 'Pending': 'Pending', 'Cancelled': 'Dibatalkan'}


def _fmt_money(value):
    try:
        return f"Rp {int(float(value)):,}".replace(',', '.')
    except (TypeError, ValueError):
        return 'Rp 0'


def _current_user(request):
    return request.session.get('user') or {}


def _role_ids(request):
    user = _current_user(request)
    return user.get('customer_id'), user.get('organizer_id')


def _get_orders(request, status='', q=''):
    role = page_role(request)
    customer_id, organizer_id = _role_ids(request)
    where = ['1=1']
    params = []
    if role == 'customer' and customer_id:
        where.append('o.customer_id = %s')
        params.append(customer_id)
    elif role == 'organizer' and organizer_id:
        where.append(
            'EXISTS (SELECT 1 FROM TICKET t JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id '
            'JOIN EVENT e ON e.event_id = tc.tevent_id WHERE t.torder_id = o.order_id AND e.organizer_id = %s)'
        )
        params.append(organizer_id)
    if status in PAYMENT_STATUSES:
        where.append('o.payment_status = %s')
        params.append(status)
    if q:
        like = f"%{q.lower()}%"
        where.append('(LOWER(o.order_id::text) LIKE %s OR LOWER(c.full_name) LIKE %s)')
        params.extend([like, like])
    
    rows = fetch_all(
        f'''
        SELECT o.order_id::text, o.order_date, o.payment_status, o.total_amount,
               c.customer_id::text, c.full_name AS customer_name,
               COALESCE((SELECT e.event_title FROM TICKET t
                         JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
                         JOIN EVENT e ON e.event_id = tc.tevent_id
                         WHERE t.torder_id = o.order_id LIMIT 1), '-') AS event_name,
               COUNT(t2.ticket_id) AS ticket_count
        FROM "ORDER" o
        JOIN CUSTOMER c ON c.customer_id = o.customer_id
        LEFT JOIN TICKET t2 ON t2.torder_id = o.order_id
        WHERE {' AND '.join(where)}
        GROUP BY o.order_id, o.order_date, o.payment_status, o.total_amount, c.customer_id, c.full_name
        ORDER BY o.order_date DESC
        ''',
        params,
    )
    for row in rows:
        row['status_label'] = STATUS_LABELS.get(row['payment_status'], row['payment_status'])
        row['total_display'] = _fmt_money(row['total_amount'])
        row['order_date_display'] = str(row['order_date'])[:16]
    return rows


def _orders_context(request, orders=None, **extra):
    if orders is None:
        orders = _get_orders(request)
    all_orders = _get_orders(request)
    total_revenue = sum(float(o['total_amount']) for o in all_orders if o['payment_status'] == 'Paid')
    ctx = {
        'orders': orders,
        'role': page_role(request),
        'payment_statuses': PAYMENT_STATUSES,
        'status_labels': STATUS_LABELS,
        'filter_status': request.GET.get('status', ''),
        'search': request.GET.get('q', ''),
        'total_orders': len(all_orders),
        'total_paid': sum(1 for o in all_orders if o['payment_status'] == 'Paid'),
        'total_pending': sum(1 for o in all_orders if o['payment_status'] == 'Pending'),
        'total_revenue_display': _fmt_money(total_revenue),
    }
    ctx.update(extra)
    return ctx


@login_required
def order_list(request):
    orders = _get_orders(request, request.GET.get('status', '').strip(), request.GET.get('q', '').strip())
    return render(request, 'orders/order_list.html', _orders_context(request, orders))


def _build_event(event_id):
    ev = fetch_one(
        '''
        SELECT e.event_id::text, e.event_title, e.event_datetime,
               v.venue_name, v.venue_id::text,
               EXISTS (SELECT 1 FROM SEAT sx WHERE sx.venue_id = v.venue_id) AS has_reserved_seating
        FROM EVENT e JOIN VENUE v ON e.venue_id = v.venue_id
        WHERE e.event_id = %s
        ''',
        [event_id],
    )
    if not ev:
        return None
    artists = fetch_all(
        'SELECT a.name FROM ARTIST a JOIN EVENT_ARTIST ea ON a.artist_id = ea.artist_id WHERE ea.event_id = %s ORDER BY a.name ASC',
        [event_id],
    )
    cats = fetch_all(
        '''
        SELECT tc.category_id::text, tc.category_name, tc.price, tc.quota,
               COUNT(t.ticket_id) AS used
        FROM TICKET_CATEGORY tc
        LEFT JOIN TICKET t ON t.tcategory_id = tc.category_id
        WHERE tc.tevent_id = %s
        GROUP BY tc.category_id, tc.category_name, tc.price, tc.quota
        ORDER BY tc.price ASC
        ''',
        [event_id],
    )
    for cat in cats:
        cat['price_display'] = _fmt_money(cat['price'])
        cat['remaining'] = int(cat['quota']) - int(cat['used'] or 0)
    seats = fetch_all(
        '''
        SELECT s.seat_id::text, s.section, s.row_number, s.seat_number
        FROM SEAT s
        WHERE s.venue_id = %s AND NOT EXISTS (SELECT 1 FROM HAS_RELATIONSHIP hr WHERE hr.seat_id = s.seat_id)
        ORDER BY s.section ASC, s.row_number ASC, s.seat_number ASC
        ''',
        [ev['venue_id']],
    )
    return {
        'event_id': ev['event_id'],
        'event_title': ev['event_title'],
        'event_datetime': ev['event_datetime'],
        'venue_name': ev['venue_name'],
        'artists': [a['name'] for a in artists],
        'categories': cats,
        'has_reserved_seating': ev['has_reserved_seating'],
        'seats': seats,
    }


@login_required
def checkout(request):
    if page_role(request) != 'customer':
        messages.error(request, 'Hanya customer yang dapat membuat order.')
        return redirect('events:event_list')
    customer_id = _current_user(request).get('customer_id')
    event_id = request.GET.get('event_id') or request.POST.get('event_id')
    if not event_id:
        first = fetch_one('SELECT event_id::text FROM EVENT ORDER BY event_datetime LIMIT 1')
        event_id = first['event_id'] if first else None
    if not event_id:
        messages.error(request, 'Belum ada event untuk checkout.')
        return redirect('events:event_list')

    if request.method == 'POST':
        category_id = request.POST.get('category_id', '').strip()
        promo_code = request.POST.get('promo_code', '').strip()
        seat_id = request.POST.get('seat_id', '').strip()
        try:
            quantity = int(request.POST.get('quantity', '1'))
            if quantity <= 0 or quantity > 10:
                raise ValueError('Jumlah tiket wajib 1 sampai 10.')
            cat = fetch_one(
                'SELECT category_id::text, category_name, price FROM TICKET_CATEGORY WHERE category_id = %s AND tevent_id = %s',
                [category_id, event_id],
            )
            if not cat:
                raise ValueError('Kategori tiket tidak ditemukan untuk event ini.')
            total_amount = float(cat['price']) * quantity
            promo = None
            if promo_code:
                promo = fetch_one(
                    'SELECT promotion_id::text, promo_code, discount_type, discount_value FROM PROMOTION WHERE UPPER(promo_code)=UPPER(%s)',
                    [promo_code],
                )
                if not promo:
                    raise ValueError('Kode promo tidak ditemukan.')
                if promo['discount_type'] == 'PERCENTAGE':
                    total_amount -= total_amount * float(promo['discount_value']) / 100
                else:
                    total_amount -= float(promo['discount_value'])
                total_amount = max(total_amount, 0)
            
            with transaction.atomic():
                order_id = str(uuid.uuid4())
                execute_query(
                    'INSERT INTO "ORDER" (order_id, order_date, payment_status, total_amount, customer_id) VALUES (%s, NOW(), %s, %s, %s)',
                    [order_id, 'Pending', total_amount, customer_id],
                )
                first_ticket_id = None
                for _ in range(quantity):
                    ticket_id = str(uuid.uuid4())
                    ticket_code = f"TIK-{ticket_id[:8].upper()}"
                    execute_query(
                        'INSERT INTO TICKET (ticket_id, ticket_code, tcategory_id, torder_id) VALUES (%s, %s, %s, %s)',
                        [ticket_id, ticket_code, category_id, order_id],
                    )
                    if first_ticket_id is None:
                        first_ticket_id = ticket_id
                if seat_id and first_ticket_id:
                    execute_query('INSERT INTO HAS_RELATIONSHIP (seat_id, ticket_id) VALUES (%s, %s)', [seat_id, first_ticket_id])
                if promo:
                    execute_query('INSERT INTO ORDER_PROMOTION (order_promotion_id, promotion_id, order_id) VALUES (%s, %s, %s)', [str(uuid.uuid4()), promo['promotion_id'], order_id])
            
            messages.success(request, 'Order berhasil dibuat dengan status Pending.')
            return redirect('orders:order_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    
    event = _build_event(event_id)
    if not event:
        messages.error(request, 'Event tidak ditemukan.')
        return redirect('events:event_list')
    return render(request, 'orders/checkout.html', {'event': event, 'role': page_role(request)})


@role_required('administrator')
def order_update(request, order_id):
    order = fetch_one(
        'SELECT o.order_id::text, o.payment_status, o.total_amount, c.full_name AS customer_name FROM "ORDER" o JOIN CUSTOMER c ON c.customer_id = o.customer_id WHERE o.order_id = %s',
        [order_id],
    )
    if not order:
        messages.error(request, 'Order tidak ditemukan.')
        return redirect('orders:order_list')
    if request.method == 'POST':
        status = request.POST.get('payment_status')
        if status not in PAYMENT_STATUSES:
            messages.error(request, 'Status pembayaran tidak valid.')
        else:
            execute_query('UPDATE "ORDER" SET payment_status=%s WHERE order_id=%s', [status, order_id])
            messages.success(request, 'Status order berhasil diperbarui.')
            return redirect('orders:order_list')
    return render(request, 'orders/order_update.html', _orders_context(request, selected_order=order))


@role_required('administrator')
def order_delete(request, order_id):
    order = fetch_one('SELECT o.order_id::text, c.full_name AS customer_name FROM "ORDER" o JOIN CUSTOMER c ON c.customer_id = o.customer_id WHERE o.order_id=%s', [order_id])
    if not order:
        messages.error(request, 'Order tidak ditemukan.')
        return redirect('orders:order_list')
    if request.method == 'POST':
        try:
            with transaction.atomic():
                execute_query('DELETE FROM HAS_RELATIONSHIP WHERE ticket_id IN (SELECT ticket_id FROM TICKET WHERE torder_id = %s)', [order_id])
                execute_query('DELETE FROM TICKET WHERE torder_id = %s', [order_id])
                execute_query('DELETE FROM ORDER_PROMOTION WHERE order_id = %s', [order_id])
                execute_query('DELETE FROM "ORDER" WHERE order_id = %s', [order_id])
            messages.success(request, 'Order berhasil dihapus.')
            return redirect('orders:order_list')
        except DatabaseError as exc:
            messages.error(request, db_error_message(exc))
    return render(request, 'orders/order_confirm_delete.html', _orders_context(request, selected_order=order))