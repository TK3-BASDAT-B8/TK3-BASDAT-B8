import uuid
import pytest
from helpers import post, get, find_ids, first_id, has_message


def test_venue_list_accessible(admin_s):
    r = get(admin_s, "/venues/")
    assert r.status_code == 200


def test_venue_list_guest_redirected(guest_s):
    r = get(guest_s, "/venues/")
    assert r.status_code == 200
    assert has_message(r.text, "login", "masuk")


def test_venue_create(admin_s):
    name = f"VenueNew{uuid.uuid4().hex[:6]}"
    r = post(admin_s, "/venues/create/", {
        "venue_name": name,
        "capacity": "300",
        "city": "Bandung",
        "address": "Jl. Dago No. 5",
    })
    assert r.status_code == 200
    r2 = get(admin_s, "/venues/", {"q": name})
    assert name in r2.text


def test_venue_edit(admin_s, base_venue):
    if not base_venue["id"]:
        pytest.skip("base_venue not created")
    r = post(admin_s, f"/venues/{base_venue['id']}/edit/", {
        "venue_name": base_venue["name"],
        "capacity": "600",
        "city": base_venue["city"],
        "address": "Jl. Updated No. 99",
    })
    assert r.status_code == 200


def test_venue_delete(admin_s):
    name = f"VenueDel{uuid.uuid4().hex[:6]}"
    post(admin_s, "/venues/create/", {
        "venue_name": name, "capacity": "100",
        "city": "Surabaya", "address": "Jl. Del No. 1",
    })
    r = get(admin_s, "/venues/", {"q": name})
    vid = first_id(r.text, r'/venues/([0-9a-f-]{36})/edit/')
    if not vid:
        pytest.skip("venue not created")
    r2 = post(admin_s, f"/venues/{vid}/delete/", {"confirm": "1"})
    assert r2.status_code == 200


def test_venue_search_by_name(admin_s, base_venue):
    r = get(admin_s, "/venues/", {"q": base_venue["name"]})
    assert r.status_code == 200
    assert base_venue["name"] in r.text


def test_venue_search_by_address(admin_s, base_venue):
    r = get(admin_s, "/venues/", {"q": "Jl. Test"})
    assert r.status_code == 200


def test_venue_filter_by_city(admin_s, base_venue):
    r = get(admin_s, "/venues/", {"city": base_venue["city"]})
    assert r.status_code == 200
    assert base_venue["name"] in r.text


def test_venue_filter_free_seating(admin_s, base_venue):
    r = get(admin_s, "/venues/", {"seating": "free"})
    assert r.status_code == 200


def test_venue_filter_reserved_seating(admin_s):
    r = get(admin_s, "/venues/", {"seating": "reserved"})
    assert r.status_code == 200


def test_venue_customer_readonly(cust_s, base_venue):
    r = get(cust_s, "/venues/")
    assert r.status_code == 200
    assert "tambah" not in r.text.lower() or "tambah venue" not in r.text.lower()


def test_seat_list(admin_s):
    r = get(admin_s, "/venues/seats/")
    assert r.status_code == 200


def test_seat_create(admin_s, base_venue):
    if not base_venue["id"]:
        pytest.skip("base_venue not created")
    section = f"S{uuid.uuid4().hex[:4].upper()}"
    r = post(admin_s, "/venues/seats/create/", {
        "venue_id": base_venue["id"],
        "section": section,
        "row_number": "B",
        "seat_number": "10",
    })
    assert r.status_code == 200


def test_seat_edit(admin_s, base_seat, base_venue):
    if not base_seat["id"]:
        pytest.skip("base_seat not created")
    r = post(admin_s, f"/venues/seats/{base_seat['id']}/edit/", {
        "venue_id": base_venue["id"],
        "section": base_seat["section"],
        "row_number": "C",
        "seat_number": "2",
    })
    assert r.status_code == 200


def test_seat_delete(admin_s, base_venue):
    if not base_venue["id"]:
        pytest.skip("base_venue not created")
    section = f"DEL{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/venues/seats/create/", {
        "venue_id": base_venue["id"], "section": section,
        "row_number": "Z", "seat_number": "99",
    })
    r = get(admin_s, "/venues/seats/")
    sid = first_id(r.text, r'/venues/seats/([0-9a-f-]{36})/edit/')
    if not sid:
        pytest.skip("seat not found")
    r2 = post(admin_s, f"/venues/seats/{sid}/delete/", {"confirm": "1"})
    assert r2.status_code == 200
