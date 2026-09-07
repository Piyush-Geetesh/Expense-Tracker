from .test_settings import *

# Local browser-test server only. Never use this settings module in production.
DATABASES["default"]["NAME"] = BASE_DIR / "e2e.sqlite3"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:3001", "http://localhost:3001"]
DEBUG = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
