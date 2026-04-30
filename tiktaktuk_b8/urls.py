from django.urls import path, include

urlpatterns = [
    path("", include("accounts.urls")),
    path("accounts/", include("accounts.urls")),
    path('venues/', include('venues.urls')),
    path('events/', include('events.urls')),
    path("orders/", include("orders.urls")),
    path("promotions/", include("promotions.urls")),
]