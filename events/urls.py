from django.urls import path
from . import views

urlpatterns = [
    path('', views.event_list, name='event_list'),
    path('create/', views.event_create, name='event_create'),
    path('<str:event_id>/edit/', views.event_edit, name='event_edit'),
    path('<str:event_id>/', views.event_detail, name='event_detail'),
]
