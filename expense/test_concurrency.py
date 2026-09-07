from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import OperationalError, close_old_connections
from django.test import TransactionTestCase
from .models import SalaryCycle
from .services import credit_salary, add_expense


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("parallel")

    def race(self, operation):
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                operation(user)
                return "created"
            except (ValidationError, OperationalError):
                # SQLite may reject lock contention; neither request may overdraw.
                return "rejected"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(results.count("created"), 1)

    def test_simultaneous_first_salary(self):
        self.race(lambda user: credit_salary(user, 100))
        self.assertEqual(SalaryCycle.objects.filter(user=self.user, is_current=True).count(), 1)

    def test_simultaneous_expenses_cannot_overdraw(self):
        cycle = credit_salary(self.user, 100)
        self.race(lambda user: add_expense(user, 75, "travel - ticket"))
        self.assertEqual(cycle.expenses.count(), 1)
        self.assertEqual(cycle.balance, 25)

    def test_simultaneous_salary_after_completion(self):
        first = credit_salary(self.user, 100)
        add_expense(self.user, 100, "finish")
        self.race(lambda user: credit_salary(user, 100))
        self.assertEqual(SalaryCycle.objects.filter(user=self.user).count(), 2)
        self.assertEqual(first.balance, 0)
