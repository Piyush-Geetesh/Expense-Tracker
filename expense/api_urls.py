from django.urls import path
from . import api

urlpatterns = [
    path("auth/csrf/", api.CsrfView.as_view()),
    path("auth/register/", api.RegisterView.as_view()),
    path("auth/login/", api.LoginView.as_view()),
    path("auth/logout/", api.LogoutView.as_view()),
    path("auth/me/", api.MeView.as_view()),
    path("dashboard/", api.DashboardView.as_view()),
    path("cycles/", api.CyclesView.as_view()),
    path("cycles/<int:cycle_id>/", api.CycleView.as_view()),
    path("cycles/<int:cycle_id>/expenses/", api.CycleExpensesView.as_view()),
    path("expenses/", api.ExpensesView.as_view()),
    path("expenses/<int:expense_id>/", api.ExpenseView.as_view()),
]
