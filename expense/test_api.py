from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Expense, SalaryCycle
from .services import add_expense, credit_salary


class ApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user("alice", password="Unusual-pass-853")
        self.other = get_user_model().objects.create_user("bob", password="Unusual-pass-853")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.foreign_cycle = credit_salary(self.other, 100)
        self.foreign_expense = add_expense(self.other, 10, "secret - private")

    def test_user_isolation_and_tampered_ids(self):
        self.assertEqual(self.client.get("/api/cycles/").data["count"], 0)
        self.assertIsNone(self.client.get("/api/dashboard/").data["cycle"])
        for path in [f"/api/cycles/{self.foreign_cycle.pk}/",
                     f"/api/cycles/{self.foreign_cycle.pk}/expenses/"]:
            self.assertEqual(self.client.get(path).status_code, 404)
        for path in [f"/api/expenses/{self.foreign_expense.pk}/",
                     f"/api/cycles/{self.foreign_cycle.pk}/expenses/"]:
            self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertTrue(Expense.objects.filter(pk=self.foreign_expense.pk).exists())

    def test_unauthenticated_endpoints(self):
        self.client.force_authenticate(user=None)
        for method, path in [("get", "/api/dashboard/"), ("get", "/api/cycles/"),
                             ("post", "/api/cycles/"), ("post", "/api/expenses/"),
                             ("get", f"/api/cycles/{self.foreign_cycle.pk}/"),
                             ("get", f"/api/cycles/{self.foreign_cycle.pk}/expenses/"),
                             ("delete", f"/api/cycles/{self.foreign_cycle.pk}/expenses/"),
                             ("delete", f"/api/expenses/{self.foreign_expense.pk}/"),
                             ("post", "/api/auth/logout/"), ("get", "/api/auth/me/")]:
            with self.subTest(path=path, method=method):
                self.assertEqual(getattr(self.client, method)(path).status_code, 403)

    def test_create_inputs_cannot_set_owner_or_cycle(self):
        self.assertEqual(self.client.post("/api/cycles/", {"amount": "10", "user": self.other.pk}).status_code, 400)
        own = credit_salary(self.user, 10)
        for field in ["user", "cycle", "cycle_id", "category"]:
            response = self.client.post("/api/expenses/", {"amount": "1", "description": "test", field: self.other.pk})
            self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/expenses/", {"amount": "2", "description": " lunch - food  "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["cycle_id"], own.pk)
        self.assertEqual(response.data["description"], " lunch - food  ")
        self.assertEqual(response.data["category"], "Lunch")

    def test_dashboard_history_and_summaries(self):
        first = credit_salary(self.user, 10)
        add_expense(self.user, 10, "travel - bus")
        second = credit_salary(self.user, 20)
        first_lunch = add_expense(self.user, 2, "lunch - food")
        add_expense(self.user, 3, "lunch - more")
        data = self.client.get("/api/dashboard/").data
        self.assertEqual(data["cycle"]["id"], second.pk)
        self.assertEqual(data["cycle"]["remaining_balance"], "15.00")
        self.assertEqual(data["cycle"]["category_summary"], [{"category": "Lunch", "amount": "5.00"}])
        self.assertEqual(len(data["recent_expenses"]), 2)
        self.assertEqual(self.client.get("/api/cycles/").data["results"][0]["id"], second.pk)
        self.assertEqual(self.client.delete(f"/api/expenses/{first_lunch.pk}/").status_code, 204)
        self.assertEqual(second.balance, 17)
        self.assertEqual(self.client.delete(f"/api/cycles/{second.pk}/expenses/").data["deleted"], 1)
        self.assertEqual(second.balance, 20)
        self.assertEqual(first.total_expenses, 10)
        self.assertTrue(SalaryCycle.objects.filter(pk=second.pk).exists())
        self.assertEqual(self.foreign_cycle.balance, 90)

    def test_validation_and_reopen(self):
        self.assertEqual(self.client.post("/api/expenses/", {"amount": 1, "description": "x"}).status_code, 400)
        response = self.client.post("/api/cycles/", {"amount": "10"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post("/api/cycles/", {"amount": "10"}).status_code, 400)
        response = self.client.post("/api/expenses/", {"amount": "11", "description": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("remaining balance", str(response.data))
        for amount in ["-1", "0", "1.001", "NaN"]:
            self.assertEqual(self.client.post("/api/expenses/", {"amount": amount, "description": "x"}).status_code, 400)
        response = self.client.post("/api/expenses/", {"amount": "10", "description": "x"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.client.get("/api/dashboard/").data["can_credit_salary"])
        self.client.delete(f"/api/expenses/{response.data['id']}/")
        self.assertFalse(self.client.get("/api/dashboard/").data["can_credit_salary"])

    def test_unassigned_records_hidden_and_old_routes_disabled(self):
        SalaryCycle.objects.create(amount=999)
        old = Expense.objects.create(amount=5, description="unassigned")
        self.assertEqual(self.client.get("/api/cycles/").data["count"], 0)
        self.assertEqual(self.client.delete(f"/api/expenses/{old.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/expense/{old.pk}/delete/").status_code, 404)
        self.assertEqual(self.client.get("/").status_code, 410)
        self.assertTrue(Expense.objects.filter(pk=old.pk).exists())

    def test_private_responses_no_cache(self):
        self.assertEqual(self.client.get("/api/dashboard/")["Cache-Control"], "no-store, private")

    def test_expense_pagination(self):
        cycle = credit_salary(self.user, 100)
        for index in range(12):
            add_expense(self.user, 1, str(index))
        response = self.client.get(f"/api/cycles/{cycle.pk}/expenses/")
        self.assertEqual(response.data["count"], 12)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(len(self.client.get(f"/api/cycles/{cycle.pk}/expenses/?page=2").data["results"]), 2)


class SessionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self):
        return self.client.get("/api/auth/csrf/").data["csrfToken"]

    def test_csrf_registration_login_logout(self):
        payload = {"username": "newuser", "password": "Distinct-password-853"}
        self.assertEqual(self.client.post("/api/auth/register/", payload).status_code, 403)
        response = self.client.post("/api/auth/register/", payload, HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.cookies["sessionid"]["httponly"])
        self.assertEqual(self.client.get("/api/auth/me/").data["username"], "newuser")
        self.assertEqual(self.client.post("/api/cycles/", {"amount": 10}).status_code, 403)
        self.assertEqual(self.client.post("/api/cycles/", {"amount": 10},
                                         HTTP_X_CSRFTOKEN=self.csrf()).status_code, 201)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 403)
        self.assertEqual(self.client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=self.csrf()).status_code, 204)
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 403)
        self.assertEqual(self.client.post("/api/auth/login/", payload).status_code, 403)
        response = self.client.post("/api/auth/login/", payload, HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/cycles/").data["count"], 1)

    def test_password_validation_and_invalid_login(self):
        response = self.client.post("/api/auth/register/", {"username": "person", "password": "123"},
                                    HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), 0)
        response = self.client.post("/api/auth/login/", {"username": "missing", "password": "bad"},
                                    HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 400)

    def test_delete_requires_csrf(self):
        user = get_user_model().objects.create_user("a", password="Distinct-password-853")
        cycle = credit_salary(user, 10)
        expense = add_expense(user, 5, "test")
        self.client.force_login(user)
        self.assertEqual(self.client.delete(f"/api/expenses/{expense.pk}/").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/cycles/{cycle.pk}/expenses/").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/expenses/{expense.pk}/", HTTP_X_CSRFTOKEN=self.csrf()).status_code, 204)
