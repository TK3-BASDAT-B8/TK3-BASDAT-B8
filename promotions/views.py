from django.shortcuts import render, redirect
from django.contrib import messages

#dummy datanya ini, buakn hardcode yh belom mainin psql
PROMOTIONS = [
    {
        'promotion_id': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1',
        'promo_code': 'PROMO_TAHUN_BARU',
        'discount_type': 'PERCENTAGE',
        'discount_value': 25.00,
        'start_date': '2026-01-01',
        'end_date': '2026-01-05',
        'usage_limit': 100,
        'used': 44,
    },
    {
        'promotion_id': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee2',
        'promo_code': 'PROMO_VALENTINE',
        'discount_type': 'NOMINAL',
        'discount_value': 14000.00,
        'start_date': '2026-02-14',
        'end_date': '2026-02-15',
        'usage_limit': 50,
        'used': 12,
    },
    {
        'promotion_id': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee3',
        'promo_code': 'LEBARAN_IDUL_FITRI',
        'discount_type': 'PERCENTAGE',
        'discount_value': 50.00,
        'start_date': '2026-03-20',
        'end_date': '2026-04-05',
        'usage_limit': 200,
        'used': 87,
    },
    {
        'promotion_id': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee4',
        'promo_code': 'DISKON_PELAJAR',
        'discount_type': 'PERCENTAGE',
        'discount_value': 15.00,
        'start_date': '2026-01-01',
        'end_date': '2026-12-31',
        'usage_limit': 500,
        'used': 156,
    },
    {
        'promotion_id': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee5',
        'promo_code': 'MEMBER_BARU',
        'discount_type': 'NOMINAL',
        'discount_value': 20000.00,
        'start_date': '2026-01-01',
        'end_date': '2026-12-31',
        'usage_limit': 1000,
        'used': 231,
    },
    {
        'promotion_id': 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee6',
        'promo_code': 'FLASH_SALE_MANTAP',
        'discount_type': 'NOMINAL',
        'discount_value': 100000.00,
        'start_date': '2026-04-28',
        'end_date': '2026-04-28',
        'usage_limit': 25,
        'used': 19,
    },
]

DISCOUNT_TYPES = ['PERCENTAGE', 'NOMINAL']
#fiturnya specifically buat admin rite but belom bikin auth karena focus di front end
MOCK_ROLE = 'admin'


def get_mock_role(request):
    return request.GET.get('role', MOCK_ROLE)


def promotion_list(request):
    role = get_mock_role(request)
    promotions = list(PROMOTIONS)

    search = request.GET.get('q', '').strip().lower()
    filter_type = request.GET.get('type', 'all')

    if search:
        promotions = [
            p for p in promotions
            if search in p['promo_code'].lower()
        ]

    if filter_type in DISCOUNT_TYPES:
        promotions = [
            p for p in promotions
            if p['discount_type'] == filter_type
        ]

    total_promos = len(PROMOTIONS)
    total_usage = sum(p['used'] for p in PROMOTIONS)
    total_percentage = sum(1 for p in PROMOTIONS if p['discount_type'] == 'PERCENTAGE')

    return render(request, 'promotions/promotion_list.html', {
        'role': role,
        'promotions': promotions,
        'search': search,
        'filter_type': filter_type,
        'discount_types': DISCOUNT_TYPES,
        'total_promos': total_promos,
        'total_usage': total_usage,
        'total_percentage': total_percentage,
    })


def promotion_create(request):
    role = get_mock_role(request)
    if role != 'admin':
        return redirect('promotion_list')

    if request.method == 'POST':
        messages.success(request, 'Promo baru berhasil dibuat!')
        return redirect('promotion_list')

    return render(request, 'promotions/promotion_form.html', {
        'role': role,
        'mode': 'create',
        'promotion': None,
        'discount_types': DISCOUNT_TYPES,
    })


def promotion_update(request, promotion_id):
    role = get_mock_role(request)
    if role != 'admin':
        return redirect('promotion_list')

    promotion = next((p for p in PROMOTIONS if p['promotion_id'] == promotion_id), None)
    if not promotion:
        return redirect('promotion_list')

    if request.method == 'POST':
        messages.success(request, f"Promo {promotion['promo_code']} berhasil diperbarui!")
        return redirect('promotion_list')

    return render(request, 'promotions/promotion_form.html', {
        'role': role,
        'mode': 'update',
        'promotion': promotion,
        'discount_types': DISCOUNT_TYPES,
    })


def promotion_delete(request, promotion_id):
    role = get_mock_role(request)
    if role != 'admin':
        return redirect('promotion_list')

    promotion = next((p for p in PROMOTIONS if p['promotion_id'] == promotion_id), None)
    if not promotion:
        return redirect('promotion_list')

    if request.method == 'POST':
        messages.success(request, f"Promo {promotion['promo_code']} berhasil dihapus!")
        return redirect('promotion_list')

    return render(request, 'promotions/promotion_confirm_delete.html', {
        'role': role,
        'promotion': promotion,
    })