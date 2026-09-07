import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from .models import Expense, SalaryCycle


class MigrationTests(TransactionTestCase):
    def test_existing_records_preserved_and_unassigned(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("expense", "0002_salary")])
        old_apps = executor.loader.project_state([("expense", "0002_salary")]).apps
        salary = old_apps.get_model("expense", "Salary").objects.create(amount="123.45")
        expense = old_apps.get_model("expense", "Expense").objects.create(amount="5.25", description=" lunch - meal ")
        salary_id, expense_id = salary.pk, expense.pk
        started, created = salary.credited_at, expense.created_at
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([("expense", "0003_salary_cycles")])
            cycle = SalaryCycle.objects.get(pk=salary_id)
            item = Expense.objects.get(pk=expense_id)
            self.assertEqual(str(cycle.amount), "123.45")
            self.assertEqual(cycle.credited_at, started)
            self.assertIsNone(cycle.user_id)
            self.assertFalse(cycle.is_current)
            self.assertEqual(item.description, " lunch - meal ")
            self.assertEqual(item.created_at, created)
            self.assertEqual(item.category, "Lunch")
            self.assertIsNone(item.cycle_id)
        finally:
            MigrationExecutor(connection).migrate([("expense", "0003_salary_cycles")])


class ReconciliationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("owner")
        self.cycle = SalaryCycle.objects.create(amount=10)
        self.expense = Expense.objects.create(amount=5, description="old")
        self.data = {"cycles": [{"id": self.cycle.pk, "user_id": self.user.pk, "is_current": True}],
                     "expenses": [{"id": self.expense.pk, "cycle_id": self.cycle.pk}]}

    def run_mapping(self, apply=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text(json.dumps(self.data), encoding="utf-8")
            call_command("reconcile_legacy", str(path), apply=apply, stdout=io.StringIO())

    def test_dry_run_then_apply(self):
        self.run_mapping()
        self.cycle.refresh_from_db()
        self.expense.refresh_from_db()
        self.assertIsNone(self.cycle.user_id)
        self.assertIsNone(self.expense.cycle_id)
        self.run_mapping(apply=True)
        self.cycle.refresh_from_db()
        self.expense.refresh_from_db()
        self.assertEqual(self.cycle.user_id, self.user.pk)
        self.assertEqual(self.expense.cycle_id, self.cycle.pk)
        self.assertEqual(self.cycle.balance, 5)

    def test_overspend_rolls_back_everything(self):
        self.expense.amount = 11
        self.expense.save()
        with self.assertRaises(CommandError):
            self.run_mapping(apply=True)
        self.cycle.refresh_from_db()
        self.expense.refresh_from_db()
        self.assertIsNone(self.cycle.user_id)
        self.assertIsNone(self.expense.cycle_id)

    def test_cannot_reassign_owned_records(self):
        self.run_mapping(apply=True)
        with self.assertRaises(CommandError):
            self.run_mapping(apply=True)
