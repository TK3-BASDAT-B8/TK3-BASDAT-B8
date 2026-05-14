import uuid

from django.contrib import messages
from django.db import DatabaseError, transaction
from django.shortcuts import redirect, render

from core.auth import page_role, role_required
from core.db import db_error_message, execute_query, fetch_all, fetch_one

DISCOUNT_TYPES = ['PERCENTAGE', 'NOMINAL']


def _promotion_context(request):
    role = page_role(request)
    search = request.GET.get('q', '').strip()
    discount_type = request.GET.get('type', 'all').strip().upper()

    where = ['1=1']
    params = []
    if search:
        where.append('LOWER(p.promo_code) LIKE LOWER(%s)')
        params.append(f'%{search}%')
    if discount_type in DISCOUNT_TYPES:
        where.append('p.discount_type = %s')
        params.append(discount_type)

    promotions = fetch_all(
        f'''
        SELECT p.promotion_id::text, p.promo_code, p.discount_type,
               p.discount_value, p.start_date, p.end_date, p.usage_limit,
               COUNT(op.order_promotion_id)::int AS used
        FROM PROMOTION p
        LEFT JOIN ORDER_PROMOTION op ON op.promotion_id = p.promotion_id
        WHERE {' AND '.join(where)}
        GROUP BY p.promotion_id, p.promo_code, p.discount_type,
                 p.discount_value, p.start_date, p.end_date, p.usage_limit
        ORDER BY p.promo_code ASC
        ''',
        params,
    )

    stats = fetch_one(
        '''
        SELECT COUNT(*)::int AS total_promos,
               COALESCE((SELECT COUNT(*) FROM ORDER_PROMOTION), 0)::int AS total_usage,
               COUNT(*) FILTER (WHERE discount_type = 'PERCENTAGE')::int AS total_percentage
        FROM PROMOTION
        '''
    ) or {}

    return {
        'role': role,
        'promotions': promotions,
        'search': search,
        'filter_type': discount_type if discount_type in DISCOUNT_TYPES else 'all',
        'discount_types': DISCOUNT_TYPES,
        'total_promos': stats.get('total_promos', 0) or 0,
        'total_usage': stats.get('total_usage', 0) or 0,
        'total_percentage': stats.get('total_percentage', 0) or 0,
    }


def _promotion_from_post(request, existing=None):
    promo = dict(existing or {})
    promo.update({
        'promo_code': request.POST.get('promo_code', '').strip().upper(),
        'discount_type': request.POST.get('discount_type', '').strip().upper(),
        'discount_value': request.POST.get('discount_value', '').strip(),
        'start_date': request.POST.get('start_date', '').strip(),
        'end_date': request.POST.get('end_date', '').strip(),
        'usage_limit': request.POST.get('usage_limit', '').strip(),
    })
    return promo


def _validate_promotion_payload(promo):
    if not promo['promo_code']:
        raise ValueError('Kode promo wajib diisi.')
    if promo['discount_type'] not in DISCOUNT_TYPES:
        raise ValueError('Tipe diskon harus PERCENTAGE atau NOMINAL.')
    try:
        discount_value = float(promo['discount_value'])
    except (TypeError, ValueError):
        raise ValueError('Nilai diskon harus berupa angka.')
    if discount_value <= 0:
        raise ValueError('Nilai diskon harus lebih dari 0.')
    try:
        usage_limit = int(promo['usage_limit'])
    except (TypeError, ValueError):
        raise ValueError('Batas penggunaan harus berupa bilangan bulat.')
    if usage_limit <= 0:
        raise ValueError('Batas penggunaan harus lebih dari 0.')
    if not promo['start_date'] or not promo['end_date']:
        raise ValueError('Tanggal mulai dan tanggal berakhir wajib diisi.')
    if promo['end_date'] < promo['start_date']:
        raise ValueError('Tanggal berakhir harus sama dengan atau setelah tanggal mulai.')
    return promo['promo_code'], promo['discount_type'], discount_value, promo['start_date'], promo['end_date'], usage_limit


def promotion_list(request):
    return render(request, 'promotions/promotion_list.html', _promotion_context(request))


@role_required('administrator')
def promotion_create(request):
    promotion = {}
    if request.method == 'POST':
        promotion = _promotion_from_post(request)
        try:
            promo_code, discount_type, discount_value, start_date, end_date, usage_limit = _validate_promotion_payload(promotion)
            execute_query(
                '''
                INSERT INTO PROMOTION
                    (promotion_id, promo_code, discount_type, discount_value, start_date, end_date, usage_limit)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''',
                [str(uuid.uuid4()), promo_code, discount_type, discount_value, start_date, end_date, usage_limit],
            )
            messages.success(request, 'Promo berhasil dibuat.')
            return redirect('promotions:promotion_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))

    return render(request, 'promotions/promotion_form.html', {
        'mode': 'create',
        'promotion': promotion,
        'discount_types': DISCOUNT_TYPES,
        'role': page_role(request),
    })


@role_required('administrator')
def promotion_update(request, promotion_id):
    promotion = fetch_one(
        '''
        SELECT promotion_id::text, promo_code, discount_type, discount_value,
               start_date, end_date, usage_limit
        FROM PROMOTION
        WHERE promotion_id = %s
        ''',
        [promotion_id],
    )
    if not promotion:
        messages.error(request, 'Promo tidak ditemukan.')
        return redirect('promotions:promotion_list')

    if request.method == 'POST':
        promotion = _promotion_from_post(request, promotion)
        try:
            promo_code, discount_type, discount_value, start_date, end_date, usage_limit = _validate_promotion_payload(promotion)
            execute_query(
                '''
                UPDATE PROMOTION
                SET promo_code = %s,
                    discount_type = %s,
                    discount_value = %s,
                    start_date = %s,
                    end_date = %s,
                    usage_limit = %s
                WHERE promotion_id = %s
                ''',
                [promo_code, discount_type, discount_value, start_date, end_date, usage_limit, promotion_id],
            )
            messages.success(request, 'Promo berhasil diperbarui.')
            return redirect('promotions:promotion_list')
        except (DatabaseError, ValueError) as exc:
            messages.error(request, db_error_message(exc) if isinstance(exc, DatabaseError) else str(exc))

    return render(request, 'promotions/promotion_form.html', {
        'mode': 'update',
        'promotion': promotion,
        'discount_types': DISCOUNT_TYPES,
        'role': page_role(request),
    })


@role_required('administrator')
def promotion_delete(request, promotion_id):
    promotion = fetch_one(
        '''
        SELECT promotion_id::text, promo_code
        FROM PROMOTION
        WHERE promotion_id = %s
        ''',
        [promotion_id],
    )
    if not promotion:
        messages.error(request, 'Promo tidak ditemukan.')
        return redirect('promotions:promotion_list')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                execute_query('DELETE FROM ORDER_PROMOTION WHERE promotion_id = %s', [promotion_id])
                execute_query('DELETE FROM PROMOTION WHERE promotion_id = %s', [promotion_id])
            messages.success(request, 'Promo berhasil dihapus.')
            return redirect('promotions:promotion_list')
        except DatabaseError as exc:
            messages.error(request, db_error_message(exc))

    return render(request, 'promotions/promotion_confirm_delete.html', {
        'promotion': promotion,
        'role': page_role(request),
    })
