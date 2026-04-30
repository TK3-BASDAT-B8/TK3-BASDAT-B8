from django.urls import path
from . import views

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('checkout/<str:event_id>/', views.checkout, name='checkout'),
    path('<str:order_id>/edit/', views.order_edit, name='order_edit'),
    path('<str:order_id>/delete/', views.order_delete, name='order_delete'),
    path('partial/', views.order_partial, name='order_partial'),
]
