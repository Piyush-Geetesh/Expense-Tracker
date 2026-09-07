from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView, exception_handler

from .models import Expense, SalaryCycle
from .serializers import (CycleSerializer, ExpenseInput, ExpenseSerializer,
                          LoginSerializer, RegisterSerializer, SalaryInput)
from . import services


def api_exception_handler(exc, context):
    if isinstance(exc, ValidationError):
        return Response({"detail": exc.messages}, status=400)
    if isinstance(exc, OperationalError):
        # In particular, a SQLite write-lock timeout must not become a partial write.
        return Response({"detail": "Database temporarily unavailable. Refresh before retrying."},
                        status=503, headers={"Retry-After": "1"})
    return exception_handler(exc, context)


class PrivateAPIView(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response


class AuthThrottle(AnonRateThrottle):
    rate = "20/min"


class CsrfView(PrivateAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class RegisterView(PrivateAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(**serializer.validated_data)
        except IntegrityError:
            return Response({"username": ["This username is already taken."]}, status=400)
        login(request, user)
        return Response({"username": user.username, "csrfToken": get_token(request)}, status=201)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(PrivateAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            return Response({"detail": "Incorrect username or password."}, status=400)
        login(request, user)
        return Response({"username": user.username, "csrfToken": get_token(request)})


class LogoutView(PrivateAPIView):
    def post(self, request):
        logout(request)
        return Response(status=204)


class MeView(PrivateAPIView):
    def get(self, request):
        return Response({"username": request.user.username})


def owned_cycles(user):
    return SalaryCycle.objects.filter(user=user).prefetch_related("expenses")


class DashboardView(PrivateAPIView):
    def get(self, request):
        cycle = owned_cycles(request.user).filter(is_current=True).first()
        data = CycleSerializer(cycle).data if cycle else None
        active = bool(data and data["status"] == "active")
        return Response({
            "cycle": data,
            "can_add_expense": active,
            "can_credit_salary": not active,
            "recent_expenses": ExpenseSerializer(list(cycle.expenses.all())[:5], many=True).data if cycle else [],
        })


class Pagination(PageNumberPagination):
    page_size = 10


class CyclesView(PrivateAPIView):
    def get(self, request):
        paginator = Pagination()
        rows = paginator.paginate_queryset(owned_cycles(request.user), request)
        return paginator.get_paginated_response(CycleSerializer(rows, many=True).data)

    def post(self, request):
        serializer = SalaryInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        cycle = services.credit_salary(request.user, **serializer.validated_data)
        return Response(CycleSerializer(cycle).data, status=201)


class CycleView(PrivateAPIView):
    def get(self, request, cycle_id):
        cycle = get_object_or_404(owned_cycles(request.user), pk=cycle_id)
        return Response(CycleSerializer(cycle).data)


class CycleExpensesView(PrivateAPIView):
    def get(self, request, cycle_id):
        cycle = get_object_or_404(SalaryCycle, pk=cycle_id, user=request.user)
        paginator = Pagination()
        rows = paginator.paginate_queryset(cycle.expenses.all(), request)
        return paginator.get_paginated_response(ExpenseSerializer(rows, many=True).data)

    def delete(self, request, cycle_id):
        count = services.delete_cycle_expenses(request.user, cycle_id)
        return Response({"deleted": count})


class ExpensesView(PrivateAPIView):
    def post(self, request):
        serializer = ExpenseInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = services.add_expense(request.user, **serializer.validated_data)
        return Response(ExpenseSerializer(expense).data, status=201)


class ExpenseView(PrivateAPIView):
    def delete(self, request, expense_id):
        services.delete_expense(request.user, expense_id)
        return Response(status=204)
