import re
import requests
from config import BASE_URL

UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _csrf(session, url):
    r = session.get(url, allow_redirects=True)
    m = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', r.text)
    return m.group(1) if m else session.cookies.get("csrftoken", "")


def post(session, path, data):
    url = BASE_URL + path
    token = _csrf(session, url)
    payload = dict(data)
    payload["csrfmiddlewaretoken"] = token
    return session.post(url, data=payload, allow_redirects=True)


def get(session, path, params=None):
    return session.get(BASE_URL + path, params=params, allow_redirects=True)


def find_ids(text, pattern):
    return re.findall(pattern, text)


def first_id(text, pattern):
    m = re.search(pattern, text)
    return m.group(1) if m else None


def has_message(text, *fragments):
    lower = text.lower()
    return any(f.lower() in lower for f in fragments)
