from django.shortcuts import redirect
from django.urls import include, path


def home_redirect(request):
    if request.session.get("user"):
        return redirect("accounts:dashboard")
    return redirect("accounts:login")


urlpatterns = [
    path("", home_redirect, name="home"),
    path("accounts/", include("accounts.urls")),
    path("venues/", include("venues.urls")),
    path("events/", include("events.urls")),
    path("tickets/", include("tickets.urls")),
    path("orders/", include("orders.urls")),
    path("promotions/", include("promotions.urls")),
]
