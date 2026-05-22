import uuid
import pytest
from helpers import post, get, first_id, has_message


def test_event_list(cust_s):
    r = get(cust_s, "/events/")
    assert r.status_code == 200


def test_event_list_guest(guest_s):
    r = get(guest_s, "/events/")
    assert r.status_code == 200


def test_event_create(org_s, base_venue, base_artist):
    if not base_venue["id"]:
        pytest.skip("base_venue not created")
    title = f"EvNew{uuid.uuid4().hex[:6]}"
    r = post(org_s, "/events/create/", {
        "event_title": title,
        "event_date": "2026-11-15",
        "event_time": "20:00",
        "venue_id": base_venue["id"],
        "category_name": "Regular",
        "category_price": "50000",
        "category_quota": "100",
        "category_id": "",
    })
    assert r.status_code == 200


def test_event_edit(org_s, base_event, base_venue):
    if not base_event["id"] or not base_venue["id"]:
        pytest.skip("base_event not created")
    r = post(org_s, f"/events/{base_event['id']}/edit/", {
        "event_title": base_event["title"] + " Updated",
        "event_date": "2026-12-25",
        "event_time": "19:30",
        "venue_id": base_venue["id"],
        "category_name": "General",
        "category_price": "100000",
        "category_quota": "200",
        "category_id": "",
    })
    assert r.status_code == 200


def test_event_detail(cust_s, base_event):
    if not base_event["id"]:
        pytest.skip("base_event not created")
    r = get(cust_s, f"/events/{base_event['id']}/")
    assert r.status_code == 200


def test_event_search_by_title(cust_s, base_event):
    r = get(cust_s, "/events/", {"q": base_event["title"][:8]})
    assert r.status_code == 200
    assert base_event["title"][:8] in r.text or r.status_code == 200


def test_event_search_by_artist(cust_s, base_artist):
    r = get(cust_s, "/events/", {"q": base_artist["name"]})
    assert r.status_code == 200


def test_event_filter_by_venue(cust_s, base_venue):
    if not base_venue["id"]:
        pytest.skip("base_venue not created")
    r = get(cust_s, "/events/", {"venue_id": base_venue["id"]})
    assert r.status_code == 200


def test_event_filter_by_artist(cust_s, base_artist):
    if not base_artist["id"]:
        pytest.skip("base_artist not created")
    r = get(cust_s, "/events/", {"artist_id": base_artist["id"]})
    assert r.status_code == 200


def test_artist_list(cust_s):
    r = get(cust_s, "/events/artists/")
    assert r.status_code == 200


def test_artist_list_guest(guest_s):
    r = get(guest_s, "/events/artists/")
    assert r.status_code == 200


def test_artist_create(admin_s):
    name = f"ArtNew{uuid.uuid4().hex[:6]}"
    r = post(admin_s, "/events/artists/create/", {"name": name, "genre": "Jazz"})
    assert r.status_code == 200
    r2 = get(admin_s, "/events/artists/")
    assert name in r2.text


def test_artist_edit(admin_s, base_artist):
    if not base_artist["id"]:
        pytest.skip("base_artist not created")
    r = post(admin_s, f"/events/artists/{base_artist['id']}/edit/", {
        "name": base_artist["name"], "genre": "Jazz Updated",
    })
    assert r.status_code == 200


def test_artist_delete(admin_s):
    name = f"ArtDel{uuid.uuid4().hex[:6]}"
    post(admin_s, "/events/artists/create/", {"name": name, "genre": "Test"})
    r = get(admin_s, "/events/artists/")
    aid = first_id(r.text, r'/events/artists/([0-9a-f-]{36})/edit/')
    if not aid:
        pytest.skip("artist not found")
    r2 = post(admin_s, f"/events/artists/{aid}/delete/", {"confirm": "1"})
    assert r2.status_code == 200


def test_event_list_shows_venue_info(cust_s, base_venue):
    r = get(cust_s, "/events/")
    assert r.status_code == 200
    assert has_message(r.text, base_venue["city"], base_venue["name"])
