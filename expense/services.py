from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from .models import Expense, SalaryCycle


def money(value, max_digits=12):
    try:
        amount = Decimal(str(value))
        if (not amount.is_finite() or amount <= 0 or
                amount >= Decimal(10) ** (max_digits - 2) or
                amount != amount.quantize(Decimal("0.01"))):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Enter a positive amount with at most two decimal places.")
    return amount


@contextmanager
def financial_transaction(user):
    with transaction.atomic():
        users = get_user_model().objects.filter(pk=user.pk)
        if connection.vendor == "sqlite":
            # A write lock BEFORE balance reads serializes SQLite writers.
            # On lock timeout the whole transaction fails; no partial write commits.
            users.update(last_login=F("last_login"))
        else:
            users.select_for_update().get()
        yield


def credit_salary(user, amount):
    amount = money(amount)
    with financial_transaction(user):
        current = SalaryCycle.objects.filter(user=user, is_current=True).first()
        if current and current.balance > 0:
            raise ValidationError("Spend the remaining balance before crediting another salary.")
        if current:
            current.is_current = False
            current.save(update_fields=["is_current"])
        return SalaryCycle.objects.create(user=user, amount=amount, is_current=True)


def add_expense(user, amount, description):
    amount = money(amount, 10)
    if not isinstance(description, str) or not description.strip() or len(description) > 200:
        raise ValidationError("Enter a description of 1 to 200 characters.")
    with financial_transaction(user):
        current = SalaryCycle.objects.filter(user=user, is_current=True).first()
        if not current or current.balance <= 0:
            raise ValidationError("Credit a salary before adding expenses; there is no active cycle.")
        if amount > current.balance:
            raise ValidationError(f"Expense exceeds the remaining balance of {current.balance:.2f}.")
        return Expense.objects.create(cycle=current, amount=amount, description=description)


def delete_expense(user, expense_id):
    with financial_transaction(user):
        expense = get_object_or_404(Expense, pk=expense_id, cycle__user=user)
        expense.delete()


def delete_cycle_expenses(user, cycle_id):
    with financial_transaction(user):
        cycle = get_object_or_404(SalaryCycle, pk=cycle_id, user=user)
        count = cycle.expenses.count()
        cycle.expenses.all().delete()
        return count
