from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.hashers import make_password, check_password
from core.db import fetch_one, execute_query


def login_user(request, username, password):
    """Authenticate user and store session. Returns True on success."""
    user = fetch_one("""
        SELECT ua.user_id, ua.username, ua.password,
               array_agg(r.role_name) AS roles
        FROM user_account ua
        JOIN account_role ar ON ua.user_id = ar.user_id
        JOIN role r ON ar.role_id = r.role_id
        WHERE ua.username = %s
        GROUP BY ua.user_id, ua.username, ua.password
    """, [username])

    if user and check_password(password, user['password']):
        request.session['user_id'] = str(user['user_id'])
        request.session['username'] = user['username']
        request.session['roles'] = user['roles']
        return True
    return False


def logout_user(request):
    """Clear session."""
    request.session.flush()


def register_user(username, password):
    """Insert new user_account with hashed password."""
    execute_query("""
        INSERT INTO user_account (user_id, username, password)
        VALUES (gen_random_uuid(), %s, %s)
    """, [username, make_password(password)])


def get_current_user(request):
    """Return session user dict or None."""
    if 'user_id' not in request.session:
        return None
    return {
        'user_id': request.session['user_id'],
        'username': request.session['username'],
        'roles': request.session.get('roles', []),
    }


def has_role(request, *roles):
    """Check if current session user has any of the given roles."""
    user_roles = request.session.get('roles', [])
    return any(r in user_roles for r in roles)


def login_required(view_func):
    """Redirect to login if not authenticated."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'user_id' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(*roles):
    """Redirect to dashboard if authenticated but wrong role."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if 'user_id' not in request.session:
                return redirect('login')
            if not has_role(request, *roles):
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
