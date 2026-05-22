import uuid
import pytest
import requests
from helpers import post, get, find_ids, first_id

_P = uuid.uuid4().hex[:6]

ADMIN_CREDS = (f"adm{_P}", "Admin1234")
ORG_CREDS = (f"org{_P}", "Org1234")
CUST_CREDS = (f"cst{_P}", "Cust1234")


def _make_session(role, username, password, **extra):
    s = requests.Session()
    data = {"username": username, "password": password, "confirm_password": password}
    data.update(extra)
    post(s, f"/accounts/register/{role}/", data)
    post(s, "/accounts/login/", {"username": username, "password": password})
    return s


@pytest.fixture(scope="session")
def admin_s():
    u, p = ADMIN_CREDS
    return _make_session("admin", u, p)


@pytest.fixture(scope="session")
def org_s():
    u, p = ORG_CREDS
    return _make_session(
        "organizer", u, p,
        organizer_name=f"OrgTest{u}",
        contact_email=f"{u}@test.com",
    )


@pytest.fixture(scope="session")
def cust_s():
    u, p = CUST_CREDS
    return _make_session("customer", u, p, full_name=f"Cust{u}")


@pytest.fixture(scope="session")
def guest_s():
    return requests.Session()


@pytest.fixture(scope="session")
def base_venue(admin_s):
    name = f"VenueTest{uuid.uuid4().hex[:6]}"
    r = post(admin_s, "/venues/create/", {
        "venue_name": name,
        "capacity": "500",
        "city": "KotaTest",
        "address": "Jl. Test No. 1",
    })
    r2 = get(admin_s, "/venues/", {"q": name})
    vid = first_id(r2.text, r'/venues/([0-9a-f-]{36})/edit/')
    return {"id": vid, "name": name, "city": "KotaTest"}


@pytest.fixture(scope="session")
def base_artist(admin_s):
    name = f"ArtistTest{uuid.uuid4().hex[:6]}"
    post(admin_s, "/events/artists/create/", {"name": name, "genre": "Pop"})
    r = get(admin_s, "/events/artists/", {"search": name})
    aid = first_id(r.text, r'/events/artists/([0-9a-f-]{36})/edit/')
    return {"id": aid, "name": name}


@pytest.fixture(scope="session")
def base_event(org_s, base_venue, base_artist):
    title = f"EventTest{uuid.uuid4().hex[:6]}"
    data = {
        "event_title": title,
        "event_date": "2026-12-25",
        "event_time": "19:00",
        "venue_id": base_venue["id"],
        "artist_ids": base_artist["id"] or "",
        "category_name": "General",
        "category_price": "100000",
        "category_quota": "200",
        "category_id": "",
    }
    post(org_s, "/events/create/", data)
    r = get(org_s, "/events/", {"q": title})
    eid = first_id(r.text, r'/events/([0-9a-f-]{36})/edit/')
    return {"id": eid, "title": title}


@pytest.fixture(scope="session")
def base_category(admin_s, base_event):
    name = f"CatTest{uuid.uuid4().hex[:6]}"
    post(admin_s, "/tickets/categories/create/", {
        "tevent_id": base_event["id"],
        "category_name": name,
        "quota": "50",
        "price": "75000",
    })
    r = get(admin_s, "/tickets/categories/", {"q": name})
    cid = first_id(r.text, r'/tickets/categories/([0-9a-f-]{36})/edit/')
    return {"id": cid, "name": name}


@pytest.fixture(scope="session")
def base_promotion(admin_s):
    code = f"PROMO{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/promotions/create/", {
        "promo_code": code,
        "discount_type": "PERCENTAGE",
        "discount_value": "10",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "usage_limit": "100",
    })
    r = get(admin_s, "/promotions/")
    pid = first_id(r.text, r'/promotions/([0-9a-f-]{36})/update/')
    return {"id": pid, "code": code}


@pytest.fixture(scope="session")
def base_seat(admin_s, base_venue):
    section = f"SEC{uuid.uuid4().hex[:4].upper()}"
    post(admin_s, "/venues/seats/create/", {
        "venue_id": base_venue["id"],
        "section": section,
        "row_number": "A",
        "seat_number": "1",
    })
    r = get(admin_s, "/venues/seats/")
    sid = first_id(r.text, r'/venues/seats/([0-9a-f-]{36})/edit/')
    return {"id": sid, "section": section}


@pytest.fixture(scope="session")
def base_order(cust_s, base_event, base_category):
    r = post(cust_s, "/orders/checkout/", {
        "event_id": base_event["id"],
        "category_id": base_category["id"],
        "quantity": "1",
    })
    r2 = get(cust_s, "/orders/")
    oid = first_id(r2.text, r'/orders/([0-9a-f-]{36})/update/')
    return {"id": oid}
