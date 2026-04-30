from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('register/customer/', views.register_customer, name='register_customer'),
    path('register/organizer/', views.register_organizer, name='register_organizer'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/password/', views.password_update, name='password_update'),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard_stats'),
]
