import uuid
import pytest
import requests
from helpers import post, get, first_id, has_message
from conftest import ADMIN_CREDS


def test_t1_duplicate_username():
    u, p = ADMIN_CREDS
    s = requests.Session()
    r = post(s, "/accounts/register/admin/", {
        "username": u, "password": p, "confirm_password": p,
    })
    assert r.status_code == 200
    assert has_message(r.text, "sudah terdaftar", "username", "error")


def test_t1_duplicate_username_case_insensitive():
    u, p = ADMIN_CREDS
    s = requests.Session()
    r = post(s, "/accounts/register/admin/", {
        "username": u.upper(), "password": p, "confirm_password": p,
    })
    assert r.status_code == 200
    assert has_message(r.text, "sudah terdaftar", "username", "error")


def test_t1_special_char_username():
    s = requests.Session()
    r = post(s, "/accounts/register/customer/", {
        "username": "user @123",
        "password": "Pass1234",
        "confirm_password": "Pass1234",
        "full_name": "Test User",
    })
    assert r.status_code == 200
    assert has_message(r.text, "huruf", "angka", "simbol", "error", "spasi")


def test_t1_special_char_with_symbol():
    s = requests.Session()
    r = post(s, "/accounts/register/customer/", {
        "username": "user#test!",
        "password": "Pass1234",
        "confirm_password": "Pass1234",
        "full_name": "Test User",
    })
    assert r.status_code == 200
    assert has_message(r.text, "huruf", "angka", "simbol", "error")


def test_t2_duplicate_venue_same_city(admin_s, base_venue):
    r = post(admin_s, "/venues/create/", {
        "venue_name": base_venue["name"],
        "capacity": "200",
        "city": base_venue["city"],
        "address": "Jl. Duplikat No. 2",
    })
    assert r.status_code == 200
    assert has_message(r.text, "sudah terdaftar", "venue", "error", base_venue["name"])


def test_t2_same_venue_different_city_allowed(admin_s, base_venue):
    r = post(admin_s, "/venues/create/", {
        "venue_name": base_venue["name"],
        "capacity": "200",
        "city": "KotaBeda",
        "address": "Jl. Beda No. 1",
    })
    assert r.status_code == 200


def test_t2_delete_venue_with_active_event(admin_s, base_venue, base_event):
    if not base_venue["id"] or not base_event["id"]:
        pytest.skip("base data not available")
    r = post(admin_s, f"/venues/{base_venue['id']}/delete/", {"confirm": "1"})
    assert r.status_code == 200
    assert has_message(r.text, "aktif", "event", "tidak dapat dihapus", "error")


def test_t3_duplicate_artist_in_event(admin_s, org_s, base_event, base_artist, base_venue):
    if not base_event["id"] or not base_artist["id"]:
        pytest.skip("base data not available")
    r = post(admin_s, f"/events/{base_event['id']}/edit/", {
        "event_title": base_event["title"],
        "event_date": "2026-12-25",
        "event_time": "19:00",
        "venue_id": base_venue["id"],
        "artist_ids": [base_artist["id"], base_artist["id"]],
        "category_name": "General",
        "category_price": "100000",
        "category_quota": "200",
        "category_id": "",
    })
    assert r.status_code == 200


def test_t3_ticket_quota_display(cust_s, base_event):
    if not base_event["id"]:
        pytest.skip("base_event not created")
    r = get(cust_s, f"/events/{base_event['id']}/")
    assert r.status_code == 200
    assert has_message(r.text, "kuota", "quota", "sisa", "tiket")


def test_t4_promotion_not_found(cust_s, base_event, base_category):
    if not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    r = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
        "promo_code": "INVALIDPROMO99",
    })
    assert r.status_code == 200
    assert has_message(r.text, "promo", "tidak ditemukan", "error", "invalid")


def test_t4_promotion_usage_limit(admin_s, cust_s, base_event, base_category):
    if not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    code = f"LIM{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/promotions/create/", {
        "promo_code": code,
        "discount_type": "PERCENTAGE",
        "discount_value": "5",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "usage_limit": "1",
    })
    post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
        "promo_code": code,
    })
    r = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
        "promo_code": code,
    })
    assert r.status_code == 200
    assert has_message(r.text, "batas", "maksimum", "penggunaan", "error", "limit")


def test_t4_promotion_out_of_date_range(admin_s, cust_s, base_event, base_category):
    if not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    code = f"EXP{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/promotions/create/", {
        "promo_code": code,
        "discount_type": "PERCENTAGE",
        "discount_value": "10",
        "start_date": "2020-01-01",
        "end_date": "2021-12-31",
        "usage_limit": "100",
    })
    r = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
        "promo_code": code,
    })
    assert r.status_code == 200
    assert has_message(r.text, "tanggal", "berlaku", "error", "tidak")


def test_t5_delete_assigned_seat(admin_s, cust_s, base_venue, base_event, base_category):
    if not base_venue["id"] or not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    section = f"ASN{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/venues/seats/create/", {
        "venue_id": base_venue["id"],
        "section": section,
        "row_number": "X",
        "seat_number": "1",
    })
    r = get(admin_s, "/venues/seats/")
    sid = first_id(r.text, r'/venues/seats/([0-9a-f-]{36})/edit/')
    if not sid:
        pytest.skip("seat not found")
    post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
        "seat_id": sid,
    })
    r2 = post(admin_s, f"/venues/seats/{sid}/delete/", {"confirm": "1"})
    assert r2.status_code == 200
    assert has_message(r2.text, "tidak dapat dihapus", "terisi", "error")


def test_t5_ticket_quota_exceeded(admin_s, cust_s, base_event):
    if not base_event["id"]:
        pytest.skip("base_event not created")
    cat_name = f"FULL{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/tickets/categories/create/", {
        "tevent_id": base_event["id"],
        "category_name": cat_name,
        "quota": "1",
        "price": "10000",
    })
    r = get(admin_s, "/tickets/categories/", {"q": cat_name})
    cid = first_id(r.text, r'/tickets/categories/([0-9a-f-]{36})/edit/')
    if not cid:
        pytest.skip("category not found")
    post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": cid,
        "quantity": "1",
    })
    r2 = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": cid,
        "quantity": "1",
    })
    assert r2.status_code == 200
    assert has_message(r2.text, "penuh", "quota", "kuota", "error", "tidak dapat")
