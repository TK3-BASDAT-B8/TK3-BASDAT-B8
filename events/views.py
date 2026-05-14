import uuid

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import redirect, render

from core.auth import login_required, page_role, role_required
from core.db import db_error_message, execute_query, fetch_all, fetch_one


def _can_manage_events(request):
    return page_role(request) in ['admin', 'organizer']


def _current_organizer_id(request):
    user = request.session.get('user') or {}
    return user.get('organizer_id')


def _format_dt(value):
    return str(value or '')[:16]


def _fmt_money(value):
    try:
        return f"{float(value):,.0f}".replace(',', '.')
    except (TypeError, ValueError):
        return '0'


def _fetch_events(request, q='', venue_id='', artist_id=''):
    role = page_role(request)
    organizer_id = _current_organizer_id(request)
    where = ['1=1']
    params = []

    if role == 'organizer' and organizer_id:
        where.append('e.organizer_id = %s')
        params.append(organizer_id)
    if q:
        like = f"%{q.lower()}%"
        where.append(
            "(LOWER(e.event_title) LIKE %s OR EXISTS ("
            "SELECT 1 FROM EVENT_ARTIST qea "
            "JOIN ARTIST qa ON qa.artist_id = qea.artist_id "
            "WHERE qea.event_id = e.event_id AND LOWER(qa.name) LIKE %s))"
        )
        params.extend([like, like])
    if venue_id:
        where.append('e.venue_id = %s')
        params.append(venue_id)
    if artist_id:
        where.append('EXISTS (SELECT 1 FROM EVENT_ARTIST fea WHERE fea.event_id = e.event_id AND fea.artist_id = %s)')
        params.append(artist_id)

    rows = fetch_all(
        f'''
        SELECT e.event_id::text, e.event_title, e.event_datetime,
               v.venue_id::text, v.venue_name,
               EXISTS (SELECT 1 FROM SEAT sx WHERE sx.venue_id = v.venue_id) AS has_reserved_seating,
               o.organizer_id::text, o.organizer_name,
               COALESCE(MIN(tc.price), 0) AS min_price,
               COALESCE(array_agg(DISTINCT a.name ORDER BY a.name) FILTER (WHERE a.name IS NOT NULL), ARRAY[]::varchar[]) AS performers
        FROM EVENT e
        JOIN VENUE v ON e.venue_id = v.venue_id
        JOIN ORGANIZER o ON e.organizer_id = o.organizer_id
        LEFT JOIN EVENT_ARTIST ea ON ea.event_id = e.event_id
        LEFT JOIN ARTIST a ON a.artist_id = ea.artist_id
        LEFT JOIN TICKET_CATEGORY tc ON tc.tevent_id = e.event_id
        WHERE {' AND '.join(where)}
        GROUP BY e.event_id, e.event_title, e.event_datetime,
                 v.venue_id, v.venue_name,
                 o.organizer_id, o.organizer_name
        ORDER BY e.event_datetime DESC
        ''',
        params,
    )
    if not rows:
        return []

    event_ids = [r['event_id'] for r in rows]
    placeholders = ','.join(['%s'] * len(event_ids))
    cats = fetch_all(
        f'''
        SELECT category_id::text, tevent_id::text AS event_id, category_name, quota, price
        FROM TICKET_CATEGORY
        WHERE tevent_id IN ({placeholders})
        ORDER BY price ASC, category_name ASC
        ''',
        event_ids,
    )
    by_event = {}
    for cat in cats:
        cat['price_display'] = _fmt_money(cat.get('price'))
        by_event.setdefault(cat['event_id'], []).append(cat)

    for row in rows:
        row['event_datetime_display'] = _format_dt(row['event_datetime'])
        row['min_price_display'] = _fmt_money(row.get('min_price'))
        row['ticket_categories'] = by_event.get(row['event_id'], [])
    return rows


def _event_options(request):
    role = page_role(request)
    organizer_id = _current_organizer_id(request)
    organizers = fetch_all('SELECT organizer_id::text, organizer_name FROM ORGANIZER ORDER BY organizer_name ASC')
    if role == 'organizer' and organizer_id:
        organizers = [o for o in organizers if o['organizer_id'] == organizer_id]
    return {
        'venues': fetch_all(
            '''
            SELECT v.venue_id::text, v.venue_name, v.capacity,
                   EXISTS (SELECT 1 FROM SEAT s WHERE s.venue_id = v.venue_id) AS has_reserved_seating
            FROM VENUE v
            ORDER BY v.venue_name ASC
            '''
        ),
        'organizers': organizers,
        'artists': fetch_all('SELECT artist_id::text, name, genre FROM ARTIST ORDER BY name ASC'),
        'venue_filters': fetch_all('SELECT venue_id::text, venue_name FROM VENUE ORDER BY venue_name ASC'),
        'artist_filters': fetch_all('SELECT artist_id::text, name FROM ARTIST ORDER BY name ASC'),
    }


def _event_context(request, events=None, **extra):
    if events is None:
        events = _fetch_events(request)
    role = page_role(request)
    ctx = {
        'events': events,
        'can_manage': _can_manage_events(request),
        'page_role': role,
        'page_title': 'Event Saya' if role == 'organizer' else ('Manajemen Event' if role == 'admin' else 'Jelajahi Acara'),
        'q': request.GET.get('q', ''),
        'selected_venue': request.GET.get('venue', ''),
        'selected_artist': request.GET.get('artist', ''),
    }
    ctx.update(_event_options(request))
    ctx.update(extra)
    return ctx


def _selected_artist_ids(event_id):
    return [r['artist_id'] for r in fetch_all('SELECT artist_id::text FROM EVENT_ARTIST WHERE event_id = %s', [event_id])]


def _category_rows(event_id):
    rows = fetch_all(
        '''
        SELECT tc.category_id::text, tc.category_name, tc.price, tc.quota,
               COUNT(t.ticket_id) AS used
        FROM TICKET_CATEGORY tc
        LEFT JOIN TICKET t ON t.tcategory_id = tc.category_id
        WHERE tc.tevent_id = %s
        GROUP BY tc.category_id, tc.category_name, tc.price, tc.quota
        ORDER BY tc.price ASC, tc.category_name ASC
        ''',
        [event_id],
    )
    for row in rows:
        row['price_display'] = _fmt_money(row.get('price'))
    return rows


def _parse_categories(post):
    ids = post.getlist('category_id')
    names = post.getlist('category_name')
    prices = post.getlist('category_price')
    quotas = post.getlist('category_quota')
    rows = []
    max_len = max(len(names), len(prices), len(quotas), len(ids), 0)
    for idx in range(max_len):
        name = names[idx].strip() if idx < len(names) else ''
        if not name:
            continue
        price_text = prices[idx].strip() if idx < len(prices) else ''
        quota_text = quotas[idx].strip() if idx < len(quotas) else ''
        cid = ids[idx].strip() if idx < len(ids) else ''
        try:
            price = float(price_text)
            quota = int(quota_text)
        except ValueError:
            raise ValueError('Harga dan kuota kategori tiket wajib berupa angka.')
        if quota <= 0:
            raise ValueError('Kuota kategori tiket wajib lebih dari 0.')
        if price < 0:
            raise ValueError('Harga kategori tiket tidak boleh negatif.')
        rows.append({'category_id': cid, 'category_name': name, 'price': price, 'quota': quota})
    if not rows:
        raise ValueError('Minimal satu kategori tiket wajib diisi.')
    return rows


def _validate_total_quota(venue_id, categories):
    venue = fetch_one('SELECT capacity FROM VENUE WHERE venue_id = %s', [venue_id])
    if not venue:
        raise ValueError('Venue tidak ditemukan.')
    total_quota = sum(row['quota'] for row in categories)
    if total_quota > int(venue['capacity']):
        raise ValueError('Total kuota kategori tiket tidak boleh melebihi kapasitas venue.')


def _sync_event_artists(event_id, artist_ids):
    execute_query('DELETE FROM EVENT_ARTIST WHERE event_id = %s', [event_id])
    for artist_id in artist_ids:
        execute_query(
            'INSERT INTO EVENT_ARTIST (event_id, artist_id, role) VALUES (%s, %s, %s)',
            [event_id, artist_id, 'Performer'],
        )


def _sync_event_categories(event_id, categories):
    existing = fetch_all('SELECT category_id::text FROM TICKET_CATEGORY WHERE tevent_id = %s', [event_id])
    existing_ids = {row['category_id'] for row in existing}
    kept_ids = set()
    for row in categories:
        cid = row['category_id']
        if cid:
            used = fetch_one('SELECT COUNT(*) AS used FROM TICKET WHERE tcategory_id = %s', [cid])
            if used and int(used['used']) > row['quota']:
                raise ValueError(f"Kuota {row['category_name']} tidak boleh lebih kecil dari tiket terjual.")
            execute_query(
                'UPDATE TICKET_CATEGORY SET category_name=%s, price=%s, quota=%s WHERE category_id=%s AND tevent_id=%s',
                [row['category_name'], row['price'], row['quota'], cid, event_id],
            )
            kept_ids.add(cid)
        else:
            new_id = str(uuid.uuid4())
            execute_query(
                'INSERT INTO TICKET_CATEGORY (category_id, category_name, quota, price, tevent_id) VALUES (%s, %s, %s, %s, %s)',
                [new_id, row['category_name'], row['quota'], row['price'], event_id],
            )
            kept_ids.add(new_id)
    for cid in existing_ids - kept_ids:
        execute_query('DELETE FROM TICKET_CATEGORY WHERE category_id = %s', [cid])


def _event_from_post(request):
    event_date = request.POST.get('event_date', '').strip()
    event_time = request.POST.get('event_time', '').strip()
    organizer_id = request.POST.get('organizer_id', '').strip()
    if page_role(request) == 'organizer':
        organizer_id = _current_organizer_id(request)
    if not organizer_id:
        raise ValueError('Organizer wajib dipilih.')
    if not event_date or not event_time:
        raise ValueError('Tanggal dan waktu acara wajib diisi.')
    return {
        'event_title': request.POST.get('event_title', '').strip(),
        'event_date': event_date,
        'event_time': event_time,
        'event_datetime': f'{event_date} {event_time}:00',
        'venue_id': request.POST.get('venue_id', '').strip(),
        'organizer_id': organizer_id,
    }


def event_list(request):
    events = _fetch_events(
        request,
        request.GET.get('q', '').strip(),
        request.GET.get('venue', '').strip(),
        request.GET.get('artist', '').strip(),
    )
    return render(request, 'events/event_list.html', _event_context(request, events))


def event_partial(request):
    return render(request, 'events/partials/event_cards.html', _event_context(request))


def event_detail(request, event_id):
    event = fetch_one(
        '''
        SELECT e.event_id::text, e.event_title, e.event_datetime,
               v.venue_name, o.organizer_name
        FROM EVENT e
        JOIN VENUE v ON v.venue_id = e.venue_id
        JOIN ORGANIZER o ON o.organizer_id = e.organizer_id
        WHERE e.event_id = %s
        ''',
        [event_id],
    )
    if not event:
        messages.error(request, 'Event tidak ditemukan.')
        return redirect('events:event_list')
    event['performers'] = [
        r['name'] for r in fetch_all(
            'SELECT a.name FROM ARTIST a JOIN EVENT_ARTIST ea ON ea.artist_id = a.artist_id WHERE ea.event_id = %s ORDER BY a.name ASC',
            [event_id],
        )
    ]
    event['ticket_categories'] = _category_rows(event_id)
    event['event_datetime_display'] = _format_dt(event['event_datetime'])
    return render(request, 'events/event_detail.html', {'event': event, 'can_manage': _can_manage_events(request)})


@role_required('administrator', 'organizer')
def event_create(request):
    selected_event = {}
    selected_artist_ids = []
    categories = [{'category_id': '', 'category_name': '', 'price': '', 'quota': ''}]
    if request.method == 'POST':
        try:
            selected_event = _event_from_post(request)
            selected_artist_ids = request.POST.getlist('artist_ids')
            categories = _parse_categories(request.POST)
            if not selected_event['event_title'] or not selected_event['venue_id']:
                raise ValueError('Judul acara dan venue wajib diisi.')
            _validate_total_quota(selected_event['venue_id'], categories)
            with transaction.atomic():
                event_id = str(uuid.uuid4())
                execute_query(
                    'INSERT INTO EVENT (event_id, event_title, event_datetime, venue_id, organizer_id) VALUES (%s, %s, %s, %s, %s)',
                    [event_id, selected_event['event_title'], selected_event['event_datetime'], selected_event['venue_id'], selected_event['organizer_id']],
                )
                _sync_event_artists(event_id, selected_artist_ids)
                _sync_event_categories(event_id, categories)
            messages.success(request, 'Event berhasil dibuat.')
            return redirect('events:event_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))

    return render(request, 'events/event_form.html', _event_context(
        request,
        form_mode='create',
        selected_event=selected_event,
        selected_artist_ids=selected_artist_ids,
        category_rows=categories,
    ))


@role_required('administrator', 'organizer')
def event_edit(request, event_id):
    event = fetch_one(
        '''
        SELECT e.event_id::text, e.event_title, e.event_datetime,
               e.venue_id::text, e.organizer_id::text
        FROM EVENT e WHERE e.event_id = %s
        ''',
        [event_id],
    )
    if not event:
        messages.error(request, 'Event tidak ditemukan.')
        return redirect('events:event_list')
    if page_role(request) == 'organizer' and event['organizer_id'] != _current_organizer_id(request):
        messages.error(request, 'Organizer hanya dapat mengubah event miliknya sendiri.')
        return redirect('events:event_list')

    dt_text = _format_dt(event['event_datetime'])
    event['event_date'] = dt_text[:10]
    event['event_time'] = dt_text[11:16]
    selected_artist_ids = _selected_artist_ids(event_id)
    categories = _category_rows(event_id)

    if request.method == 'POST':
        try:
            event.update(_event_from_post(request))
            selected_artist_ids = request.POST.getlist('artist_ids')
            categories = _parse_categories(request.POST)
            if not event['event_title'] or not event['venue_id']:
                raise ValueError('Judul acara dan venue wajib diisi.')
            _validate_total_quota(event['venue_id'], categories)
            with transaction.atomic():
                execute_query(
                    'UPDATE EVENT SET event_title=%s, event_datetime=%s, venue_id=%s, organizer_id=%s WHERE event_id=%s',
                    [event['event_title'], event['event_datetime'], event['venue_id'], event['organizer_id'], event_id],
                )
                _sync_event_artists(event_id, selected_artist_ids)
                _sync_event_categories(event_id, categories)
            messages.success(request, 'Event berhasil diperbarui.')
            return redirect('events:event_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))

    return render(request, 'events/event_form.html', _event_context(
        request,
        form_mode='edit',
        selected_event=event,
        selected_artist_ids=selected_artist_ids,
        category_rows=categories,
    ))


@login_required
def artist_list(request):
    search = request.GET.get('search', '').strip()
    where = ''
    params = []
    if search:
        where = "WHERE LOWER(name) LIKE %s OR LOWER(COALESCE(genre, '')) LIKE %s"
        like = f"%{search.lower()}%"
        params = [like, like]
    artists = fetch_all(f'SELECT artist_id::text, name, genre FROM ARTIST {where} ORDER BY name ASC', params)
    return render(request, 'events/artist_list.html', {
        'artists': artists,
        'search': search,
        'can_manage': page_role(request) == 'admin',
        'total_artists': len(artists),
        'total_genres': len({a.get('genre') for a in artists if a.get('genre')}),
        'total_in_events': (fetch_one('SELECT COUNT(DISTINCT artist_id) AS count FROM EVENT_ARTIST') or {}).get('count', 0),
    })


@login_required
def artist_partial(request):
    artists = fetch_all('SELECT artist_id::text, name, genre FROM ARTIST ORDER BY name ASC')
    return render(request, 'events/partials/artist_table.html', {'artists': artists, 'can_manage': page_role(request) == 'admin'})


@role_required('administrator')
def artist_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        genre = request.POST.get('genre', '').strip()
        try:
            if not name:
                raise ValueError('Name wajib diisi.')
            execute_query('INSERT INTO ARTIST (artist_id, name, genre) VALUES (%s, %s, %s)', [str(uuid.uuid4()), name, genre or None])
            messages.success(request, 'Artist berhasil ditambahkan.')
            return redirect('events:artist_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    return render(request, 'events/artist_form.html', {'action': 'create'})


@role_required('administrator')
def artist_edit(request, artist_id):
    artist = fetch_one('SELECT artist_id::text, name, genre FROM ARTIST WHERE artist_id = %s', [artist_id])
    if not artist:
        messages.error(request, 'Artist tidak ditemukan.')
        return redirect('events:artist_list')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        genre = request.POST.get('genre', '').strip()
        try:
            if not name:
                raise ValueError('Name wajib diisi.')
            execute_query('UPDATE ARTIST SET name=%s, genre=%s WHERE artist_id=%s', [name, genre or None, artist_id])
            messages.success(request, 'Artist berhasil diperbarui.')
            return redirect('events:artist_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))
    return render(request, 'events/artist_form.html', {'action': 'edit', 'artist': artist})


@role_required('administrator')
def artist_delete(request, artist_id):
    artist = fetch_one('SELECT artist_id::text, name, genre FROM ARTIST WHERE artist_id = %s', [artist_id])
    if not artist:
        messages.error(request, 'Artist tidak ditemukan.')
        return redirect('events:artist_list')
    if request.method == 'POST':
        try:
            execute_query('DELETE FROM ARTIST WHERE artist_id = %s', [artist_id])
            messages.success(request, 'Artist berhasil dihapus.')
            return redirect('events:artist_list')
        except DatabaseError as exc:
            messages.error(request, db_error_message(exc))
    return render(request, 'events/artist_confirm_delete.html', {'artist': artist})
