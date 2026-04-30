from django.shortcuts import render, redirect
from django.contrib import messages
from core.auth import login_required, role_required, has_role, get_current_user
from core.db import fetch_all, fetch_one, execute_query


def event_list(request):
    search = request.GET.get('search', '')
    venue_id = request.GET.get('venue_id', '')
    artist_id = request.GET.get('artist_id', '')
    user = get_current_user(request)

    sql = """
        SELECT DISTINCT e.*, v.venue_name, o.organizer_name
        FROM event e
        JOIN venue v ON e.venue_id = v.venue_id
        JOIN organizer o ON e.organizer_id = o.organizer_id
        LEFT JOIN event_artist ea ON e.event_id = ea.event_id
        WHERE 1=1
    """
    params = []

    if user and has_role(request, 'organizer') and not has_role(request, 'administrator'):
        org = fetch_one("SELECT organizer_id FROM organizer WHERE user_id = %s", [user['user_id']])
        if org:
            sql += " AND e.organizer_id = %s"
            params.append(org['organizer_id'])

    if search:
        sql += " AND (e.event_title ILIKE %s OR ea.artist_id IN (SELECT artist_id FROM artist WHERE name ILIKE %s))"
        params += [f'%{search}%', f'%{search}%']
    if venue_id:
        sql += " AND e.venue_id = %s"
        params.append(venue_id)
    if artist_id:
        sql += " AND ea.artist_id = %s"
        params.append(artist_id)

    sql += " ORDER BY e.event_datetime"
    events = fetch_all(sql, params)
    venues = fetch_all("SELECT venue_id, venue_name FROM venue ORDER BY venue_name")
    artists = fetch_all("SELECT artist_id, name FROM artist ORDER BY name")
    return render(request, 'events/event_list.html', {
        'events': events, 'venues': venues, 'artists': artists,
        'search': search, 'selected_venue': venue_id, 'selected_artist': artist_id
    })


def event_partial(request):
    events = fetch_all("""
        SELECT e.*, v.venue_name FROM event e
        JOIN venue v ON e.venue_id = v.venue_id ORDER BY e.event_datetime
    """)
    return render(request, 'events/partials/event_cards.html', {'events': events})


def event_detail(request, event_id):
    event = fetch_one("""
        SELECT e.*, v.venue_name, v.city, o.organizer_name
        FROM event e
        JOIN venue v ON e.venue_id = v.venue_id
        JOIN organizer o ON e.organizer_id = o.organizer_id
        WHERE e.event_id = %s
    """, [event_id])
    artists = fetch_all("""
        SELECT a.name, a.genre, ea.role FROM artist a
        JOIN event_artist ea ON a.artist_id = ea.artist_id
        WHERE ea.event_id = %s
    """, [event_id])
    categories = fetch_all(
        "SELECT * FROM ticket_category WHERE tevent_id = %s ORDER BY price DESC", [event_id]
    )
    return render(request, 'events/event_detail.html', {
        'event': event, 'artists': artists, 'categories': categories
    })


@role_required('administrator', 'organizer')
def event_create(request):
    venues = fetch_all("SELECT * FROM venue ORDER BY venue_name")
    artists = fetch_all("SELECT * FROM artist ORDER BY name")
    if request.method == 'POST':
        title = request.POST.get('event_title', '').strip()
        event_dt = request.POST.get('event_datetime', '')
        venue_id = request.POST.get('venue_id')
        artist_ids = request.POST.getlist('artist_ids')
        description = request.POST.get('description', '')
        user = get_current_user(request)
        org = fetch_one("SELECT organizer_id FROM organizer WHERE user_id = %s", [user['user_id']])
        if not org:
            messages.error(request, 'Akun anda tidak terdaftar sebagai organizer.')
            return redirect('event_list')
        event_id = None
        from core.db import fetch_one as fo
        execute_query(
            "INSERT INTO event (event_id, event_datetime, event_title, venue_id, organizer_id) VALUES (gen_random_uuid(), %s, %s, %s, %s)",
            [event_dt, title, venue_id, org['organizer_id']]
        )
        new_event = fetch_one(
            "SELECT event_id FROM event WHERE event_title = %s AND organizer_id = %s ORDER BY event_datetime DESC LIMIT 1",
            [title, org['organizer_id']]
        )
        for aid in artist_ids:
            execute_query(
                "INSERT INTO event_artist (event_id, artist_id, role) VALUES (%s, %s, %s)",
                [new_event['event_id'], aid, 'Performer']
            )
        messages.success(request, 'Event berhasil dibuat.')
        return redirect('event_list')
    return render(request, 'events/event_form.html', {'action': 'create', 'venues': venues, 'artists': artists})


@role_required('administrator', 'organizer')
def event_edit(request, event_id):
    event = fetch_one("SELECT * FROM event WHERE event_id = %s", [event_id])
    venues = fetch_all("SELECT * FROM venue ORDER BY venue_name")
    artists = fetch_all("SELECT * FROM artist ORDER BY name")
    if not event:
        return redirect('event_list')
    if request.method == 'POST':
        title = request.POST.get('event_title', '').strip()
        event_dt = request.POST.get('event_datetime', '')
        venue_id = request.POST.get('venue_id')
        execute_query(
            "UPDATE event SET event_title=%s, event_datetime=%s, venue_id=%s WHERE event_id=%s",
            [title, event_dt, venue_id, event_id]
        )
        messages.success(request, 'Event berhasil diperbarui.')
        return redirect('event_list')
    return render(request, 'events/event_form.html', {'action': 'edit', 'event': event, 'venues': venues, 'artists': artists})


def artist_list(request):
    search = request.GET.get('search', '')
    sql = "SELECT * FROM artist"
    params = []
    if search:
        sql += " WHERE name ILIKE %s OR genre ILIKE %s"
        params = [f'%{search}%', f'%{search}%']
    sql += " ORDER BY name"
    artists = fetch_all(sql, params)
    total_artists = fetch_one("SELECT COUNT(*) as count FROM artist")
    total_genres = fetch_one("SELECT COUNT(DISTINCT genre) as count FROM artist WHERE genre IS NOT NULL")
    total_in_events = fetch_one("SELECT COUNT(DISTINCT artist_id) as count FROM event_artist")
    return render(request, 'events/artist_list.html', {
        'artists': artists,
        'search': search,
        'total_artists': total_artists['count'] if total_artists else 0,
        'total_genres': total_genres['count'] if total_genres else 0,
        'total_in_events': total_in_events['count'] if total_in_events else 0,
    })


def artist_partial(request):
    artists = fetch_all("SELECT * FROM artist ORDER BY name")
    return render(request, 'events/partials/artist_table.html', {'artists': artists})


@role_required('administrator')
def artist_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        genre = request.POST.get('genre', '').strip()
        if not name:
            messages.error(request, 'Nama artist wajib diisi.')
        else:
            execute_query(
                "INSERT INTO artist (artist_id, name, genre) VALUES (gen_random_uuid(), %s, %s)",
                [name, genre or None]
            )
            messages.success(request, 'Artist berhasil ditambahkan.')
            return redirect('artist_list')
    return render(request, 'events/artist_form.html', {'action': 'create'})


@role_required('administrator')
def artist_edit(request, artist_id):
    artist = fetch_one("SELECT * FROM artist WHERE artist_id = %s", [artist_id])
    if not artist:
        return redirect('artist_list')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        genre = request.POST.get('genre', '').strip()
        if not name:
            messages.error(request, 'Nama artist wajib diisi.')
        else:
            execute_query(
                "UPDATE artist SET name=%s, genre=%s WHERE artist_id=%s",
                [name, genre or None, artist_id]
            )
            messages.success(request, 'Artist berhasil diperbarui.')
            return redirect('artist_list')
    return render(request, 'events/artist_form.html', {'action': 'edit', 'artist': artist})


@role_required('administrator')
def artist_delete(request, artist_id):
    artist = fetch_one("SELECT * FROM artist WHERE artist_id = %s", [artist_id])
    if not artist:
        return redirect('artist_list')
    if request.method == 'POST':
        execute_query("DELETE FROM artist WHERE artist_id = %s", [artist_id])
        messages.success(request, 'Artist berhasil dihapus.')
        return redirect('artist_list')
    return render(request, 'events/artist_confirm_delete.html', {'artist': artist})
