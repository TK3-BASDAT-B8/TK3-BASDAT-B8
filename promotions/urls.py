from django.urls import path
from . import views

urlpatterns = [
    path('', views.promotion_list, name='promotion_list'),
    path('create/', views.promotion_create, name='promotion_create'),
    path('<str:promotion_id>/edit/', views.promotion_edit, name='promotion_edit'),
    path('<str:promotion_id>/delete/', views.promotion_delete, name='promotion_delete'),
    path('partial/', views.promotion_partial, name='promotion_partial'),
]
