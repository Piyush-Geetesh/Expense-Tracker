from django.db import models


class Expense(models.Model):
    description = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description


class Salary(models.Model):
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    credited_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.amount)