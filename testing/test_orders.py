import uuid
import pytest
from helpers import post, get, first_id, has_message


def test_order_list_admin(admin_s):
    r = get(admin_s, "/orders/")
    assert r.status_code == 200


def test_order_list_organizer(org_s):
    r = get(org_s, "/orders/")
    assert r.status_code == 200


def test_order_list_customer(cust_s):
    r = get(cust_s, "/orders/")
    assert r.status_code == 200


def test_order_list_requires_login(guest_s):
    r = get(guest_s, "/orders/")
    assert r.status_code == 200
    assert has_message(r.text, "login", "masuk")


def test_order_search_by_id(admin_s, base_order):
    if not base_order["id"]:
        pytest.skip("base_order not created")
    r = get(admin_s, "/orders/", {"q": base_order["id"][:8]})
    assert r.status_code == 200


def test_order_filter_by_status_paid(admin_s):
    r = get(admin_s, "/orders/", {"status": "Paid"})
    assert r.status_code == 200


def test_order_filter_by_status_pending(admin_s):
    r = get(admin_s, "/orders/", {"status": "Pending"})
    assert r.status_code == 200


def test_order_filter_by_status_cancelled(admin_s):
    r = get(admin_s, "/orders/", {"status": "Cancelled"})
    assert r.status_code == 200


def test_checkout_page_accessible(cust_s, base_event):
    if not base_event["id"]:
        pytest.skip("base_event not created")
    r = get(cust_s, "/orders/checkout/", {"event_id": base_event["id"]})
    assert r.status_code == 200


def test_checkout_create_order(cust_s, base_event, base_category):
    if not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    r = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
    })
    assert r.status_code == 200


def test_checkout_with_promo(cust_s, base_event, base_category, base_promotion):
    if not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    r = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
        "promo_code": base_promotion["code"],
    })
    assert r.status_code == 200


def test_checkout_invalid_quantity(cust_s, base_event, base_category):
    if not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    r = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "0",
    })
    assert r.status_code == 200
    assert has_message(r.text, "error", "wajib", "valid", "1")


def test_order_update_status(admin_s, base_order):
    if not base_order["id"]:
        pytest.skip("base_order not created")
    r = post(admin_s, f"/orders/{base_order['id']}/update/", {
        "payment_status": "Paid",
    })
    assert r.status_code == 200


def test_order_update_only_admin(cust_s, base_order):
    if not base_order["id"]:
        pytest.skip("base_order not created")
    r = get(cust_s, f"/orders/{base_order['id']}/update/")
    assert r.status_code == 200
    assert has_message(r.text, "login", "dashboard", "admin", "tidak")


def test_order_delete(admin_s, base_event, base_category):
    if not base_event["id"] or not base_category["id"]:
        pytest.skip("base data not available")
    r = post(admin_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
    })
    r2 = get(admin_s, "/orders/")
    oid = first_id(r2.text, r'/orders/([0-9a-f-]{36})/update/')
    if not oid:
        pytest.skip("order not found")
    r3 = post(admin_s, f"/orders/{oid}/delete/", {"confirm": "1"})
    assert r3.status_code == 200


def test_order_statistics_shown(admin_s):
    r = get(admin_s, "/orders/")
    assert r.status_code == 200
    assert has_message(r.text, "total", "lunas", "pending")
