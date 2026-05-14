import uuid

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import redirect, render

from core.auth import login_required, page_role, role_required
from core.db import db_error_message, execute_query, fetch_all, fetch_one


STATUS_MAP = {
    'paid': 'Valid',
    'valid': 'Valid',
    'lunas': 'Valid',
    'pending': 'Pending',
    'used': 'Terpakai',
    'terpakai': 'Terpakai',
    'cancelled': 'Dibatalkan',
    'canceled': 'Dibatalkan',
    'dibatalkan': 'Dibatalkan',
}

STATUS_CHOICES = [
    ('Paid', 'Valid'),
    ('Used', 'Terpakai'),
    ('Cancelled', 'Dibatalkan'),
]


def _normalize_payment_status(value):
    value = (value or '').strip()
    lower = value.lower()

    aliases = {
        'valid': 'Paid',
        'paid': 'Paid',
        'lunas': 'Paid',

        'terpakai': 'Used',
        'used': 'Used',

        'dibatalkan': 'Cancelled',
        'cancelled': 'Cancelled',
        'canceled': 'Cancelled',

        'pending': 'Pending',
    }

    return aliases.get(lower, value)


def _status_label(value):
    return STATUS_MAP.get((value or '').strip().lower(), value or '-')


def _status_filter_values(value):
    normalized = _normalize_payment_status(value)

    if normalized == 'Paid':
        return ['Paid', 'paid', 'Valid', 'valid', 'Lunas', 'lunas']

    if normalized == 'Used':
        return ['Used', 'used', 'Terpakai', 'terpakai']

    if normalized == 'Cancelled':
        return ['Cancelled', 'cancelled', 'Canceled', 'canceled', 'Dibatalkan', 'dibatalkan']

    if normalized == 'Pending':
        return ['Pending', 'pending']

    return [value]


def _fmt_money(value):
    try:
        return f"{int(float(value)):,}".replace(',', '.')
    except (TypeError, ValueError):
        return '0'


def _current_user(request):
    return request.session.get('user') or {}


def _current_customer_id(request):
    user = _current_user(request)
    return user.get('customer_id') if user.get('role') == 'customer' else None


def _current_organizer_id(request):
    user = _current_user(request)
    return user.get('organizer_id') if user.get('role') == 'organizer' else None


def _is_admin(request):
    return page_role(request) == 'admin' or _current_user(request).get('role') == 'administrator'


def _is_organizer(request):
    return page_role(request) == 'organizer' or _current_user(request).get('role') == 'organizer'


def _is_customer(request):
    return page_role(request) == 'customer' or _current_user(request).get('role') == 'customer'


def _can_manage_categories(request):
    return _is_admin(request) or _is_organizer(request)


def _can_create_ticket(request):
    return _is_admin(request) or _is_organizer(request)


def _can_manage_ticket(request):
    return _is_admin(request)


# ticket category views

def _fetch_category_rows(request, q='', event_id=''):
    role = page_role(request)
    organizer_id = _current_organizer_id(request)

    where = ['1=1']
    params = []

    if role == 'organizer':
        if organizer_id:
            where.append('e.organizer_id = %s')
            params.append(organizer_id)
        else:
            where.append('1=0')

    if q:
        like = f"%{q.lower()}%"
        where.append('(LOWER(tc.category_name) LIKE %s OR LOWER(e.event_title) LIKE %s)')
        params.extend([like, like])

    if event_id:
        where.append('e.event_id = %s')
        params.append(event_id)

    rows = fetch_all(
        f'''
        SELECT
            tc.category_id::text,
            tc.category_name,
            tc.quota,
            tc.price,
            e.event_id::text,
            e.event_title,
            v.capacity,
            COUNT(t.ticket_id) AS used
        FROM TICKET_CATEGORY tc
        JOIN EVENT e ON e.event_id = tc.tevent_id
        JOIN VENUE v ON v.venue_id = e.venue_id
        LEFT JOIN TICKET t ON t.tcategory_id = tc.category_id
        WHERE {' AND '.join(where)}
        GROUP BY
            tc.category_id,
            tc.category_name,
            tc.quota,
            tc.price,
            e.event_id,
            e.event_title,
            v.capacity
        ORDER BY e.event_title ASC, tc.category_name ASC
        ''',
        params,
    )

    for row in rows:
        row['price_display'] = _fmt_money(row.get('price'))
        row['used'] = int(row.get('used') or 0)
        row['remaining'] = int(row.get('quota') or 0) - row['used']

    return rows


def _category_events(request):
    role = page_role(request)
    organizer_id = _current_organizer_id(request)

    where = []
    params = []

    if role == 'organizer':
        if organizer_id:
            where.append('organizer_id = %s')
            params.append(organizer_id)
        else:
            where.append('1=0')

    sql = '''
        SELECT event_id::text, event_title
        FROM EVENT
    '''

    if where:
        sql += ' WHERE ' + ' AND '.join(where)

    sql += ' ORDER BY event_title ASC'

    return fetch_all(sql, params)


def _category_context(request, rows=None, **extra):
    if rows is None:
        rows = _fetch_category_rows(request)

    all_rows = _fetch_category_rows(request)

    ctx = {
        'categories': rows,
        'events': _category_events(request),
        'can_manage': _can_manage_categories(request),
        'page_role': page_role(request),
        'q': request.GET.get('q', ''),
        'event_filter': request.GET.get('event_id', ''),
        'total_kategori': len(all_rows),
        'total_kuota': sum(int(r.get('quota') or 0) for r in all_rows),
        'harga_tertinggi': _fmt_money(
            max([float(r.get('price') or 0) for r in all_rows], default=0)
        ),
    }

    ctx.update(extra)
    return ctx


def _validate_category_payload(request, category_id=None):
    tevent_id = request.POST.get('tevent_id', '').strip()
    name = request.POST.get('category_name', '').strip()

    try:
        quota = int(request.POST.get('quota', '0'))
        price = float(request.POST.get('price', '0'))
    except ValueError:
        raise ValueError('Quota dan price wajib berupa angka.')

    if not tevent_id or not name:
        raise ValueError('Event dan category name wajib diisi.')

    if quota <= 0:
        raise ValueError('Quota wajib lebih dari 0.')

    if price < 0:
        raise ValueError('Price tidak boleh negatif.')

    venue = fetch_one(
        '''
        SELECT v.capacity
        FROM EVENT e
        JOIN VENUE v ON v.venue_id = e.venue_id
        WHERE e.event_id = %s
        ''',
        [tevent_id],
    )

    if not venue:
        raise ValueError('Event tidak ditemukan.')

    used_other = fetch_one(
        '''
        SELECT COALESCE(SUM(quota), 0) AS total
        FROM TICKET_CATEGORY
        WHERE tevent_id = %s
          AND (%s::uuid IS NULL OR category_id <> %s::uuid)
        ''',
        [tevent_id, category_id or None, category_id or None],
    )

    total = int(used_other.get('total') or 0) + quota

    if total > int(venue.get('capacity') or 0):
        raise ValueError('Total kuota seluruh kategori tiket melebihi kapasitas venue.')

    return tevent_id, name, quota, price


def ticket_category_list(request):
    rows = _fetch_category_rows(
        request,
        request.GET.get('q', '').strip(),
        request.GET.get('event_id', '').strip(),
    )

    return render(
        request,
        'tickets/ticket_category_list.html',
        _category_context(request, rows),
    )


def ticket_category_partial(request):
    return render(
        request,
        'tickets/partials/ticket_category_table.html',
        _category_context(request),
    )


@role_required('administrator', 'organizer')
def ticket_category_create(request):
    selected = {}

    if request.method == 'POST':
        selected = request.POST.dict()

        try:
            tevent_id, name, quota, price = _validate_category_payload(request)

            execute_query(
                '''
                INSERT INTO TICKET_CATEGORY
                    (category_id, category_name, quota, price, tevent_id)
                VALUES
                    (%s, %s, %s, %s, %s)
                ''',
                [str(uuid.uuid4()), name, quota, price, tevent_id],
            )

            messages.success(request, 'Kategori tiket berhasil ditambahkan.')
            return redirect('tickets:ticket_category_list')

        except (DatabaseError, ValueError) as exc:
            messages.error(
                request,
                db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc),
            )

    return render(
        request,
        'tickets/ticket_category_form.html',
        _category_context(
            request,
            form_mode='create',
            selected_category=selected,
        ),
    )


@role_required('administrator', 'organizer')
def ticket_category_edit(request, category_id):
    category = fetch_one(
        '''
        SELECT
            category_id::text,
            category_name,
            quota,
            price,
            tevent_id::text
        FROM TICKET_CATEGORY
        WHERE category_id = %s
        ''',
        [category_id],
    )

    if not category:
        messages.error(request, 'Kategori tiket tidak ditemukan.')
        return redirect('tickets:ticket_category_list')

    if request.method == 'POST':
        category.update(request.POST.dict())

        try:
            tevent_id, name, quota, price = _validate_category_payload(request, category_id)

            execute_query(
                '''
                UPDATE TICKET_CATEGORY
                SET category_name = %s,
                    quota = %s,
                    price = %s,
                    tevent_id = %s
                WHERE category_id = %s
                ''',
                [name, quota, price, tevent_id, category_id],
            )

            messages.success(request, 'Kategori tiket berhasil diperbarui.')
            return redirect('tickets:ticket_category_list')

        except (DatabaseError, ValueError) as exc:
            messages.error(
                request,
                db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc),
            )

    return render(
        request,
        'tickets/ticket_category_form.html',
        _category_context(
            request,
            form_mode='edit',
            selected_category=category,
        ),
    )


@role_required('administrator', 'organizer')
def ticket_category_delete(request, category_id):
    category = fetch_one(
        '''
        SELECT
            tc.category_id::text,
            tc.category_name,
            e.event_title
        FROM TICKET_CATEGORY tc
        JOIN EVENT e ON e.event_id = tc.tevent_id
        WHERE tc.category_id = %s
        ''',
        [category_id],
    )

    if not category:
        messages.error(request, 'Kategori tiket tidak ditemukan.')
        return redirect('tickets:ticket_category_list')

    if request.method == 'POST':
        try:
            execute_query(
                '''
                DELETE FROM TICKET_CATEGORY
                WHERE category_id = %s
                ''',
                [category_id],
            )

            messages.success(request, 'Kategori tiket berhasil dihapus.')
            return redirect('tickets:ticket_category_list')

        except DatabaseError as exc:
            messages.error(request, db_error_message(exc))

    return render(
        request,
        'tickets/ticket_category_confirm_delete.html',
        _category_context(request, selected_category=category),
    )


# Ticket views
def _ticket_where_for_role(request):
    role = page_role(request)

    params = []
    where = []

    if role == 'customer':
        customer_id = _current_customer_id(request)

        if customer_id:
            where.append('c.customer_id = %s')
            params.append(customer_id)
        else:
            where.append('1=0')

    elif role == 'organizer':
        organizer_id = _current_organizer_id(request)

        if organizer_id:
            where.append('e.organizer_id = %s')
            params.append(organizer_id)
        else:
            where.append('1=0')

    return where, params


def _fetch_ticket_rows(request, q='', status=''):
    where, params = _ticket_where_for_role(request)

    if q:
        like = f"%{q.lower()}%"
        where.append(
            '''
            (
                LOWER(t.ticket_code) LIKE %s
                OR LOWER(e.event_title) LIKE %s
                OR LOWER(c.full_name) LIKE %s
            )
            '''
        )
        params.extend([like, like, like])

    if status:
        status_values = _status_filter_values(status)
        placeholders = ', '.join(['%s'] * len(status_values))
        where.append(f'o.payment_status IN ({placeholders})')
        params.extend(status_values)

    sql = '''
        SELECT
            t.ticket_id::text,
            t.ticket_code,
            o.payment_status AS payment_status,
            t.tcategory_id::text,
            t.torder_id::text,
            tc.category_name,
            tc.price,
            e.event_id::text,
            e.event_title,
            e.event_datetime,
            v.venue_id::text,
            v.venue_name,
            EXISTS (
                SELECT 1
                FROM SEAT sx
                WHERE sx.venue_id = v.venue_id
            ) AS has_reserved_seating,
            c.customer_id::text,
            c.full_name AS customer_name,
            hr.seat_id::text,
            s.section,
            s.row_number,
            s.seat_number
        FROM TICKET t
        JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
        JOIN EVENT e ON e.event_id = tc.tevent_id
        JOIN VENUE v ON v.venue_id = e.venue_id
        JOIN "ORDER" o ON o.order_id = t.torder_id
        JOIN CUSTOMER c ON c.customer_id = o.customer_id
        LEFT JOIN HAS_RELATIONSHIP hr ON hr.ticket_id = t.ticket_id
        LEFT JOIN SEAT s ON s.seat_id = hr.seat_id
    '''

    if where:
        sql += ' WHERE ' + ' AND '.join(where)

    sql += ' ORDER BY e.event_datetime DESC, t.ticket_code DESC'

    rows = fetch_all(sql, params)

    for row in rows:
        row['payment_status'] = _normalize_payment_status(row.get('payment_status'))
        row['status_label'] = _status_label(row.get('payment_status'))
        row['price_display'] = _fmt_money(row.get('price'))
        row['order_code'] = str(row.get('torder_id') or '')[:8].upper()
        row['event_datetime_display'] = str(row.get('event_datetime') or '')[:16]

        if row.get('seat_id'):
            row['seat_label'] = f"{row['section']} - Baris {row['row_number']} No. {row['seat_number']}"
        else:
            row['seat_label'] = '-'

    return rows


def _ticket_context(request, rows=None, **extra):
    if rows is None:
        rows = _fetch_ticket_rows(
            request,
            request.GET.get('q', '').strip(),
            request.GET.get('status', '').strip(),
        )

    role = page_role(request)

    ctx = {
        'tickets': rows,
        'stats': {
            'total': len(rows),
            'valid': sum(1 for r in rows if _normalize_payment_status(r.get('payment_status')) == 'Paid'),
            'used': sum(1 for r in rows if _normalize_payment_status(r.get('payment_status')) == 'Used'),
            'cancelled': sum(1 for r in rows if _normalize_payment_status(r.get('payment_status')) == 'Cancelled'),
        },
        'page_role': role,
        'raw_role': _current_user(request).get('role', 'guest'),
        'page_title': 'Tiket Saya' if role == 'customer' else 'Manajemen Tiket',
        'page_subtitle': 'Akses tiket digital Anda' if role == 'customer' else 'Atur status dan distribusi tiket',
        'is_customer_view': role == 'customer',
        'can_create_ticket': _can_create_ticket(request),
        'can_manage_ticket': _can_manage_ticket(request),
        'status_choices': STATUS_CHOICES,
        'status_filter': _normalize_payment_status(request.GET.get('status', '')),
        'q': request.GET.get('q', ''),
    }

    ctx.update(extra)
    return ctx


def _ticket_form_orders(request):
    role = page_role(request)
    organizer_id = _current_organizer_id(request)

    where = []
    params = []

    if role == 'organizer':
        if organizer_id:
            where.append('(oe.organizer_id = %s OR oe.organizer_id IS NULL)')
            params.append(organizer_id)
        else:
            where.append('1=0')

    sql = '''
        SELECT
            o.order_id::text,
            c.full_name AS customer_name,
            oe.event_id::text,
            oe.event_title,
            oe.organizer_id::text
        FROM "ORDER" o
        JOIN CUSTOMER c ON c.customer_id = o.customer_id
        LEFT JOIN LATERAL (
            SELECT
                e.event_id,
                e.event_title,
                e.organizer_id
            FROM TICKET t
            JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
            JOIN EVENT e ON e.event_id = tc.tevent_id
            WHERE t.torder_id = o.order_id
            ORDER BY t.ticket_code ASC
            LIMIT 1
        ) oe ON TRUE
    '''

    if where:
        sql += ' WHERE ' + ' AND '.join(where)

    sql += ' ORDER BY o.order_date DESC'

    rows = fetch_all(sql, params)

    for row in rows:
        event_title = row.get('event_title') or 'Event belum ditentukan'
        row['event_id'] = row.get('event_id') or ''
        row['label'] = f"{row['order_id'][:8].upper()} - {row['customer_name']} - {event_title}"

    return rows


def _ticket_form_categories(request):
    role = page_role(request)
    organizer_id = _current_organizer_id(request)

    where = []
    params = []

    if role == 'organizer':
        if organizer_id:
            where.append('e.organizer_id = %s')
            params.append(organizer_id)
        else:
            where.append('1=0')

    sql = '''
        SELECT
            tc.category_id::text,
            tc.category_name,
            tc.price,
            tc.quota,
            e.event_id::text,
            e.event_title,
            v.venue_id::text,
            v.venue_name,
            EXISTS (
                SELECT 1
                FROM SEAT sx
                WHERE sx.venue_id = v.venue_id
            ) AS has_reserved_seating,
            COUNT(t.ticket_id) AS used
        FROM TICKET_CATEGORY tc
        JOIN EVENT e ON e.event_id = tc.tevent_id
        JOIN VENUE v ON v.venue_id = e.venue_id
        LEFT JOIN TICKET t ON t.tcategory_id = tc.category_id
    '''

    if where:
        sql += ' WHERE ' + ' AND '.join(where)

    sql += '''
        GROUP BY
            tc.category_id,
            tc.category_name,
            tc.price,
            tc.quota,
            e.event_id,
            e.event_title,
            v.venue_id,
            v.venue_name
        ORDER BY e.event_title ASC, tc.price ASC
    '''

    rows = fetch_all(sql, params)

    for row in rows:
        row['used'] = int(row.get('used') or 0)
        row['remaining'] = int(row.get('quota') or 0) - row['used']
        row['label'] = (
            f"{row['event_title']} - {row['category_name']} - "
            f"Rp {_fmt_money(row.get('price'))} ({row['used']}/{row['quota']})"
        )

    return rows


def _ticket_form_seats(current_ticket_id=None):
    if current_ticket_id:
        rows = fetch_all(
            '''
            SELECT
                s.seat_id::text,
                s.section,
                s.row_number,
                s.seat_number,
                s.venue_id::text,
                v.venue_name
            FROM SEAT s
            JOIN VENUE v ON v.venue_id = s.venue_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM HAS_RELATIONSHIP hr
                WHERE hr.seat_id = s.seat_id
                  AND hr.ticket_id <> %s::uuid
            )
            ORDER BY v.venue_name ASC, s.section ASC, s.row_number ASC, s.seat_number ASC
            ''',
            [current_ticket_id],
        )
    else:
        rows = fetch_all(
            '''
            SELECT
                s.seat_id::text,
                s.section,
                s.row_number,
                s.seat_number,
                s.venue_id::text,
                v.venue_name
            FROM SEAT s
            JOIN VENUE v ON v.venue_id = s.venue_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM HAS_RELATIONSHIP hr
                WHERE hr.seat_id = s.seat_id
            )
            ORDER BY v.venue_name ASC, s.section ASC, s.row_number ASC, s.seat_number ASC
            '''
        )

    for row in rows:
        row['label'] = f"{row['venue_name']} - {row['section']} - Baris {row['row_number']} No. {row['seat_number']}"

    return rows


@login_required
def ticket_list(request):
    rows = _fetch_ticket_rows(
        request,
        request.GET.get('q', '').strip(),
        request.GET.get('status', '').strip(),
    )

    return render(
        request,
        'tickets/ticket_list.html',
        _ticket_context(request, rows),
    )


@login_required
def ticket_partial(request):
    return render(
        request,
        'tickets/partials/ticket_cards.html',
        _ticket_context(request),
    )


@role_required('administrator', 'organizer')
def ticket_create(request):
    selected = {}

    if request.method == 'POST':
        selected = request.POST.dict()

        order_id = request.POST.get('order_id', '').strip()
        category_id = request.POST.get('category_id', '').strip()
        seat_id = request.POST.get('seat_id', '').strip()

        try:
            if not order_id or not category_id:
                raise ValueError('Order dan kategori tiket wajib dipilih.')

            order = fetch_one(
                '''
                SELECT order_id::text
                FROM "ORDER"
                WHERE order_id = %s
                ''',
                [order_id],
            )

            if not order:
                raise ValueError('Order tidak ditemukan.')

            category = fetch_one(
                '''
                SELECT
                    tc.category_id::text,
                    tc.category_name,
                    tc.tevent_id::text AS event_id,
                    v.venue_id::text,
                    EXISTS (
                        SELECT 1
                        FROM SEAT sx
                        WHERE sx.venue_id = v.venue_id
                    ) AS has_reserved_seating
                FROM TICKET_CATEGORY tc
                JOIN EVENT e ON e.event_id = tc.tevent_id
                JOIN VENUE v ON v.venue_id = e.venue_id
                WHERE tc.category_id = %s
                ''',
                [category_id],
            )

            if not category:
                raise ValueError('Kategori tiket tidak ditemukan.')

            order_event = fetch_one(
                '''
                SELECT tc.tevent_id::text AS event_id
                FROM TICKET t
                JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
                WHERE t.torder_id = %s
                LIMIT 1
                ''',
                [order_id],
            )

            if order_event and order_event.get('event_id') and order_event['event_id'] != category['event_id']:
                raise ValueError('Kategori tiket harus sesuai dengan event dari order yang dipilih.')

            if seat_id:
                if not category.get('has_reserved_seating'):
                    raise ValueError('Venue event ini tidak menggunakan reserved seating.')

                seat = fetch_one(
                    '''
                    SELECT seat_id::text, venue_id::text
                    FROM SEAT
                    WHERE seat_id = %s
                    ''',
                    [seat_id],
                )

                if not seat:
                    raise ValueError('Kursi tidak ditemukan.')

                if seat['venue_id'] != category['venue_id']:
                    raise ValueError('Kursi harus berasal dari venue event yang dipilih.')

                occupied = fetch_one(
                    '''
                    SELECT ticket_id::text
                    FROM HAS_RELATIONSHIP
                    WHERE seat_id = %s
                    LIMIT 1
                    ''',
                    [seat_id],
                )

                if occupied:
                    raise ValueError('Kursi sudah di-assign ke tiket lain.')

            with transaction.atomic():
                ticket_id = str(uuid.uuid4())
                ticket_code = f"TIK-{ticket_id[:8].upper()}"

                execute_query(
                    '''
                    INSERT INTO TICKET
                        (ticket_id, ticket_code, tcategory_id, torder_id)
                    VALUES
                        (%s, %s, %s, %s)
                    ''',
                    [ticket_id, ticket_code, category_id, order_id],
                )

                if seat_id:
                    execute_query(
                        '''
                        INSERT INTO HAS_RELATIONSHIP
                            (seat_id, ticket_id)
                        VALUES
                            (%s, %s)
                        ''',
                        [seat_id, ticket_id],
                    )

            messages.success(request, f'Tiket {ticket_code} berhasil dibuat.')
            return redirect('tickets:ticket_list')

        except (DatabaseError, ValueError) as exc:
            messages.error(
                request,
                db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc),
            )

    return render(
        request,
        'tickets/ticket_form.html',
        _ticket_context(
            request,
            form_mode='create',
            selected_ticket=selected,
            orders=_ticket_form_orders(request),
            categories=_ticket_form_categories(request),
            seats=_ticket_form_seats(),
        ),
    )


@role_required('administrator')
def ticket_edit(request, ticket_id):
    rows = _fetch_ticket_rows(request)
    selected = next((r for r in rows if r['ticket_id'] == ticket_id), None)

    if not selected:
        messages.error(request, 'Tiket tidak ditemukan.')
        return redirect('tickets:ticket_list')

    if request.method == 'POST':
        new_status = _normalize_payment_status(request.POST.get('payment_status'))
        seat_id = request.POST.get('seat_id', '').strip()
        current_status = _normalize_payment_status(selected.get('payment_status', 'Pending'))

        try:
            if new_status not in ['Paid', 'Used', 'Cancelled']:
                raise ValueError('Status tiket tidak valid.')

            if current_status in ['Used', 'Cancelled'] and new_status != current_status:
                raise ValueError('Tiket yang sudah Terpakai atau Dibatalkan tidak dapat diubah lagi.')

            if seat_id:
                seat = fetch_one(
                    '''
                    SELECT seat_id::text, venue_id::text
                    FROM SEAT
                    WHERE seat_id = %s
                    ''',
                    [seat_id],
                )

                if not seat:
                    raise ValueError('Kursi tidak ditemukan.')

                if seat['venue_id'] != selected['venue_id']:
                    raise ValueError('Kursi harus berasal dari venue event tiket ini.')

                occupied = fetch_one(
                    '''
                    SELECT ticket_id::text
                    FROM HAS_RELATIONSHIP
                    WHERE seat_id = %s
                      AND ticket_id <> %s
                    LIMIT 1
                    ''',
                    [seat_id, ticket_id],
                )

                if occupied:
                    raise ValueError('Kursi sudah di-assign ke tiket lain.')

            with transaction.atomic():
                execute_query(
                    '''
                    UPDATE "ORDER"
                    SET payment_status = %s
                    WHERE order_id = %s
                    ''',
                    [new_status, selected['torder_id']],
                )

                execute_query(
                    '''
                    DELETE FROM HAS_RELATIONSHIP
                    WHERE ticket_id = %s
                    ''',
                    [ticket_id],
                )

                if seat_id:
                    execute_query(
                        '''
                        INSERT INTO HAS_RELATIONSHIP
                            (seat_id, ticket_id)
                        VALUES
                            (%s, %s)
                        ''',
                        [seat_id, ticket_id],
                    )

            messages.success(request, 'Status dan data tiket berhasil diperbarui.')
            return redirect('tickets:ticket_list')

        except (DatabaseError, ValueError) as exc:
            messages.error(
                request,
                db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc),
            )

    return render(
        request,
        'tickets/ticket_form.html',
        _ticket_context(
            request,
            rows,
            form_mode='edit',
            selected_ticket=selected,
            orders=[],
            categories=[],
            seats=_ticket_form_seats(ticket_id),
        ),
    )


@role_required('administrator')
def ticket_delete(request, ticket_id):
    rows = _fetch_ticket_rows(request)
    selected = next((r for r in rows if r['ticket_id'] == ticket_id), None)

    if not selected:
        messages.error(request, 'Tiket tidak ditemukan.')
        return redirect('tickets:ticket_list')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                execute_query(
                    '''
                    DELETE FROM HAS_RELATIONSHIP
                    WHERE ticket_id = %s
                    ''',
                    [ticket_id],
                )

                execute_query(
                    '''
                    DELETE FROM TICKET
                    WHERE ticket_id = %s
                    ''',
                    [ticket_id],
                )

            messages.success(request, 'Tiket berhasil dihapus.')
            return redirect('tickets:ticket_list')

        except DatabaseError as exc:
            messages.error(request, db_error_message(exc))

    return render(
        request,
        'tickets/ticket_confirm_delete.html',
        _ticket_context(
            request,
            rows,
            selected_ticket=selected,
        ),
    )