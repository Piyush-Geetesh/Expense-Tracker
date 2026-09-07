from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404
from django.test import TestCase
from .models import Expense, SalaryCycle, extract_category
from .services import credit_salary, add_expense, delete_expense, delete_cycle_expenses


class FinancialTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("alice", password="sample-pass-123")
        self.other = get_user_model().objects.create_user("bob", password="sample-pass-123")

    def test_cycle_lifecycle_and_isolation(self):
        first = credit_salary(self.user, "100")
        add_expense(self.user, "100", "lunch - meal")
        self.assertEqual(first.balance, 0)
        second = credit_salary(self.user, "200")
        new = add_expense(self.user, "25", "travel - bus")
        self.assertEqual(new.cycle, second)
        self.assertEqual(second.balance, 175)
        first.refresh_from_db()
        self.assertEqual(first.status, "completed")
        self.assertEqual(first.total_expenses, 100)

    def test_salary_blocked_until_zero(self):
        credit_salary(self.user, 100)
        with self.assertRaises(ValidationError):
            credit_salary(self.user, 200)
        self.assertEqual(SalaryCycle.objects.count(), 1)

    def test_no_cycle_or_overdraft(self):
        with self.assertRaises(ValidationError):
            add_expense(self.user, 1, "test")
        cycle = credit_salary(self.user, 10)
        with self.assertRaises(ValidationError):
            add_expense(self.user, "10.01", "test")
        self.assertEqual(cycle.balance, 10)
        add_expense(self.user, 10, "test")
        with self.assertRaises(ValidationError):
            add_expense(self.user, 1, "test")

    def test_individual_deletion_reopens_latest(self):
        cycle = credit_salary(self.user, 10)
        expense = add_expense(self.user, 10, "test")
        self.assertEqual(cycle.status, "completed")
        delete_expense(self.user, expense.pk)
        self.assertEqual(cycle.balance, 10)
        self.assertEqual(cycle.status, "active")

    def test_delete_all_only_selected_cycle(self):
        first = credit_salary(self.user, 10)
        add_expense(self.user, 10, "old")
        second = credit_salary(self.user, 20)
        keep = add_expense(self.user, 5, "new")
        other = credit_salary(self.other, 30)
        foreign = add_expense(self.other, 3, "other")
        self.assertEqual(delete_cycle_expenses(self.user, first.pk), 1)
        self.assertTrue(Expense.objects.filter(pk=keep.pk).exists())
        self.assertTrue(Expense.objects.filter(pk=foreign.pk).exists())
        self.assertEqual(SalaryCycle.objects.count(), 3)
        self.assertEqual(second.balance, 15)
        self.assertEqual(other.balance, 27)
        first.refresh_from_db()
        self.assertFalse(first.is_current)

    def test_foreign_deletes_rejected(self):
        cycle = credit_salary(self.other, 10)
        expense = add_expense(self.other, 5, "test")
        with self.assertRaises(Http404):
            delete_expense(self.user, expense.pk)
        with self.assertRaises(Http404):
            delete_cycle_expenses(self.user, cycle.pk)
        self.assertTrue(Expense.objects.filter(pk=expense.pk).exists())

    def test_category_preserves_description(self):
        cycle = credit_salary(self.user, 10)
        original = "  lunch  - at Restaurant  "
        expense = add_expense(self.user, 1, original)
        self.assertEqual(expense.description, original)
        self.assertEqual(expense.category, "Lunch")
        for text, expected in [("travel - Uber", "Travel"), ("grocery - vegetables", "Grocery"),
                               ("no hyphen", "Other"), (" - empty", "Other"),
                               (" bus   fare - ticket - more", "Bus Fare")]:
            self.assertEqual(extract_category(text), expected)

    def test_invalid_amounts(self):
        for amount in ["0", "-1", "NaN", "Infinity", "1.001", "10000000000"]:
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                credit_salary(self.user, amount)
        self.assertEqual(SalaryCycle.objects.count(), 0)

    def test_legacy_data_untouched(self):
        legacy = SalaryCycle.objects.create(amount=50)
        old = Expense.objects.create(description="legacy", amount=3)
        cycle = credit_salary(self.user, 10)
        self.assertEqual(cycle.balance, Decimal("10"))
        self.assertIsNone(legacy.user_id)
        self.assertIsNone(old.cycle_id)
