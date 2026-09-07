from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path(
        'expense/<int:expense_id>/delete/',
        views.delete_expense,
        name='delete_expense'
    ),
]