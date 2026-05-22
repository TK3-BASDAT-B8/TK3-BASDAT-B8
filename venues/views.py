import uuid

from django.contrib import messages
from django.db import DatabaseError
from django.shortcuts import redirect, render

from core.auth import get_current_user, role_required, page_role
from core.db import db_error_message, execute_query, fetch_all, fetch_one


def _can_manage(request):
    user = get_current_user(request)
    return bool(user and user.get('role') in ['administrator', 'organizer'])


def _fmt_int(value):
    try:
        return f"{int(value):,}".replace(',', '.')
    except (TypeError, ValueError):
        return '0'


# venue views

def _fetch_venues(q='', city='', seating=''):
    where = []
    params = []
    if q:
        like = f"%{q.lower()}%"
        where.append('(LOWER(v.venue_name) LIKE %s OR LOWER(v.address) LIKE %s)')
        params.extend([like, like])
    if city:
        where.append('LOWER(v.city) = LOWER(%s)')
        params.append(city)
    if seating == 'reserved':
        where.append('EXISTS (SELECT 1 FROM SEAT sx WHERE sx.venue_id = v.venue_id)')
    elif seating == 'free':
        where.append('NOT EXISTS (SELECT 1 FROM SEAT sx WHERE sx.venue_id = v.venue_id)')
    where_sql = 'WHERE ' + ' AND '.join(where) if where else ''
    rows = fetch_all(
        f'''
        SELECT v.venue_id::text, v.venue_name, v.capacity, v.address, v.city,
               EXISTS (SELECT 1 FROM SEAT s WHERE s.venue_id = v.venue_id) AS has_reserved_seating,
               (SELECT COUNT(*) FROM SEAT s WHERE s.venue_id = v.venue_id) AS seat_count
        FROM VENUE v
        {where_sql}
        ORDER BY v.venue_name ASC
        ''',
        params,
    )
    for row in rows:
        row['capacity_display'] = _fmt_int(row.get('capacity'))
        row['seating_label'] = 'Reserved Seating' if row.get('has_reserved_seating') else 'Free Seating'
    return rows


def venue_list(request):
    q = request.GET.get('q', '').strip()
    city = request.GET.get('city', '').strip()
    seating = request.GET.get('seating', '').strip()
    venues = _fetch_venues(q, city, seating)
    cities = fetch_all('SELECT DISTINCT city FROM VENUE ORDER BY city ASC')
    return render(request, 'venues/venue_list.html', {
        'venues': venues,
        'cities': cities,
        'q': q,
        'selected_city': city,
        'selected_seating': seating,
        'can_manage': _can_manage(request),
        'stats': {
            'total': len(venues),
            'reserved': sum(1 for v in venues if v.get('has_reserved_seating')),
            'capacity': _fmt_int(sum(int(v.get('capacity') or 0) for v in venues)),
        },
    })


def venue_partial(request):
    return render(request, 'venues/partials/venue_cards.html', {
        'venues': _fetch_venues(),
        'can_manage': _can_manage(request),
    })


@role_required('administrator', 'organizer')
def venue_create(request):
    selected = {}
    if request.method == 'POST':
        selected = {
            'venue_name': request.POST.get('venue_name', '').strip(),
            'capacity': request.POST.get('capacity', '').strip(),
            'address': request.POST.get('address', '').strip(),
            'city': request.POST.get('city', '').strip(),
        }
        try:
            if not all(selected.values()):
                raise ValueError('Seluruh field venue wajib diisi.')
            capacity = int(selected['capacity'])
            if capacity <= 0:
                raise ValueError('Kapasitas harus lebih dari 0.')
            execute_query(
                'INSERT INTO VENUE (venue_id, venue_name, capacity, address, city) VALUES (%s, %s, %s, %s, %s)',
                [str(uuid.uuid4()), selected['venue_name'], capacity, selected['address'], selected['city']],
            )
            messages.success(request, 'Venue berhasil ditambahkan. Jika venue reserved seating, tambahkan kursi di Manajemen Kursi.')
            return redirect('venues:venue_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    return render(request, 'venues/venue_form.html', {
        'form_mode': 'create',
        'selected_venue': selected,
        'venues': _fetch_venues(),
        'cities': fetch_all('SELECT DISTINCT city FROM VENUE ORDER BY city ASC'),
        'can_manage': True,
        'stats': {'total': len(_fetch_venues()), 'reserved': 0, 'capacity': '0'},
    })


@role_required('administrator', 'organizer')
def venue_edit(request, venue_id):
    venue = fetch_one(
        '''
        SELECT v.venue_id::text, v.venue_name, v.capacity, v.address, v.city,
               EXISTS (SELECT 1 FROM SEAT s WHERE s.venue_id = v.venue_id) AS has_reserved_seating
        FROM VENUE v
        WHERE v.venue_id = %s
        ''',
        [venue_id],
    )
    if not venue:
        messages.error(request, 'Venue tidak ditemukan.')
        return redirect('venues:venue_list')
    if request.method == 'POST':
        venue.update({
            'venue_name': request.POST.get('venue_name', '').strip(),
            'capacity': request.POST.get('capacity', '').strip(),
            'address': request.POST.get('address', '').strip(),
            'city': request.POST.get('city', '').strip(),
        })
        try:
            if not venue['venue_name'] or not venue['capacity'] or not venue['address'] or not venue['city']:
                raise ValueError('Seluruh field venue wajib diisi.')
            capacity = int(venue['capacity'])
            if capacity <= 0:
                raise ValueError('Kapasitas harus lebih dari 0.')
            execute_query(
                'UPDATE VENUE SET venue_name=%s, capacity=%s, address=%s, city=%s WHERE venue_id=%s',
                [venue['venue_name'], capacity, venue['address'], venue['city'], venue_id],
            )
            messages.success(request, 'Venue berhasil diperbarui.')
            return redirect('venues:venue_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    return render(request, 'venues/venue_form.html', {
        'form_mode': 'edit',
        'selected_venue': venue,
        'venues': _fetch_venues(),
        'cities': fetch_all('SELECT DISTINCT city FROM VENUE ORDER BY city ASC'),
        'can_manage': True,
        'stats': {'total': len(_fetch_venues()), 'reserved': 0, 'capacity': '0'},
    })


@role_required('administrator', 'organizer')
def venue_delete(request, venue_id):
    venue = fetch_one('SELECT venue_id::text, venue_name, city, address, capacity FROM VENUE WHERE venue_id = %s', [venue_id])
    if not venue:
        messages.error(request, 'Venue tidak ditemukan.')
        return redirect('venues:venue_list')
    if request.method == 'POST':
        try:
            execute_query('DELETE FROM VENUE WHERE venue_id = %s', [venue_id])
            messages.success(request, 'Venue berhasil dihapus.')
            return redirect('venues:venue_list')
        except (DatabaseError, ValueError) as exc: 
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    return render(request, 'venues/venue_confirm_delete.html', {
        'selected_venue': venue,
        'venues': _fetch_venues(),
        'can_manage': True,
        'stats': {'total': len(_fetch_venues()), 'reserved': 0, 'capacity': '0'},
    })


# seat views

def _fetch_seats(q='', venue_id=''):
    where = []
    params = []
    if q:
        like = f"%{q.lower()}%"
        where.append('(LOWER(s.section) LIKE %s OR LOWER(s.row_number) LIKE %s OR LOWER(s.seat_number) LIKE %s OR LOWER(v.venue_name) LIKE %s)')
        params.extend([like, like, like, like])
    if venue_id:
        where.append('s.venue_id = %s')
        params.append(venue_id)
    where_sql = 'WHERE ' + ' AND '.join(where) if where else ''
    rows = fetch_all(
        f'''
        SELECT s.seat_id::text, s.section, s.seat_number, s.row_number, s.venue_id::text,
               v.venue_name,
               CASE WHEN EXISTS (SELECT 1 FROM HAS_RELATIONSHIP hr WHERE hr.seat_id = s.seat_id)
                    THEN 'Terisi' ELSE 'Tersedia' END AS status
        FROM SEAT s
        JOIN VENUE v ON v.venue_id = s.venue_id
        {where_sql}
        ORDER BY v.venue_name ASC, s.section ASC, s.row_number ASC, s.seat_number ASC
        ''',
        params,
    )
    return rows


def _seat_stats(seats):
    return {
        'total': len(seats),
        'available': sum(1 for s in seats if s['status'] == 'Tersedia'),
        'filled': sum(1 for s in seats if s['status'] == 'Terisi'),
        'venues': len({s.get('venue_id') for s in seats}),
        'sections': len({(s.get('venue_id'), s.get('section')) for s in seats}),
    }


def seat_list(request):
    q = request.GET.get('q', '').strip()
    venue_filter = request.GET.get('venue', '').strip()
    seats = _fetch_seats(q, venue_filter)
    venues = fetch_all('SELECT venue_id::text, venue_name FROM VENUE ORDER BY venue_name ASC')
    can_manage = _can_manage(request)
    return render(request, 'venues/seat_list.html', {
        'seats': seats,
        'venues': venues,
        'q': q,
        'selected_venue_filter': venue_filter,
        'can_manage': can_manage,
        'is_readonly': not can_manage,
        'stats': _seat_stats(seats),
    })


def seat_partial(request):
    seats = _fetch_seats()
    return render(request, 'venues/partials/seat_table.html', {
        'seats': seats,
        'can_manage': _can_manage(request),
    })


@role_required('administrator', 'organizer')
def seat_create(request):
    selected = {}
    if request.method == 'POST':
        selected = {
            'venue_id': request.POST.get('venue_id', '').strip(),
            'section': request.POST.get('section', '').strip(),
            'row_number': request.POST.get('row_number', '').strip(),
            'seat_number': request.POST.get('seat_number', '').strip(),
        }
        try:
            if not all(selected.values()):
                raise ValueError('Venue, section, baris, dan nomor kursi wajib diisi.')
            execute_query(
                'INSERT INTO SEAT (seat_id, section, seat_number, row_number, venue_id) VALUES (%s, %s, %s, %s, %s)',
                [str(uuid.uuid4()), selected['section'], selected['seat_number'], selected['row_number'], selected['venue_id']],
            )
            messages.success(request, 'Kursi berhasil ditambahkan.')
            return redirect('venues:seat_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    seats = _fetch_seats()
    return render(request, 'venues/seat_form.html', {
        'form_mode': 'create',
        'selected_seat': selected,
        'seats': seats,
        'venues': fetch_all('SELECT venue_id::text, venue_name FROM VENUE ORDER BY venue_name ASC'),
        'can_manage': True,
        'stats': _seat_stats(seats),
    })


@role_required('administrator', 'organizer')
def seat_edit(request, seat_id):
    seat = fetch_one(
        '''
        SELECT s.seat_id::text, s.section, s.seat_number, s.row_number, s.venue_id::text, v.venue_name
        FROM SEAT s JOIN VENUE v ON v.venue_id = s.venue_id
        WHERE s.seat_id = %s
        ''',
        [seat_id],
    )
    if not seat:
        messages.error(request, 'Kursi tidak ditemukan.')
        return redirect('venues:seat_list')
    if request.method == 'POST':
        seat.update({
            'venue_id': request.POST.get('venue_id', '').strip(),
            'section': request.POST.get('section', '').strip(),
            'row_number': request.POST.get('row_number', '').strip(),
            'seat_number': request.POST.get('seat_number', '').strip(),
        })
        try:
            if not seat['venue_id'] or not seat['section'] or not seat['row_number'] or not seat['seat_number']:
                raise ValueError('Venue, section, baris, dan nomor kursi wajib diisi.')
            execute_query(
                'UPDATE SEAT SET venue_id=%s, section=%s, row_number=%s, seat_number=%s WHERE seat_id=%s',
                [seat['venue_id'], seat['section'], seat['row_number'], seat['seat_number'], seat_id],
            )
            messages.success(request, 'Kursi berhasil diperbarui.')
            return redirect('venues:seat_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    seats = _fetch_seats()
    return render(request, 'venues/seat_form.html', {
        'form_mode': 'edit',
        'selected_seat': seat,
        'seats': seats,
        'venues': fetch_all('SELECT venue_id::text, venue_name FROM VENUE ORDER BY venue_name ASC'),
        'can_manage': True,
        'stats': _seat_stats(seats),
    })


@role_required('administrator', 'organizer')
def seat_delete(request, seat_id):
    seat = fetch_one(
        '''
        SELECT s.seat_id::text, s.section, s.row_number, s.seat_number, v.venue_name
        FROM SEAT s JOIN VENUE v ON v.venue_id = s.venue_id
        WHERE s.seat_id = %s
        ''',
        [seat_id],
    )
    if not seat:
        messages.error(request, 'Kursi tidak ditemukan.')
        return redirect('venues:seat_list')
    if request.method == 'POST':
        try:
            execute_query('DELETE FROM SEAT WHERE seat_id = %s', [seat_id])
            messages.success(request, 'Kursi berhasil dihapus.')
            return redirect('venues:seat_list')
        except DatabaseError as exc:
            messages.error(request, db_error_message(exc))
    seats = _fetch_seats()
    return render(request, 'venues/seat_confirm_delete.html', {
        'selected_seat': seat,
        'seats': seats,
        'can_manage': True,
        'stats': _seat_stats(seats),
    })
