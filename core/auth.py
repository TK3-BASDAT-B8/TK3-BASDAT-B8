from functools import wraps
from django.shortcuts import redirect

DUMMY_USERS = [
    {
        "username": "syafiq",
        "password": "admin123",
        "role": "administrator",
        "name": "Syafiq Faqih",
        "email": "admin@tiktaktuk.com",
    },
    {
        "username": "eilannyst",
        "password": "organizer123",
        "role": "organizer",
        "name": "AElizabeth Meiulanny",
        "email": "eilannyst.organizer@tiktaktuk.com",
    },
    {
        "username": "chazelnut",
        "password": "customer123",
        "role": "customer",
        "name": "Rashika Maharani",
        "email": "chazelnut.customer@tiktaktuk.com",
    },
    {
        "username": "nadzimmm",
        "password": "customer456",
        "role": "customer",
        "name": "Kak Nadzim",
        "email": "nadzimmm.customer@tiktaktuk.com",
    },
]

def login_user(request, user):
    request.session["user"] = user

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