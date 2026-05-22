import uuid
import pytest
from helpers import post, get, first_id, has_message


def test_ticket_category_list(cust_s):
    r = get(cust_s, "/tickets/categories/")
    assert r.status_code == 200


def test_ticket_category_list_guest(guest_s):
    r = get(guest_s, "/tickets/categories/")
    assert r.status_code == 200


def test_ticket_category_create(admin_s, base_event):
    if not base_event["id"]:
        pytest.skip("base_event not created")
    name = f"CatNew{uuid.uuid4().hex[:6]}"
    r = post(admin_s, "/tickets/categories/create/", {
        "tevent_id": base_event["id"],
        "category_name": name,
        "quota": "30",
        "price": "50000",
    })
    assert r.status_code == 200


def test_ticket_category_edit(admin_s, base_category, base_event):
    if not base_category["id"]:
        pytest.skip("base_category not created")
    r = post(admin_s, f"/tickets/categories/{base_category['id']}/edit/", {
        "tevent_id": base_event["id"],
        "category_name": base_category["name"],
        "quota": "60",
        "price": "80000",
    })
    assert r.status_code == 200


def test_ticket_category_delete(admin_s, base_event):
    if not base_event["id"]:
        pytest.skip("base_event not created")
    name = f"CatDel{uuid.uuid4().hex[:6]}"
    post(admin_s, "/tickets/categories/create/", {
        "tevent_id": base_event["id"],
        "category_name": name,
        "quota": "10",
        "price": "25000",
    })
    r = get(admin_s, "/tickets/categories/")
    cid = first_id(r.text, r'/tickets/categories/([0-9a-f-]{36})/edit/')
    if not cid:
        pytest.skip("category not found")
    r2 = post(admin_s, f"/tickets/categories/{cid}/delete/", {"confirm": "1"})
    assert r2.status_code == 200


def test_ticket_category_organizer_can_view(org_s):
    r = get(org_s, "/tickets/categories/")
    assert r.status_code == 200


def test_ticket_list(admin_s):
    r = get(admin_s, "/tickets/my-tickets/")
    assert r.status_code == 200


def test_ticket_create(admin_s, base_order, base_category):
    if not base_order["id"] or not base_category["id"]:
        pytest.skip("base_order or base_category not available")
    r = post(admin_s, "/tickets/my-tickets/create/", {
        "order_id": base_order["id"],
        "category_id": base_category["id"],
        "seat_id": "",
    })
    assert r.status_code == 200


def test_ticket_list_customer(cust_s):
    r = get(cust_s, "/tickets/my-tickets/")
    assert r.status_code == 200


def test_ticket_category_search(admin_s, base_category):
    r = get(admin_s, "/tickets/categories/", {"q": base_category["name"][:5]})
    assert r.status_code == 200


def test_ticket_category_filter_by_event(admin_s, base_event):
    if not base_event["id"]:
        pytest.skip("base_event not created")
    r = get(admin_s, "/tickets/categories/", {"event_id": base_event["id"]})
    assert r.status_code == 200
