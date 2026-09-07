import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from expense.models import Expense, SalaryCycle, extract_category


class Command(BaseCommand):
    help = "Validate an explicit legacy mapping. Dry-run unless --apply is supplied; run in maintenance mode."

    def add_arguments(self, parser):
        parser.add_argument("mapping", type=Path)
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            data = json.loads(options["mapping"].read_text(encoding="utf-8"))
            cycles = data["cycles"]
            expenses = data["expenses"]
            if not isinstance(cycles, list) or not isinstance(expenses, list):
                raise ValueError("cycles and expenses must be lists")
            if len({r["id"] for r in cycles}) != len(cycles) or len({r["id"] for r in expenses}) != len(expenses):
                raise ValueError("Duplicate IDs in mapping")
            mapped = {}
            for row in cycles:
                if type(row.get("is_current")) is not bool:
                    raise ValueError("Every cycle requires an explicit boolean is_current")
                cycle = SalaryCycle.objects.get(pk=row["id"], user__isnull=True)
                user = get_user_model().objects.get(pk=row["user_id"])
                if cycle.amount <= 0:
                    raise ValueError(f"Salary {cycle.pk} has a non-positive amount")
                cycle.user = user
                cycle.is_current = row["is_current"]
                cycle.full_clean()
                cycle.save(update_fields=["user", "is_current"])
                mapped[cycle.pk] = cycle
            for row in expenses:
                expense = Expense.objects.get(pk=row["id"], cycle__isnull=True)
                if row["cycle_id"] not in mapped:
                    raise ValueError("Expenses must reference a cycle in this mapping")
                expense.cycle = mapped[row["cycle_id"]]
                expense.category = extract_category(expense.description)
                expense.full_clean()
                expense.save(update_fields=["cycle", "category"])
            for cycle in mapped.values():
                if cycle.balance < 0:
                    raise ValueError(f"Salary {cycle.pk} would be overspent")
            for user_id in {cycle.user_id for cycle in mapped.values()}:
                owned = SalaryCycle.objects.filter(user_id=user_id)
                latest = owned.first()
                current = owned.filter(is_current=True).first()
                if not current or current.pk != latest.pk:
                    raise ValueError(f"User {user_id}: newest cycle must be the single current cycle")
            self.stdout.write(f"Validated {len(cycles)} salary cycles and {len(expenses)} expenses.")
            self.stdout.write(f"Remaining unassigned: {SalaryCycle.objects.filter(user__isnull=True).count()} salaries; "
                              f"{Expense.objects.filter(cycle__isnull=True).count()} expenses.")
            if options["apply"]:
                self.stdout.write(self.style.SUCCESS("Mapping applied. Original amounts, descriptions, IDs and dates preserved."))
            else:
                transaction.set_rollback(True)
                self.stdout.write("DRY RUN: all mapping changes rolled back. Use --apply only after review and backup.")
        except Exception as exc:
            raise CommandError(f"Mapping rejected; no changes committed: {exc}") from exc
