import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

ROOT = Path(__file__).resolve().parent.parent


class DeploymentSettingsTests(SimpleTestCase):
    def settings(self, **overrides):
        env = {
            "DJANGO_READ_DOTENV": "False",
            "RENDER": "true",
            "DEBUG": "False",
            "DJANGO_SECRET_KEY": "test-only-random-shaped-key-0123456789-abcdefghijklmnopqrstuvwxyz",
            "DATABASE_URL": "postgresql://test:test@neon.example/db?sslmode=require",
            "RENDER_EXTERNAL_HOSTNAME": "expense-api.onrender.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": " https://expense-tracker-lemon-omega-49.vercel.app ",
            "DJANGO_TRUST_PROXY": "True",
        }
        env.update(overrides)
        with patch.dict(os.environ, env, clear=True):
            return runpy.run_path(str(ROOT / "config" / "settings.py"))

    def test_render_host_neon_tls_and_secure_cookies(self):
        config = self.settings()
        self.assertEqual(config["ALLOWED_HOSTS"], ["expense-api.onrender.com"])
        self.assertEqual(config["DATABASES"]["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["DATABASES"]["default"]["OPTIONS"]["sslmode"], "require")
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["SESSION_COOKIE_HTTPONLY"])
        self.assertTrue(config["CSRF_COOKIE_SECURE"])
        self.assertEqual(config["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertEqual(config["CSRF_TRUSTED_ORIGINS"],
                         ["https://expense-tracker-lemon-omega-49.vercel.app"])

    def test_production_never_falls_back_to_sqlite(self):
        for url in ["", "sqlite:///temporary.sqlite3"]:
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured):
                self.settings(DATABASE_URL=url)

    def test_production_rejects_placeholder_secret(self):
        with self.assertRaises(ImproperlyConfigured):
            self.settings(DJANGO_SECRET_KEY="REPLACE_WITH_A_GENERATED_RANDOM_SECRET")

    def test_render_generated_256_bit_secret_is_accepted(self):
        config = self.settings(DJANGO_SECRET_KEY="abCD12efGH34ijKL56mnOP78qrST90uvWX12yzAB34c=")
        self.assertFalse(config["DEBUG"])

    def test_explicit_hostnames_trimmed_without_broad_wildcard(self):
        config = self.settings(DJANGO_ALLOWED_HOSTS=" api.example.com, , expense-api.onrender.com ")
        self.assertEqual(config["ALLOWED_HOSTS"], ["api.example.com", "expense-api.onrender.com"])

    def test_local_env_file_cannot_override_hosted_values(self):
        config = self.settings(DJANGO_READ_DOTENV="True")
        self.assertFalse(config["DEBUG"])
        self.assertEqual(config["DATABASES"]["default"]["HOST"], "neon.example")

    def test_production_requires_frontend_origin(self):
        with self.assertRaises(ImproperlyConfigured):
            self.settings(DJANGO_CSRF_TRUSTED_ORIGINS="")


class HealthTests(TestCase):
    def test_health_is_public_and_not_cached(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_database_failure_has_no_sensitive_details(self):
        with patch("config.health.connection.cursor", side_effect=DatabaseError("secret database address")):
            response = self.client.get("/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotIn("secret", response.content.decode())
