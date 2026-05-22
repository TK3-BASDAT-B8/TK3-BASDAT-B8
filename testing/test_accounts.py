import uuid
import pytest
import requests
from helpers import post, get, has_message
from conftest import ADMIN_CREDS, ORG_CREDS, CUST_CREDS


def test_register_customer():
    s = requests.Session()
    u = f"cust{uuid.uuid4().hex[:6]}"
    r = post(s, "/accounts/register/customer/", {
        "username": u, "password": "Pass1234", "confirm_password": "Pass1234",
        "full_name": f"Customer {u}",
    })
    assert r.status_code == 200


def test_register_organizer():
    s = requests.Session()
    u = f"org{uuid.uuid4().hex[:6]}"
    r = post(s, "/accounts/register/organizer/", {
        "username": u, "password": "Pass1234", "confirm_password": "Pass1234",
        "organizer_name": f"Org {u}", "contact_email": f"{u}@test.com",
    })
    assert r.status_code == 200


def test_register_admin():
    s = requests.Session()
    u = f"adm{uuid.uuid4().hex[:6]}"
    r = post(s, "/accounts/register/admin/", {
        "username": u, "password": "Pass1234", "confirm_password": "Pass1234",
    })
    assert r.status_code == 200


def test_login_valid(admin_s):
    r = get(admin_s, "/accounts/dashboard/")
    assert r.status_code == 200


def test_login_invalid():
    s = requests.Session()
    r = post(s, "/accounts/login/", {"username": "nobody", "password": "wrongpass"})
    assert r.status_code == 200
    assert has_message(r.text, "salah", "tidak valid", "error")


def test_logout(admin_s):
    s = requests.Session()
    u, p = ADMIN_CREDS
    post(s, "/accounts/login/", {"username": u, "password": p})
    r = post(s, "/accounts/logout/", {})
    assert r.status_code == 200


def test_dashboard_admin(admin_s):
    r = get(admin_s, "/accounts/dashboard/")
    assert r.status_code == 200
    assert has_message(r.text, "admin", "system console", "dashboard")


def test_dashboard_organizer(org_s):
    r = get(org_s, "/accounts/dashboard/")
    assert r.status_code == 200
    assert has_message(r.text, "organizer", "dashboard", "acara")


def test_dashboard_customer(cust_s):
    r = get(cust_s, "/accounts/dashboard/")
    assert r.status_code == 200
    assert has_message(r.text, "customer", "tiket", "dashboard")


def test_profile_view(cust_s):
    r = get(cust_s, "/accounts/profile/")
    assert r.status_code == 200
    assert has_message(r.text, "profil", "username", "role")


def test_profile_edit_customer(cust_s):
    r = post(cust_s, "/accounts/profile/edit/", {
        "full_name": "Updated Customer Name",
        "phone_number": "081234567890",
    })
    assert r.status_code == 200


def test_profile_edit_organizer(org_s):
    u = ORG_CREDS[0]
    r = post(org_s, "/accounts/profile/edit/", {
        "organizer_name": f"OrgUpdated{u}",
        "contact_email": f"{u}updated@test.com",
    })
    assert r.status_code == 200


def test_password_update(cust_s):
    u, p = CUST_CREDS
    r = post(cust_s, "/accounts/profile/password/", {
        "old_password": p,
        "new_password": p,
        "confirm_password": p,
    })
    assert r.status_code == 200


def test_guest_redirected_to_login(guest_s):
    r = get(guest_s, "/accounts/dashboard/")
    assert r.status_code == 200
    assert has_message(r.text, "login", "masuk")


def test_register_page_accessible():
    s = requests.Session()
    r = get(s, "/accounts/register/")
    assert r.status_code == 200
