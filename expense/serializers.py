from decimal import Decimal
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Expense, SalaryCycle


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected a JSON object.")
        unexpected = set(data) - set(self.fields)
        if unexpected:
            raise serializers.ValidationError({key: "This field is not accepted." for key in unexpected})
        return super().to_internal_value(data)


class RegisterSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_username(self, value):
        field = get_user_model()._meta.get_field("username")
        try:
            field.run_validators(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        if get_user_model().objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate(self, attrs):
        try:
            password_validation.validate_password(
                attrs["password"], get_user_model()(username=attrs["username"]))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages})
        return attrs


class LoginSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False, max_length=128, write_only=True)


class SalaryInput(StrictSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class ExpenseInput(StrictSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    description = serializers.CharField(max_length=200, trim_whitespace=False)

    def validate_description(self, value):
        if not value.strip():
            raise serializers.ValidationError("Enter a description.")
        return value


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ["id", "cycle_id", "amount", "description", "category", "created_at"]
        read_only_fields = fields


class CycleSerializer(serializers.ModelSerializer):
    total_expenses = serializers.SerializerMethodField()
    remaining_balance = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    category_summary = serializers.SerializerMethodField()

    class Meta:
        model = SalaryCycle
        fields = ["id", "amount", "credited_at", "is_current", "status",
                  "total_expenses", "remaining_balance", "category_summary"]

    def totals(self, obj):
        # Prefetched per cycle, so totals and categories use the same expense snapshot.
        if not hasattr(self, "_totals_cache"):
            self._totals_cache = {}
        if obj.pk in self._totals_cache:
            return self._totals_cache[obj.pk]
        expenses = list(obj.expenses.all())
        total = sum((expense.amount for expense in expenses), Decimal("0.00"))
        categories = {}
        for expense in expenses:
            categories[expense.category] = categories.get(expense.category, Decimal("0.00")) + expense.amount
        self._totals_cache[obj.pk] = (total, categories)
        return total, categories

    def get_total_expenses(self, obj):
        return f"{self.totals(obj)[0]:.2f}"

    def get_remaining_balance(self, obj):
        return f"{obj.amount - self.totals(obj)[0]:.2f}"

    def get_status(self, obj):
        if obj.amount == self.totals(obj)[0]:
            return "completed"
        return "active" if obj.is_current else "historical"

    def get_category_summary(self, obj):
        return [{"category": key, "amount": f"{value:.2f}"} for key, value in sorted(self.totals(obj)[1].items())]
