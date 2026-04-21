from django.shortcuts import render, redirect
from django.contrib import messages
from core.auth import login_required, role_required
from core.db import fetch_all, fetch_one, execute_query


def venue_list(request):
    search = request.GET.get('search', '')
    city = request.GET.get('city', '')
    sql = "SELECT * FROM venue WHERE 1=1"
    params = []
    if search:
        sql += " AND (venue_name ILIKE %s OR address ILIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    if city:
        sql += " AND city = %s"
        params.append(city)
    sql += " ORDER BY venue_name"
    venues = fetch_all(sql, params)
    cities = fetch_all("SELECT DISTINCT city FROM venue ORDER BY city")
    return render(request, 'venues/venue_list.html', {'venues': venues, 'cities': cities, 'search': search, 'selected_city': city})


def venue_partial(request):
    venues = fetch_all("SELECT * FROM venue ORDER BY venue_name")
    return render(request, 'venues/partials/venue_table.html', {'venues': venues})


@role_required('administrator', 'organizer')
def venue_create(request):
    if request.method == 'POST':
        name = request.POST.get('venue_name', '').strip()
        capacity = request.POST.get('capacity', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        if not all([name, capacity, address, city]):
            messages.error(request, 'Semua field wajib diisi.')
        else:
            execute_query(
                "INSERT INTO venue (venue_id, venue_name, capacity, address, city) VALUES (gen_random_uuid(), %s, %s, %s, %s)",
                [name, int(capacity), address, city]
            )
            messages.success(request, 'Venue berhasil ditambahkan.')
            return redirect('venue_list')
    return render(request, 'venues/venue_form.html', {'action': 'create'})


@role_required('administrator', 'organizer')
def venue_edit(request, venue_id):
    venue = fetch_one("SELECT * FROM venue WHERE venue_id = %s", [venue_id])
    if not venue:
        return redirect('venue_list')
    if request.method == 'POST':
        name = request.POST.get('venue_name', '').strip()
        capacity = request.POST.get('capacity', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        execute_query(
            "UPDATE venue SET venue_name=%s, capacity=%s, address=%s, city=%s WHERE venue_id=%s",
            [name, int(capacity), address, city, venue_id]
        )
        messages.success(request, 'Venue berhasil diperbarui.')
        return redirect('venue_list')
    return render(request, 'venues/venue_form.html', {'action': 'edit', 'venue': venue})


@role_required('administrator', 'organizer')
def venue_delete(request, venue_id):
    venue = fetch_one("SELECT * FROM venue WHERE venue_id = %s", [venue_id])
    if not venue:
        return redirect('venue_list')
    if request.method == 'POST':
        execute_query("DELETE FROM venue WHERE venue_id = %s", [venue_id])
        messages.success(request, 'Venue berhasil dihapus.')
        return redirect('venue_list')
    return render(request, 'venues/venue_confirm_delete.html', {'venue': venue})


@login_required
def seat_list(request):
    seats = fetch_all("""
        SELECT s.*, v.venue_name,
               CASE WHEN hr.seat_id IS NOT NULL THEN 'Terisi' ELSE 'Tersedia' END AS status
        FROM seat s
        JOIN venue v ON s.venue_id = v.venue_id
        LEFT JOIN has_relationship hr ON s.seat_id = hr.seat_id
        ORDER BY v.venue_name, s.section, s.row_number, s.seat_number
    """)
    venues = fetch_all("SELECT * FROM venue ORDER BY venue_name")
    return render(request, 'venues/seat_list.html', {'seats': seats, 'venues': venues})


def seat_partial(request):
    seats = fetch_all("""
        SELECT s.*, v.venue_name,
               CASE WHEN hr.seat_id IS NOT NULL THEN 'Terisi' ELSE 'Tersedia' END AS status
        FROM seat s
        JOIN venue v ON s.venue_id = v.venue_id
        LEFT JOIN has_relationship hr ON s.seat_id = hr.seat_id
        ORDER BY v.venue_name, s.section, s.row_number, s.seat_number
    """)
    return render(request, 'venues/partials/seat_table.html', {'seats': seats})


@role_required('administrator', 'organizer')
def seat_create(request):
    venues = fetch_all("SELECT * FROM venue ORDER BY venue_name")
    if request.method == 'POST':
        venue_id = request.POST.get('venue_id')
        section = request.POST.get('section', '').strip()
        row_number = request.POST.get('row_number', '').strip()
        seat_number = request.POST.get('seat_number', '').strip()
        if not all([venue_id, section, row_number, seat_number]):
            messages.error(request, 'Semua field wajib diisi.')
        else:
            execute_query(
                "INSERT INTO seat (seat_id, section, seat_number, row_number, venue_id) VALUES (gen_random_uuid(), %s, %s, %s, %s)",
                [section, seat_number, row_number, venue_id]
            )
            messages.success(request, 'Kursi berhasil ditambahkan.')
            return redirect('seat_list')
    return render(request, 'venues/seat_form.html', {'action': 'create', 'venues': venues})


@role_required('administrator', 'organizer')
def seat_edit(request, seat_id):
    seat = fetch_one("SELECT * FROM seat WHERE seat_id = %s", [seat_id])
    venues = fetch_all("SELECT * FROM venue ORDER BY venue_name")
    if not seat:
        return redirect('seat_list')
    if request.method == 'POST':
        venue_id = request.POST.get('venue_id')
        section = request.POST.get('section', '').strip()
        row_number = request.POST.get('row_number', '').strip()
        seat_number = request.POST.get('seat_number', '').strip()
        execute_query(
            "UPDATE seat SET section=%s, row_number=%s, seat_number=%s, venue_id=%s WHERE seat_id=%s",
            [section, row_number, seat_number, venue_id, seat_id]
        )
        messages.success(request, 'Kursi berhasil diperbarui.')
        return redirect('seat_list')
    return render(request, 'venues/seat_form.html', {'action': 'edit', 'seat': seat, 'venues': venues})


@role_required('administrator', 'organizer')
def seat_delete(request, seat_id):
    assigned = fetch_one("SELECT seat_id FROM has_relationship WHERE seat_id = %s", [seat_id])
    if assigned:
        messages.error(request, 'Kursi ini sudah di-assign ke tiket dan tidak dapat dihapus.')
        return redirect('seat_list')
    seat = fetch_one("SELECT * FROM seat WHERE seat_id = %s", [seat_id])
    if request.method == 'POST':
        execute_query("DELETE FROM seat WHERE seat_id = %s", [seat_id])
        messages.success(request, 'Kursi berhasil dihapus.')
        return redirect('seat_list')
    return render(request, 'venues/seat_confirm_delete.html', {'seat': seat})
