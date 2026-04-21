from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from core.auth import login_required, role_required, has_role, get_current_user
from core.db import fetch_all, fetch_one, execute_query


@login_required
def order_list(request):
    user = get_current_user(request)
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if has_role(request, 'administrator'):
        sql = """
            SELECT o.*, c.full_name FROM "order" o
            JOIN customer c ON o.customer_id = c.customer_id WHERE 1=1
        """
        params = []
    elif has_role(request, 'organizer'):
        org = fetch_one("SELECT organizer_id FROM organizer WHERE user_id = %s", [user['user_id']])
        sql = """
            SELECT DISTINCT o.*, c.full_name FROM "order" o
            JOIN customer c ON o.customer_id = c.customer_id
            JOIN ticket t ON t.torder_id = o.order_id
            JOIN ticket_category tc ON t.tcategory_id = tc.category_id
            JOIN event e ON tc.tevent_id = e.event_id
            WHERE e.organizer_id = %s
        """
        params = [org['organizer_id']] if org else []
    else:
        cust = fetch_one("SELECT customer_id FROM customer WHERE user_id = %s", [user['user_id']])
        sql = """
            SELECT o.*, c.full_name FROM "order" o
            JOIN customer c ON o.customer_id = c.customer_id
            WHERE o.customer_id = %s
        """
        params = [cust['customer_id']] if cust else []

    if search:
        sql += " AND CAST(o.order_id AS TEXT) ILIKE %s"
        params.append(f'%{search}%')
    if status_filter:
        sql += " AND o.payment_status = %s"
        params.append(status_filter)

    sql += " ORDER BY o.order_date DESC"
    orders = fetch_all(sql, params)

    stats = {
        'total': len(orders),
        'paid': sum(1 for o in orders if o['payment_status'] == 'Paid'),
        'pending': sum(1 for o in orders if o['payment_status'] == 'Pending'),
        'revenue': sum(o['total_amount'] for o in orders if o['payment_status'] == 'Paid'),
    }
    return render(request, 'orders/order_list.html', {
        'orders': orders, 'stats': stats, 'search': search, 'status_filter': status_filter
    })


def order_partial(request):
    orders = fetch_all('SELECT * FROM "order" ORDER BY order_date DESC')
    return render(request, 'orders/partials/order_table.html', {'orders': orders})


@role_required('customer')
def checkout(request, event_id):
    event = fetch_one("""
        SELECT e.*, v.venue_name FROM event e
        JOIN venue v ON e.venue_id = v.venue_id WHERE e.event_id = %s
    """, [event_id])
    categories = fetch_all(
        "SELECT * FROM ticket_category WHERE tevent_id = %s ORDER BY price DESC", [event_id]
    )
    promotions = fetch_all(
        "SELECT * FROM promotion WHERE end_date >= CURRENT_DATE ORDER BY promo_code"
    )
    seats = fetch_all("""
        SELECT s.* FROM seat s
        WHERE s.venue_id = %s
        AND s.seat_id NOT IN (SELECT seat_id FROM has_relationship)
        ORDER BY s.section, s.row_number, s.seat_number
    """, [event['venue_id']])

    if request.method == 'POST':
        user = get_current_user(request)
        cust = fetch_one("SELECT customer_id FROM customer WHERE user_id = %s", [user['user_id']])
        category_id = request.POST.get('category_id')
        quantity = int(request.POST.get('quantity', 1))
        seat_ids = request.POST.getlist('seat_ids')
        promo_code = request.POST.get('promo_code', '').strip()

        if quantity < 1 or quantity > 10:
            messages.error(request, 'Jumlah tiket harus antara 1 dan 10.')
            return redirect('checkout', event_id=event_id)

        category = fetch_one("SELECT * FROM ticket_category WHERE category_id = %s", [category_id])
        total = float(category['price']) * quantity

        promo = None
        if promo_code:
            promo = fetch_one(
                "SELECT * FROM promotion WHERE promo_code = %s AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE",
                [promo_code]
            )
            if promo:
                if promo['discount_type'] == 'PERCENTAGE':
                    total -= total * float(promo['discount_value']) / 100
                else:
                    total -= float(promo['discount_value'])
                total = max(0, total)
            else:
                messages.error(request, 'Kode promo tidak valid atau sudah kadaluarsa.')
                return redirect('checkout', event_id=event_id)

        import uuid as _uuid
        order_id = str(_uuid.uuid4())
        execute_query(
            'INSERT INTO "order" (order_id, order_date, payment_status, total_amount, customer_id) VALUES (%s, %s, %s, %s, %s)',
            [order_id, timezone.now(), 'Pending', total, cust['customer_id']]
        )

        if promo:
            execute_query(
                "INSERT INTO order_promotion (order_promotion_id, promotion_id, order_id) VALUES (gen_random_uuid(), %s, %s)",
                [promo['promotion_id'], order_id]
            )

        messages.success(request, f'Pesanan berhasil dibuat! Total: Rp {total:,.0f}')
        return redirect('order_list')

    return render(request, 'orders/checkout.html', {
        'event': event, 'categories': categories,
        'promotions': promotions, 'seats': seats
    })


@role_required('administrator')
def order_edit(request, order_id):
    order = fetch_one('SELECT * FROM "order" WHERE order_id = %s', [order_id])
    if not order:
        return redirect('order_list')
    if request.method == 'POST':
        status = request.POST.get('payment_status')
        execute_query(
            'UPDATE "order" SET payment_status = %s WHERE order_id = %s',
            [status, order_id]
        )
        messages.success(request, 'Status order berhasil diperbarui.')
        return redirect('order_list')
    return render(request, 'orders/order_update.html', {'order': order})


@role_required('administrator')
def order_delete(request, order_id):
    order = fetch_one('SELECT * FROM "order" WHERE order_id = %s', [order_id])
    if not order:
        return redirect('order_list')
    if request.method == 'POST':
        execute_query('DELETE FROM "order" WHERE order_id = %s', [order_id])
        messages.success(request, 'Order berhasil dihapus.')
        return redirect('order_list')
    return render(request, 'orders/order_confirm_delete.html', {'order': order})
