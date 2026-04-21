from django.shortcuts import render, redirect
from django.contrib import messages
from core.auth import role_required
from core.db import fetch_all, fetch_one, execute_query


def promotion_list(request):
    search = request.GET.get('search', '')
    type_filter = request.GET.get('discount_type', '')
    sql = "SELECT * FROM promotion WHERE 1=1"
    params = []
    if search:
        sql += " AND promo_code ILIKE %s"
        params.append(f'%{search}%')
    if type_filter:
        sql += " AND discount_type = %s"
        params.append(type_filter)
    sql += " ORDER BY promo_code"
    promotions = fetch_all(sql, params)

    from core.db import fetch_one as fo
    usage = fetch_all("""
        SELECT promotion_id, COUNT(*) AS used_count
        FROM order_promotion GROUP BY promotion_id
    """)
    usage_map = {u['promotion_id']: u['used_count'] for u in usage}
    for p in promotions:
        p['used_count'] = usage_map.get(p['promotion_id'], 0)

    stats = {
        'total': len(promotions),
        'total_usage': sum(p['used_count'] for p in promotions),
        'percentage_count': sum(1 for p in promotions if p['discount_type'] == 'PERCENTAGE'),
    }
    return render(request, 'promotions/promotion_list.html', {
        'promotions': promotions, 'stats': stats,
        'search': search, 'type_filter': type_filter
    })


def promotion_partial(request):
    promotions = fetch_all("SELECT * FROM promotion ORDER BY promo_code")
    return render(request, 'promotions/partials/promotion_table.html', {'promotions': promotions})


@role_required('administrator')
def promotion_create(request):
    if request.method == 'POST':
        code = request.POST.get('promo_code', '').strip()
        dtype = request.POST.get('discount_type')
        dval = request.POST.get('discount_value', '').strip()
        start = request.POST.get('start_date')
        end = request.POST.get('end_date')
        limit = request.POST.get('usage_limit', '').strip()
        if not all([code, dtype, dval, start, end, limit]):
            messages.error(request, 'Semua field wajib diisi.')
        else:
            execute_query(
                "INSERT INTO promotion (promotion_id, promo_code, discount_type, discount_value, start_date, end_date, usage_limit) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s)",
                [code, dtype, float(dval), start, end, int(limit)]
            )
            messages.success(request, 'Promosi berhasil dibuat.')
            return redirect('promotion_list')
    return render(request, 'promotions/promotion_form.html', {'action': 'create'})


@role_required('administrator')
def promotion_edit(request, promotion_id):
    promo = fetch_one("SELECT * FROM promotion WHERE promotion_id = %s", [promotion_id])
    if not promo:
        return redirect('promotion_list')
    if request.method == 'POST':
        code = request.POST.get('promo_code', '').strip()
        dtype = request.POST.get('discount_type')
        dval = request.POST.get('discount_value', '').strip()
        start = request.POST.get('start_date')
        end = request.POST.get('end_date')
        limit = request.POST.get('usage_limit', '').strip()
        execute_query(
            "UPDATE promotion SET promo_code=%s, discount_type=%s, discount_value=%s, start_date=%s, end_date=%s, usage_limit=%s WHERE promotion_id=%s",
            [code, dtype, float(dval), start, end, int(limit), promotion_id]
        )
        messages.success(request, 'Promosi berhasil diperbarui.')
        return redirect('promotion_list')
    return render(request, 'promotions/promotion_form.html', {'action': 'edit', 'promo': promo})


@role_required('administrator')
def promotion_delete(request, promotion_id):
    promo = fetch_one("SELECT * FROM promotion WHERE promotion_id = %s", [promotion_id])
    if not promo:
        return redirect('promotion_list')
    if request.method == 'POST':
        execute_query("DELETE FROM promotion WHERE promotion_id = %s", [promotion_id])
        messages.success(request, 'Promosi berhasil dihapus.')
        return redirect('promotion_list')
    return render(request, 'promotions/promotion_confirm_delete.html', {'promo': promo})
