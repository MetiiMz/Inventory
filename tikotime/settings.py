"""
Django settings for the TikoTime watch-inventory project.

توسعه:  .venv/bin/python manage.py runserver
تولید:  .venv/bin/gunicorn tikotime.wsgi
مسیر دیتابیس برای تست:  TIKOTIME_DB=/tmp/test.db
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- security
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-tikotime-local-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "inventory.apps.InventoryConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Whitenoise: سرو استاتیک با فشرده‌سازی و کش — سریع‌ترین حالت ممکن
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "tikotime.urls"

TEMPLATES = [
    {
        # همان قالب‌های Jinja2 نسخه‌ی Flask — UI دست‌نخورده
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "environment": "tikotime.jinja.environment",
            "extensions": ["jinja2.ext.loopcontrols"],
        },
    },
]

WSGI_APPLICATION = "tikotime.wsgi.application"

# ---------------------------------------------------------------- database
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "images"
BACKUP_DIR = DATA_DIR / "backups"
DB_PATH = os.environ.get("TIKOTIME_DB") or str(DATA_DIR / "db.sqlite3")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
        # سرعت: WAL + synchronous=NORMAL + اتصال ماندگار
        "OPTIONS": {
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                "PRAGMA synchronous=NORMAL;"
                "PRAGMA foreign_keys=ON;"
            ),
            "transaction_mode": "IMMEDIATE",
        },
    }
}

# ---------------------------------------------------------------- i18n
LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- static
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
# حداکثر سرعت: کش یک‌ساله برای استاتیک‌ها
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 365

# ---------------------------------------------------------------- uploads
DATA_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

for _d in (DATA_DIR, IMG_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

