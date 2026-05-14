from functools import wraps

from django.shortcuts import redirect

from core.db import fetch_one

ROLE_PRIORITY_SQL = """
    CASE r.role_name
        WHEN 'administrator' THEN 1
        WHEN 'organizer' THEN 2
        WHEN 'customer' THEN 3
        ELSE 99
    END
"""


def authenticate_user(username, password):
    user = fetch_one(
        f"""
        SELECT ua.user_id::text, ua.username, r.role_name AS role
        FROM USER_ACCOUNT ua
        JOIN ACCOUNT_ROLE ar ON ua.user_id = ar.user_id
        JOIN ROLE r ON ar.role_id = r.role_id
        WHERE LOWER(ua.username) = LOWER(%s) AND ua.password = %s
        ORDER BY {ROLE_PRIORITY_SQL}
        LIMIT 1
        """,
        [username, password],
    )

    if not user:
        return None

    if user["role"] == "customer":
        extra = fetch_one(
            """
            SELECT customer_id::text, full_name AS name, phone_number
            FROM CUSTOMER
            WHERE user_id = %s
            """,
            [user["user_id"]],
        )
        if extra:
            user.update(extra)
    elif user["role"] == "organizer":
        extra = fetch_one(
            """
            SELECT organizer_id::text, organizer_name AS name, contact_email
            FROM ORGANIZER
            WHERE user_id = %s
            """,
            [user["user_id"]],
        )
        if extra:
            user.update(extra)
    else:
        user["name"] = user["username"]

    return user


def login_user(request, user):
    request.session["user"] = user
    request.session["user_id"] = user.get("user_id")
    request.session["username"] = user.get("username")
    request.session["roles"] = [user.get("role")] if user.get("role") else []
    request.session.modified = True


def refresh_login_user(request):
    current = request.session.get("user")
    if not current:
        return None
    user = fetch_one("SELECT username, password FROM USER_ACCOUNT WHERE user_id = %s", [current.get("user_id")])
    if not user:
        logout_user(request)
        return None
    fresh = authenticate_user(user["username"], user["password"])
    if fresh:
        login_user(request, fresh)
    return fresh


def logout_user(request):
    request.session.flush()


def get_current_user(request):
    return request.session.get("user")


def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not get_current_user(request):
            return redirect("accounts:login")
        return view_func(request, *args, **kwargs)
    return wrapper


def has_role(request, *roles):
    user = get_current_user(request)
    return bool(user and user.get("role") in roles)


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not get_current_user(request):
                return redirect("accounts:login")
            if not has_role(request, *roles):
                return redirect("accounts:dashboard")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def page_role(request):
    user = get_current_user(request)
    if not user:
        return "guest"
    role = user.get("role", "guest")
    return "admin" if role == "administrator" else role
