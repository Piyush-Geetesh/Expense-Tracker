from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def categorize(apps, schema_editor):
    Expense = apps.get_model("expense", "Expense")
    for expense in Expense.objects.using(schema_editor.connection.alias).all().iterator():
        prefix, separator, _ = expense.description.partition("-")
        category = (" ".join(prefix.split()).title() or "Other") if separator else "Other"
        Expense.objects.using(schema_editor.connection.alias).filter(pk=expense.pk).update(category=category)


class Migration(migrations.Migration):
    dependencies = [
        ("expense", "0002_salary"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AlterModelTable(name="salary", table="expense_salary"),
        migrations.RenameModel(old_name="Salary", new_name="SalaryCycle"),
        migrations.AddField(model_name="salarycycle", name="user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="salary_cycles", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="salarycycle", name="is_current",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="expense", name="cycle",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name="expenses", to="expense.salarycycle")),
        migrations.AddField(model_name="expense", name="category",
                            field=models.CharField(default="Other", max_length=200)),
        migrations.AlterModelOptions(name="salarycycle", options={"ordering": ["-credited_at", "-id"]}),
        migrations.AlterModelOptions(name="expense", options={"ordering": ["-created_at", "-id"]}),
        migrations.AddConstraint(model_name="salarycycle",
            constraint=models.UniqueConstraint(fields=("user",), condition=models.Q(is_current=True),
                                               name="one_current_cycle_per_user")),
        migrations.AddConstraint(model_name="salarycycle",
            constraint=models.CheckConstraint(condition=models.Q(user__isnull=True) | models.Q(amount__gt=0),
                                              name="owned_salary_positive")),
        migrations.AddConstraint(model_name="salarycycle",
            constraint=models.CheckConstraint(condition=models.Q(is_current=False) | models.Q(user__isnull=False),
                                              name="current_cycle_has_owner")),
        migrations.AddConstraint(model_name="expense",
            constraint=models.CheckConstraint(condition=models.Q(cycle__isnull=True) | models.Q(amount__gt=0),
                                              name="assigned_expense_positive")),
        migrations.RunPython(categorize, migrations.RunPython.noop),
    ]
