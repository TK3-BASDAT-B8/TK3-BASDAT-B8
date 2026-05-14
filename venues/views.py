from django.urls import reverse
import uuid

from django.contrib import messages
from django.db import DatabaseError
from django.shortcuts import redirect, render

from core.auth import get_current_user, role_required, page_role
from core.db import db_error_message, execute_query, fetch_all, fetch_one


# =========================================================
# SEAT DUMMY DATA
# =========================================================

FILLED_SEAT_IDS = {
    "00000000-0000-0000-0000-000000000001",
    "00000000-0000-0000-0000-000000000002",
    "00000000-0000-0000-0000-000000000003",
    "00000000-0000-0000-0000-000000000004",
    "00000000-0000-0000-0000-000000000005",
    "00000000-0000-0000-0000-000000000006",
    "00000000-0000-0000-0000-000000000007",
    "00000000-0000-0000-0000-000000000008",
    "00000000-0000-0000-0000-000000000009",
    "00000000-0000-0000-0000-000000000010",
}

RAW_DUMMY_SEATS = [
    ("00000000-0000-0000-0000-000000000001", "WVIP", "1", "A", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000002", "WVIP", "2", "A", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000003", "WVIP", "3", "A", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000004", "WVIP", "4", "A", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000005", "WVIP", "5", "A", "11111111-1111-1111-1111-111111111111"),

    ("00000000-0000-0000-0000-000000000006", "VIP", "1", "B", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000007", "VIP", "2", "B", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000008", "VIP", "3", "B", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000009", "VIP", "4", "B", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000010", "VIP", "5", "B", "11111111-1111-1111-1111-111111111111"),

    ("00000000-0000-0000-0000-000000000011", "REGULER", "1", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000012", "REGULER", "2", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000013", "REGULER", "3", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000014", "REGULER", "4", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000015", "REGULER", "5", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000016", "REGULER", "6", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000017", "REGULER", "7", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000018", "REGULER", "8", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000019", "REGULER", "9", "C", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000020", "REGULER", "10", "C", "11111111-1111-1111-1111-111111111111"),

    ("00000000-0000-0000-0000-000000000021", "FESTIVAL", "1", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000022", "FESTIVAL", "2", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000023", "FESTIVAL", "3", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000024", "FESTIVAL", "4", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000025", "FESTIVAL", "5", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000026", "FESTIVAL", "6", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000027", "FESTIVAL", "7", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000028", "FESTIVAL", "8", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000029", "FESTIVAL", "9", "D", "11111111-1111-1111-1111-111111111111"),
    ("00000000-0000-0000-0000-000000000030", "FESTIVAL", "10", "D", "11111111-1111-1111-1111-111111111111"),
]


def _build_dummy_seats():
    venue_map = {venue["venue_id"]: venue["venue_name"] for venue in DUMMY_VENUES}
    seats = []

    for seat_id, section, seat_number, row_number, venue_id in RAW_DUMMY_SEATS:
        seats.append({
            "seat_id": seat_id,
            "section": section,
            "seat_number": seat_number,
            "row_number": row_number,
            "venue_id": venue_id,
            "venue_name": venue_map.get(venue_id, "-"),
            "status": "Terisi" if seat_id in FILLED_SEAT_IDS else "Tersedia",
        })

    return seats


DUMMY_SEATS = _build_dummy_seats()


def _seat_stats(seats):
    return {
        "total": len(seats),
        "available": len([seat for seat in seats if seat["status"] == "Tersedia"]),
        "filled": len([seat for seat in seats if seat["status"] == "Terisi"]),
    }


def _find_seat(seat_id):
    for seat in DUMMY_SEATS:
        if str(seat["seat_id"]) == str(seat_id):
            return seat
    return None


def _get_seat_page_role(request):
    role = request.GET.get("role", "admin").strip().lower()

    if role in ["admin", "administrator"]:
        return "admin"
    if role == "organizer":
        return "organizer"
    if role == "customer":
        return "customer"
    return "admin"


def _redirect_seat_list_with_role(page_role):
    url = reverse("seat_list")
    return redirect(f"{url}?role={page_role}")


def _seat_context(request, seats):
    page_role = _get_seat_page_role(request)
    can_manage_seat = page_role in ["admin", "organizer"]

    return {
        "seats": seats,
        "venues": DUMMY_VENUES,
        "stats": _seat_stats(seats),
        "page_role": page_role,
        "page_title": "Manajemen Kursi" if can_manage_seat else "Daftar Kursi",
        "page_subtitle": (
            "Kelola kursi dan denah tempat duduk venue"
            if can_manage_seat
            else "Lihat daftar kursi dan status ketersediaannya"
        ),
        "can_create_seat": can_manage_seat,
        "can_manage_seat": can_manage_seat,
        "user_role": "administrator" if page_role == "admin" else page_role,
    }


def seat_list(request):
    q = request.GET.get("q", "").strip().lower()
    venue = request.GET.get("venue", "").strip()

    filtered_seats = DUMMY_SEATS

    if q:
        filtered_seats = [
            seat for seat in filtered_seats
            if q in seat["section"].lower()
            or q in seat["row_number"].lower()
            or q in seat["seat_number"].lower()
            or q in seat["venue_name"].lower()
        ]

    if venue:
        filtered_seats = [
            seat for seat in filtered_seats
            if seat["venue_id"] == venue
        ]

    return render(request, "venues/seat_list.html", _seat_context(request, filtered_seats))


def seat_partial(request):
    return render(request, "venues/partials/seat_table.html", _seat_context(request, DUMMY_SEATS))


def seat_create(request):
    page_role = _get_seat_page_role(request)

    if page_role not in ["admin", "organizer"]:
        messages.error(request, "Hanya Admin atau Organizer yang dapat menambahkan kursi.")
        return _redirect_seat_list_with_role(page_role)

    if request.method == "POST":
        messages.success(request, "Kursi berhasil ditambahkan. Ini masih dummy frontend.")
        return _redirect_seat_list_with_role(page_role)

    context = _seat_context(request, DUMMY_SEATS)
    context.update({
        "form_mode": "create",
        "selected_seat": {},
    })

    return render(request, "venues/seat_form.html", context)


def seat_edit(request, seat_id):
    page_role = _get_seat_page_role(request)

    if page_role not in ["admin", "organizer"]:
        messages.error(request, "Hanya Admin atau Organizer yang dapat mengubah kursi.")
        return _redirect_seat_list_with_role(page_role)

    selected_seat = _find_seat(seat_id)

    if not selected_seat:
        messages.error(request, "Kursi tidak ditemukan.")
        return _redirect_seat_list_with_role(page_role)

    if request.method == "POST":
        messages.success(request, "Kursi berhasil diperbarui. Ini masih dummy frontend.")
        return _redirect_seat_list_with_role(page_role)

    context = _seat_context(request, DUMMY_SEATS)
    context.update({
        "form_mode": "edit",
        "selected_seat": selected_seat,
    })

    return render(request, "venues/seat_form.html", context)


def seat_delete(request, seat_id):
    page_role = _get_seat_page_role(request)

    if page_role not in ["admin", "organizer"]:
        messages.error(request, "Hanya Admin atau Organizer yang dapat menghapus kursi.")
        return _redirect_seat_list_with_role(page_role)

    selected_seat = _find_seat(seat_id)

    if not selected_seat:
        messages.error(request, "Kursi tidak ditemukan.")
        return _redirect_seat_list_with_role(page_role)

    if selected_seat["status"] == "Terisi":
        messages.error(request, "Kursi ini sudah di-assign ke tiket dan tidak dapat dihapus.")
        return _redirect_seat_list_with_role(page_role)

    if request.method == "POST":
        messages.success(request, "Kursi berhasil dihapus. Ini masih dummy frontend.")
        return _redirect_seat_list_with_role(page_role)

    context = _seat_context(request, DUMMY_SEATS)
    context.update({
        "selected_seat": selected_seat,
    })

    return render(request, "venues/seat_confirm_delete.html", context)



def _can_manage(request):
    user = get_current_user(request)
    return bool(user and user.get('role') in ['administrator', 'organizer'])


def _fmt_int(value):
    try:
        return f"{int(value):,}".replace(',', '.')
    except (TypeError, ValueError):
        return '0'


# ============================================================
# VENUE
# ============================================================

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
        except DatabaseError as exc:
            messages.error(request, db_error_message(exc))
    return render(request, 'venues/venue_confirm_delete.html', {
        'selected_venue': venue,
        'venues': _fetch_venues(),
        'can_manage': True,
        'stats': {'total': len(_fetch_venues()), 'reserved': 0, 'capacity': '0'},
    })