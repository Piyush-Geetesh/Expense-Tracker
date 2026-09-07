from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum


def extract_category(description):
    prefix, separator, _ = description.partition("-")
    return (" ".join(prefix.split()).title() or "Other") if separator else "Other"


class SalaryCycle(models.Model):
    # Keep the original table and IDs throughout the additive migration.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.PROTECT, related_name="salary_cycles")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    credited_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        db_table = "expense_salary"
        ordering = ["-credited_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=Q(is_current=True),
                                    name="one_current_cycle_per_user"),
            models.CheckConstraint(condition=Q(user__isnull=True) | Q(amount__gt=0),
                                   name="owned_salary_positive"),
            models.CheckConstraint(condition=Q(is_current=False) | Q(user__isnull=False),
                                   name="current_cycle_has_owner"),
        ]

    @property
    def total_expenses(self):
        return self.expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    @property
    def balance(self):
        return self.amount - self.total_expenses

    @property
    def status(self):
        if self.balance == 0:
            return "completed"
        return "active" if self.is_current else "historical"

    def __str__(self):
        return str(self.amount)


class Expense(models.Model):
    cycle = models.ForeignKey(SalaryCycle, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="expenses")
    description = models.CharField(max_length=200)
    category = models.CharField(max_length=200, default="Other")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(cycle__isnull=True) | Q(amount__gt=0),
                                   name="assigned_expense_positive"),
        ]

    def save(self, *args, **kwargs):
        self.category = extract_category(self.description)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"category"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description
