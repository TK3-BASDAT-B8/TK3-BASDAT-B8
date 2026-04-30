from django.urls import path, include

urlpatterns = [
    path("", include("accounts.urls")),
    path("accounts/", include("accounts.urls")),
    path("orders/", include("orders.urls")),
    path("promotions/", include("promotions.urls")),
]