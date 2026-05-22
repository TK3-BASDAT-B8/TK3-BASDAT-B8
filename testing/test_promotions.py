import uuid
import pytest
from helpers import post, get, first_id, has_message


def test_promotion_list_admin(admin_s):
    r = get(admin_s, "/promotions/")
    assert r.status_code == 200


def test_promotion_list_customer(cust_s):
    r = get(cust_s, "/promotions/")
    assert r.status_code == 200


def test_promotion_list_guest(guest_s):
    r = get(guest_s, "/promotions/")
    assert r.status_code == 200


def test_promotion_create_percentage(admin_s):
    code = f"PCT{uuid.uuid4().hex[:4].upper()}"
    r = post(admin_s, "/promotions/create/", {
        "promo_code": code,
        "discount_type": "PERCENTAGE",
        "discount_value": "15",
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
        "usage_limit": "50",
    })
    assert r.status_code == 200
    r2 = get(admin_s, "/promotions/")
    assert code in r2.text


def test_promotion_create_nominal(admin_s):
    code = f"NOM{uuid.uuid4().hex[:4].upper()}"
    r = post(admin_s, "/promotions/create/", {
        "promo_code": code,
        "discount_type": "NOMINAL",
        "discount_value": "25000",
        "start_date": "2026-03-01",
        "end_date": "2026-09-30",
        "usage_limit": "30",
    })
    assert r.status_code == 200
    r2 = get(admin_s, "/promotions/")
    assert code in r2.text


def test_promotion_update(admin_s, base_promotion):
    if not base_promotion["id"]:
        pytest.skip("base_promotion not created")
    r = post(admin_s, f"/promotions/{base_promotion['id']}/update/", {
        "promo_code": base_promotion["code"],
        "discount_type": "PERCENTAGE",
        "discount_value": "20",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "usage_limit": "200",
    })
    assert r.status_code == 200


def test_promotion_delete(admin_s):
    code = f"DEL{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/promotions/create/", {
        "promo_code": code,
        "discount_type": "PERCENTAGE",
        "discount_value": "5",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "usage_limit": "10",
    })
    r = get(admin_s, "/promotions/")
    pid = first_id(r.text, r'/promotions/([0-9a-f-]{36})/update/')
    if not pid:
        pytest.skip("promotion not found")
    r2 = post(admin_s, f"/promotions/{pid}/delete/", {"confirm": "1"})
    assert r2.status_code == 200


def test_promotion_only_admin_can_create(cust_s):
    r = get(cust_s, "/promotions/create/")
    assert r.status_code == 200
    assert has_message(r.text, "login", "dashboard", "admin", "tidak")


def test_promotion_shows_discount_info(cust_s, base_promotion):
    r = get(cust_s, "/promotions/")
    assert r.status_code == 200
    assert base_promotion["code"] in r.text
