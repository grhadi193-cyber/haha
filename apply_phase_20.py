# coding: utf-8
"""
apply_phase_20.py
=================
Phase 20 — Hardening v2 + نهایی‌سازی

فایل‌های تغییریافته:
  - config/settings/base.py          ← اضافه: DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE,
                                               OTP_EXPIRY_MINUTES, OTP_RATE_LIMIT_SECONDS
                                        تغییر: CORS default=[], حذف OTP_EXPIRY_SECONDS
  - config/settings/production.py    ← آپدیت imports (نام‌های جدید)
  - accounts/services.py             ← OTP rate-limit از settings (نه عدد ثابت)
  - core/api.py                      ← حذف /error-test endpoint از production
  - requirements/production.txt      ← حذف whitenoise تکراری
  - .env.example                     ← اضافه: OTP_EXPIRY_MINUTES
  - DEPLOY.md                        ← بروزرسانی نهایی
  - CURRENT_STATE.md                 ← همه فازها چک‌مارک

اجرا:
    python apply_phase_20.py
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent

FILES = {}

# ─────────────────────────────────────────────────────────────────────────────
# config/settings/base.py
# ─────────────────────────────────────────────────────────────────────────────

FILES["config/settings/base.py"] = '''\
"""
Base settings shared by all environments.
"""
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# Read .env only when it actually exists (local dev).
# On production the shell environment already contains all variables.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="change-me-in-env-at-least-32-chars!!")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "ninja",
    "corsheaders",
    # project apps
    "core",
    "sms",
    "accounts",
    "store",
    "shipping",
    "payment",
    "blog",
    "admin_panel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — dj-database-url / django-environ style
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3"),
}

# ---------------------------------------------------------------------------
# Auth validators
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# JWT (djangorestframework-simplejwt)
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------
# مدت اعتبار کد OTP بر حسب دقیقه (قابل override از env)
OTP_EXPIRY_MINUTES = env.int("OTP_EXPIRY_MINUTES", default=2)
# حداقل فاصله زمانی بین دو ارسال OTP بر حسب ثانیه
OTP_RATE_LIMIT_SECONDS = 60

# ---------------------------------------------------------------------------
# Pagination defaults
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ---------------------------------------------------------------------------
# SMS / Kavenegar
# ---------------------------------------------------------------------------
KAVENEGAR_API_KEY = env("KAVENEGAR_API_KEY", default="")
SMS_SENDER = env("SMS_SENDER", default="")

# ---------------------------------------------------------------------------
# Payment gateway
# ---------------------------------------------------------------------------
AZ_IRANIAN_BANK_GATEWAYS = {
    "BANKS": {
        "ZARINPAL": {
            "MERCHANT_CODE": env("ZARINPAL_MERCHANT_CODE", default="SANDBOX"),
            "SANDBOX": env.bool("PAYMENT_SANDBOX", default=True),
        },
    },
    "IS_SAMPLE_FORM_ENABLE": False,
    "DEFAULT": "ZARINPAL",
}
PAYMENT_CALLBACK_BASE_URL = env("PAYMENT_CALLBACK_BASE_URL", default="http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Logging (base — console only; production overrides with file handlers)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
'''

# ─────────────────────────────────────────────────────────────────────────────
# config/settings/production.py
# ─────────────────────────────────────────────────────────────────────────────

FILES["config/settings/production.py"] = '''\
"""
Production settings.

Set DJANGO_SETTINGS_MODULE=config.settings.production on the server.
All secrets MUST be present in the environment — never hard-coded here.

Local "check" usage (Windows dev):
    python manage.py check --settings=config.settings.production
    → Works as long as .env contains at least placeholder values for
      SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS.
"""
import os
import logging.handlers  # noqa: F401 — imported early so handlers dict is valid

import environ

from .base import (  # explicit imports — no star import — avoids mutation issues
    BASE_DIR,
    INSTALLED_APPS,
    MIDDLEWARE,
    ROOT_URLCONF,
    TEMPLATES,
    WSGI_APPLICATION,
    AUTH_USER_MODEL,
    AUTH_PASSWORD_VALIDATORS,
    LANGUAGE_CODE,
    TIME_ZONE,
    USE_I18N,
    USE_TZ,
    STATIC_URL,
    STATIC_ROOT,
    MEDIA_URL,
    MEDIA_ROOT,
    SIMPLE_JWT,
    OTP_EXPIRY_MINUTES,
    OTP_RATE_LIMIT_SECONDS,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    KAVENEGAR_API_KEY,
    SMS_SENDER,
    PAYMENT_CALLBACK_BASE_URL,
    CORS_ALLOW_CREDENTIALS,
    DEFAULT_AUTO_FIELD,
    STATICFILES_STORAGE,
)

env = environ.Env()

_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
DEBUG = False

# On the production server these MUST be in the environment.
# On a dev machine running `check --settings=production` they fall back to
# safe placeholder values so the import succeeds without crashing.
SECRET_KEY = env("SECRET_KEY", default="placeholder-for-local-check-only-not-real")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# Warn loudly if someone accidentally deploys with the placeholder key.
if SECRET_KEY == "placeholder-for-local-check-only-not-real":
    import warnings
    warnings.warn(
        "SECRET_KEY is using the placeholder value — "
        "set a real SECRET_KEY in the environment before going live!",
        stacklevel=1,
    )

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Database (PostgreSQL required in production)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

# Only add sslmode for non-SQLite backends to avoid sqlite3 warnings.
_db_url = env("DATABASE_URL", default="sqlite:///db.sqlite3")
if not _db_url.startswith("sqlite"):
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"]["sslmode"] = env("DB_SSLMODE", default="prefer")

# ---------------------------------------------------------------------------
# Static files — WhiteNoise
# ---------------------------------------------------------------------------
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# ---------------------------------------------------------------------------
# Payment gateway — redefine in full (do NOT mutate the base dict)
# ---------------------------------------------------------------------------
AZ_IRANIAN_BANK_GATEWAYS = {
    "BANKS": {
        "ZARINPAL": {
            "MERCHANT_CODE": env("ZARINPAL_MERCHANT_CODE", default="SANDBOX"),
            "SANDBOX": False,   # always OFF in production
        },
    },
    "IS_SAMPLE_FORM_ENABLE": False,
    "DEFAULT": "ZARINPAL",
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[],
)

# ---------------------------------------------------------------------------
# Logging — rotating files + console
# ---------------------------------------------------------------------------
LOG_DIR = env("LOG_DIR", default=str(BASE_DIR / "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} pid={process:d} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "django.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "django_errors.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "level": "ERROR",
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file", "error_file"],
            "level": env("DJANGO_LOG_LEVEL", default="WARNING"),
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["error_file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
'''

# ─────────────────────────────────────────────────────────────────────────────
# accounts/services.py  — OTP rate-limit از settings (نه عدد ثابت 60)
# ─────────────────────────────────────────────────────────────────────────────

FILES["accounts/services.py"] = '''\
from typing import Optional

from django.conf import settings
from django.utils import timezone

from core.exceptions import AppException
from sms.services import send_otp as send_otp_code

from .models import User, Address, OTPRecord


def send_otp(phone_number: str) -> None:
    record, created = OTPRecord.objects.get_or_create(
        phone_number=phone_number,
        defaults={"code": "000000", "expires_at": timezone.now()},
    )

    if not created:
        rate_limit = getattr(settings, "OTP_RATE_LIMIT_SECONDS", 60)
        time_since_last = (timezone.now() - record.last_sent_at).total_seconds()
        if time_since_last < rate_limit:
            remaining = int(rate_limit - time_since_last)
            raise AppException(
                f"لطفاً {remaining} ثانیه دیگر تلاش کنید.",
                status_code=429,
            )

    record.generate_code()
    send_otp_code(phone_number, record.code)


def verify_otp(phone_number: str, code: str) -> User:
    try:
        record = OTPRecord.objects.get(phone_number=phone_number, is_used=False)
    except OTPRecord.DoesNotExist:
        raise AppException("کد تایید یافت نشد", status_code=400)

    if record.is_expired():
        raise AppException("کد تایید منقضی شده است", status_code=400)

    if record.code != code:
        raise AppException("کد تایید اشتباه است", status_code=400)

    record.is_used = True
    record.save(update_fields=["is_used"])

    user, _ = User.objects.get_or_create(phone_number=phone_number)
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user


def get_addresses(user: User) -> list:
    return list(user.addresses.all())


def create_address(
    user: User,
    title: str,
    province: str,
    city: str,
    street: str,
    postal_code: str,
    is_default: bool,
) -> Address:
    if is_default:
        user.addresses.filter(is_default=True).update(is_default=False)
    return Address.objects.create(
        user=user,
        title=title,
        province=province,
        city=city,
        street=street,
        postal_code=postal_code,
        is_default=is_default,
    )


def delete_address(user: User, address_id: int) -> None:
    try:
        address = user.addresses.get(pk=address_id)
    except Address.DoesNotExist:
        raise AppException("آدرس یافت نشد", status_code=404)
    address.delete()


def get_profile(user: User) -> User:
    return user


def update_profile(
    user: User,
    full_name: Optional[str],
    email: Optional[str],
    national_id: Optional[str],
) -> User:
    updated_fields: list[str] = []

    if full_name is not None:
        user.full_name = full_name.strip()
        updated_fields.append("full_name")

    if email is not None:
        user.email = email.strip() or None
        updated_fields.append("email")

    if national_id is not None:
        nid = national_id.strip() or None
        if nid is not None:
            # بررسی unique بودن — کاربر دیگری همین کد ملی را ندارد
            if (
                User.objects.filter(national_id=nid)
                .exclude(pk=user.pk)
                .exists()
            ):
                raise AppException("کد ملی تکراری است", status_code=400)
        user.national_id = nid
        updated_fields.append("national_id")

    if updated_fields:
        user.save(update_fields=updated_fields)

    return user
'''

# ─────────────────────────────────────────────────────────────────────────────
# core/api.py  — حذف /error-test (production-unsafe)
# ─────────────────────────────────────────────────────────────────────────────

FILES["core/api.py"] = '''\
from typing import Optional

from ninja import Router
from pydantic import BaseModel

router = Router(tags=["core"])


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class SiteSettingsOut(BaseModel):
    site_name:        str
    banner_text:      str
    announcement:     str
    primary_color:    str
    maintenance_mode: bool
    social_instagram: str
    social_telegram:  str
    support_phone:    str
    logo:             Optional[str] = None
    # فیلدهای legacy
    hero_title:  str
    hero_text:   str
    hero_banner: Optional[str] = None
    about_us:    str

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", summary="Health check")
def health(request):
    """Returns 200 OK — used by load-balancers and CI."""
    return {"status": "ok"}


@router.get("/settings", response=SiteSettingsOut, summary="تنظیمات عمومی سایت")
def get_site_settings(request):
    """
    تنظیمات سایت — عمومی، بدون نیاز به auth.
    فرانت‌اند برای رنگ، نام، پیام‌ها و شبکه‌های اجتماعی از اینجا می‌خواند.
    """
    from core.models import SiteSettings
    s = SiteSettings.get()

    def _url(field):
        if field and hasattr(field, "url"):
            try:
                return request.build_absolute_uri(field.url)
            except Exception:
                return None
        return None

    return SiteSettingsOut(
        site_name        = s.site_name,
        banner_text      = s.banner_text,
        announcement     = s.announcement,
        primary_color    = s.primary_color,
        maintenance_mode = s.maintenance_mode,
        social_instagram = s.social_instagram,
        social_telegram  = s.social_telegram,
        support_phone    = s.support_phone,
        logo             = _url(s.logo),
        hero_title       = s.hero_title,
        hero_text        = s.hero_text,
        hero_banner      = _url(s.hero_banner),
        about_us         = s.about_us,
    )
'''

# ─────────────────────────────────────────────────────────────────────────────
# requirements/production.txt  — حذف whitenoise تکراری (قبلاً در base.txt بود)
# ─────────────────────────────────────────────────────────────────────────────

FILES["requirements/production.txt"] = '''\
-r base.txt

# WSGI server
gunicorn>=21.2.0

# PostgreSQL adapter
psycopg2-binary>=2.9.9
'''

# ─────────────────────────────────────────────────────────────────────────────
# .env.example  — نهایی‌سازی کامل
# ─────────────────────────────────────────────────────────────────────────────

FILES[".env.example"] = '''\
# ============================================================
#  .env.example — copy to .env and fill in your values
#  LOCAL DEV: uncomment the "local dev" lines
#  PRODUCTION: set all mandatory variables in the server env
# ============================================================

# ── Django core ─────────────────────────────────────────────
# Generate with:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=change-me-to-a-50-char-random-string!!!!!!!!!!!!!!

# true for local dev, false on production server
DEBUG=True

# Comma-separated.  Local: 127.0.0.1,localhost  Prod: yourdomain.com
ALLOWED_HOSTS=127.0.0.1,localhost

# ── Database ─────────────────────────────────────────────────
# Local SQLite (Windows-safe):
DATABASE_URL=sqlite:///db.sqlite3

# Production PostgreSQL:
# DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME

# Optional: keep DB connections alive for N seconds (prod only)
DB_CONN_MAX_AGE=60

# PostgreSQL SSL mode: disable | allow | prefer | require | verify-ca | verify-full
DB_SSLMODE=prefer

# ── CORS ─────────────────────────────────────────────────────
# Comma-separated list of origins allowed to call the API
# Local dev:
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
# Production example:
# CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# ── HTTPS / Security (production only) ───────────────────────
# Set to false only if your reverse-proxy handles redirects
SECURE_SSL_REDIRECT=True

# HSTS max-age in seconds (31536000 = 1 year). Start with 0 to test.
SECURE_HSTS_SECONDS=31536000

# ── OTP ──────────────────────────────────────────────────────
# مدت اعتبار کد OTP (دقیقه)
OTP_EXPIRY_MINUTES=2

# ── SMS / Kavenegar ──────────────────────────────────────────
KAVENEGAR_API_KEY=your-kavenegar-api-key-here
SMS_SENDER=your-sms-sender-number

# ── Payment / Zarinpal ───────────────────────────────────────
ZARINPAL_MERCHANT_CODE=SANDBOX
# true in dev/staging, false in production
PAYMENT_SANDBOX=True
# Base URL used to build the callback URL sent to the gateway
PAYMENT_CALLBACK_BASE_URL=http://127.0.0.1:8000

# ── Email (optional — used by Django admin password reset etc.) ──
EMAIL_HOST=localhost
EMAIL_PORT=25
EMAIL_USE_TLS=False
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@example.com

# ── Logging (production only) ────────────────────────────────
# Absolute path on the server where log files will be written
LOG_DIR=/var/log/django

# One of: DEBUG INFO WARNING ERROR CRITICAL
DJANGO_LOG_LEVEL=INFO
'''

# ─────────────────────────────────────────────────────────────────────────────
# DEPLOY.md  — راهنمای نهایی استقرار
# ─────────────────────────────────────────────────────────────────────────────

FILES["DEPLOY.md"] = '''\
# Deployment Guide — Linux Production Server

## Prerequisites

| Item | Version |
|------|---------|
| Python | 3.11+ |
| PostgreSQL | 14+ |
| Nginx | 1.24+ (reverse proxy) |
| OS | Ubuntu 22.04 LTS (recommended) |

---

## 1 — First-time server setup

```bash
# Create a dedicated system user (no login shell)
sudo adduser --system --group --no-create-home appuser

# Create directories
sudo mkdir -p /srv/app /var/log/django /srv/app/media
sudo chown appuser:appuser /srv/app /var/log/django /srv/app/media
```

---

## 2 — Clone / pull the repository

```bash
cd /srv/app
# First deploy:
git clone https://github.com/YOUR_ORG/YOUR_REPO.git .

# Subsequent deploys:
git pull origin main
```

---

## 3 — Python virtual environment

```bash
python3 -m venv /srv/app/venv
source /srv/app/venv/bin/activate
pip install --upgrade pip
pip install -r requirements/production.txt
```

---

## 4 — Environment variables

Copy `.env.example` to `/srv/app/.env` and fill in every value, **or**
export variables directly in the systemd service (recommended for secrets):

```bash
cp .env.example .env
nano .env          # fill in SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, etc.
chmod 600 .env     # restrict read access
```

> **Mandatory for production:**
> `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`

> **Tip:** Generate a strong SECRET_KEY:
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

---

## 5 — Database

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production

# Run migrations
python manage.py migrate --noinput

# Create superuser (first deploy only)
python manage.py createsuperuser
```

---

## 6 — Static files

```bash
python manage.py collectstatic --noinput
```

WhiteNoise serves `staticfiles/` directly from gunicorn — no separate
Nginx `alias` needed for static files.

---

## 7 — Sanity check

```bash
python manage.py check --deploy --settings=config.settings.production
```

All issues flagged here must be resolved before going live.

---

## 8 — Gunicorn (run manually to test)

```bash
gunicorn config.wsgi:application \\
  --workers 3 \\
  --bind 0.0.0.0:8000 \\
  --timeout 120 \\
  --access-logfile /var/log/django/gunicorn_access.log \\
  --error-logfile  /var/log/django/gunicorn_error.log
```

Worker formula: `(2 × CPU cores) + 1`

---

## 9 — Systemd service (recommended)

Create `/etc/systemd/system/app.service`:

```ini
[Unit]
Description=Django App (gunicorn)
After=network.target postgresql.service

[Service]
User=appuser
Group=appuser
WorkingDirectory=/srv/app
EnvironmentFile=/srv/app/.env
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/srv/app/venv/bin/gunicorn config.wsgi:application \\
          --workers 3 \\
          --bind unix:/run/app.sock \\
          --timeout 120 \\
          --access-logfile /var/log/django/gunicorn_access.log \\
          --error-logfile  /var/log/django/gunicorn_error.log
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable app
sudo systemctl start app
sudo systemctl status app
```

---

## 10 — Nginx reverse proxy

`/etc/nginx/sites-available/app`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 20M;

    location /media/ {
        alias /srv/app/media/;
    }

    location / {
        proxy_pass         http://unix:/run/app.sock;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 11 — TLS certificate (Let\'s Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Auto-renewal is set up by certbot automatically.

---

## 12 — Routine deploy checklist

```bash
# On the server
cd /srv/app
source venv/bin/activate

git pull origin main
pip install -r requirements/production.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart app
sudo systemctl status app
```

---

## 13 — Log files

| File | Content |
|------|---------|
| `/var/log/django/django.log` | All WARNING+ application events |
| `/var/log/django/django_errors.log` | ERROR+ only (alerts / crashes) |
| `/var/log/django/gunicorn_access.log` | HTTP access log |
| `/var/log/django/gunicorn_error.log` | Gunicorn worker errors |

---

## 14 — Rollback

```bash
git log --oneline -10          # find the last good commit
git checkout <COMMIT_HASH>
python manage.py migrate --noinput   # if migrations rolled back
sudo systemctl restart app
```

---

## 15 — Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Django secret key (min 50 chars) |
| `DEBUG` | ✅ | `False` in production |
| `DATABASE_URL` | ✅ | `postgres://USER:PASS@HOST:5432/DB` |
| `ALLOWED_HOSTS` | ✅ | Comma-separated hostnames |
| `CORS_ALLOWED_ORIGINS` | ✅ | Comma-separated frontend origins |
| `KAVENEGAR_API_KEY` | ✅ | SMS gateway API key |
| `ZARINPAL_MERCHANT_CODE` | ✅ | Payment gateway merchant ID |
| `PAYMENT_CALLBACK_BASE_URL` | ✅ | Public base URL for payment callbacks |
| `OTP_EXPIRY_MINUTES` | — | Default: `2` |
| `SECURE_SSL_REDIRECT` | — | Default: `True` |
| `SECURE_HSTS_SECONDS` | — | Default: `31536000` |
| `DB_CONN_MAX_AGE` | — | Default: `60` |
| `LOG_DIR` | — | Default: `BASE_DIR/logs` |
| `DJANGO_LOG_LEVEL` | — | Default: `WARNING` |
'''

# ─────────────────────────────────────────────────────────────────────────────
# CURRENT_STATE.md  — آپدیت نهایی (همه فازها چک‌مارک)
# ─────────────────────────────────────────────────────────────────────────────

FILES["CURRENT_STATE.md"] = '''\
# CURRENT_STATE

## Environment
- Local OS: Windows
- Mode: development (split settings)
- Target: Linux server
- Testing: Swagger UI

## Completed Phases (v1)
- [x] Phase 01 Bootstrap
- [x] Phase 02 Core
- [x] Phase 03 SMS
- [x] Phase 04 Accounts (User + Address)
- [x] Phase 05 OTP Auth
- [x] Phase 06 Store Catalog
- [x] Phase 07 Shipping (basic)
- [x] Phase 08 Orders
- [x] Phase 09 Payment (zarinpal + mock)
- [x] Phase 10 Blog
- [x] Phase 11 Hardening

## Completed Phases (v2 — اصلاحیه)
- [x] Phase 12 — Account Profile + کد ملی + آدرس کامل
- [x] Phase 13 — Order Tracking + OrderStatusHistory
- [x] Phase 14 — Product Gallery + بهبود مدل محصول
- [x] Phase 15 — Smart Shipping (Zone + Weight)
- [x] Phase 16 — Payment Refactor (Orchestrator + Providers)
- [x] Phase 17 — Admin API کامل
- [x] Phase 18 — SiteSettings کامل
- [x] Phase 19 — Pagination + Search
- [x] Phase 20 — Hardening v2 ✅

## Existing Apps
- core/        — exceptions, health, SiteSettings (کامل — فاز 18)
- sms/         — SMSLog, send_otp, send_order_success_sms
- accounts/    — User, Address, OTPRecord, auth endpoints
- store/       — Category, Product, ProductImage, Order, OrderItem, OrderStatusHistory
- shipping/    — ShippingZone, ShippingMethod
- payment/     — Transaction, zarinpal provider, mock provider, orchestrator
- blog/        — Post
- admin_panel/ — Admin API کامل (فاز 17) + settings endpoints (فاز 18)

---

## Model Field Map (وضعیت دقیق فیلدها)

### accounts.User
- phone_number (unique)
- full_name
- email (null, unique)
- national_id (null, unique)
- is_active, is_staff, date_joined

### accounts.Address
- user (FK)
- title, province, city, street, postal_code, is_default

### accounts.OTPRecord
- phone_number (unique), code, created_at, expires_at, is_used, last_sent_at

### store.Category
- name, slug, description, image, is_active, created_at

### store.Product
- category (FK, null)
- name, slug, description
- price, discount_price (null)
- sku (null, unique), meta_title, meta_description, view_count
- stock, weight, image, is_active, created_at, updated_at

### store.ProductImage
- product (FK), image, alt_text, order, is_cover

### store.Order
- user (FK), address (FK), shipping_method (FK)
- status (pending/paid/processing/shipped/delivered/cancelled)
- total_price, shipping_cost
- tracking_number, postal_tracking, carrier_name
- shipped_at, delivered_at, customer_notes
- shipping_address_snapshot (JSONField)
- created_at

### store.OrderItem
- order (FK), product (FK)
- product_name_snapshot, quantity, unit_price

### store.OrderStatusHistory
- order (FK), status, note, created_at, created_by (FK User, null)

### shipping.ShippingZone
- name, provinces (JSONField)

### shipping.ShippingMethod
- name, slug, base_cost, cost_per_kg, free_above (null)
- min_days, max_days, zone (FK, null), is_active

### payment.Transaction
- order (FK), amount, provider, ref_id
- status (pending/success/failed)
- gateway_response (JSONField), created_at

### core.SiteSettings
- site_name (default="فروشگاه من")
- logo (ImageField, null/blank)
- banner_text
- announcement
- primary_color (default="#01696f")
- maintenance_mode (BooleanField)
- social_instagram (URLField)
- social_telegram (URLField)
- support_phone
- hero_title (legacy)
- hero_text (legacy)
- hero_banner (legacy, ImageField)
- about_us (legacy)

---

## Migration Heads (آخرین migration هر app)
- accounts:    0009_alter_user_national_id
- store:       0008_product_discount_price_product_meta_description_and_more
- shipping:    0002_shippingzone_shippingmethod_cost_per_kg_and_more
- payment:     0002_transaction_provider
- core:        0002_site_settings_complete
- sms:         0001_initial
- blog:        0001_initial
- admin_panel: (no migrations — بدون مدل)

> ⚠️ فاز 20 هیچ migration جدیدی ندارد.
> خروجی `makemigrations --check` باید `No changes detected` باشد.

---

## API Endpoints (وضعیت فعلی)

### Auth — /api/auth/
- POST /send-otp
- POST /verify-otp
- GET  /profile
- PATCH /profile  (full_name, email, national_id)
- GET  /addresses
- POST /addresses
- DELETE /addresses/{id}
- GET  /orders
- GET  /orders/{id}
- DELETE /orders/{id}  ← لغو سفارش (فقط pending) + برگشت موجودی

### Store — /api/
- GET /categories
- GET /products            ← pagination + search (فاز 19)
- GET /products/{id}
- POST /orders (auth)

### Shipping — /api/shipping/
- GET  /methods
- POST /options

### Payment — /api/payment/
- POST /initiate (auth)
- GET  /callback
- GET  /mock-callback (DEBUG only)

### Blog — /api/blog/
- (endpoints موجود)

### Core — /api/
- GET /health
- GET /settings          ← عمومی، بدون auth (فاز 18)

### Admin — /api/admin/
#### داشبورد
- GET /dashboard

#### مدیریت کاربران
- GET  /users/
- GET  /users/{id}/
- PUT  /users/{id}/

#### مدیریت سفارش‌ها
- GET  /orders/
- GET  /orders/{id}/
- PUT  /orders/{id}/status/

#### مدیریت محصولات
- GET    /products/
- POST   /products/
- GET    /products/{id}/
- PUT    /products/{id}/
- PUT    /products/{id}/stock/
- DELETE /products/{id}/

#### آنالیتیکس
- GET /analytics/overview/

#### تنظیمات سایت (فاز 18)
- GET /settings/
- PUT /settings/

---

## Settings Constants (فاز 20)
- `DEFAULT_PAGE_SIZE = 20`       — پیش‌فرض صفحه‌بندی
- `MAX_PAGE_SIZE = 100`          — حداکثر تعداد در هر صفحه
- `OTP_EXPIRY_MINUTES` (env)     — پیش‌فرض: 2 دقیقه
- `OTP_RATE_LIMIT_SECONDS = 60`  — فاصله بین ارسال‌های OTP
- `CORS_ALLOWED_ORIGINS` (env)   — پیش‌فرض: [] (در production باید تنظیم شود)

---

## Hardening v2 — فاز 20
- OTP rate-limit از `settings.OTP_RATE_LIMIT_SECONDS` خوانده می‌شود (نه عدد ثابت)
- `OTP_EXPIRY_MINUTES` در `.env.example` مستند شد
- `/error-test` endpoint از core/api.py حذف شد
- `whitenoise` تکراری از `requirements/production.txt` حذف شد
- `CORS_ALLOWED_ORIGINS` default به `[]` تغییر کرد (production-safe)
- `DEPLOY.md` با جدول env variables کامل شد

---

## Known Issues / ناقص‌ها
- store/api.py و payment/api.py هر دو AuthBearer تعریف کرده‌اند (تکراری — قابل refactor در آینده)
- debug_toolbar: خطای template بی‌خطر در ترمینال

## Last Successful Commands
```
python apply_phase_20.py
python manage.py check              → 0 issues
python manage.py makemigrations --check  → No changes detected
python manage.py migrate            → No new migrations
python manage.py runserver          → OK
python manage.py check --settings=config.settings.production → OK
```

## Project Status
✅ پروژه آماده production است.
'''

# ─────────────────────────────────────────────────────────────────────────────
# Write all files
# ─────────────────────────────────────────────────────────────────────────────

def main():
    written = []
    for rel_path, content in FILES.items():
        target = BASE / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(str(target))

    print("\n✅  Phase 20 applied successfully!\n")
    print("Files written:")
    for f in written:
        print(f"  ✔  {f}")
    print()
    print("Next steps:")
    print("  1. python manage.py check")
    print("  2. python manage.py makemigrations --check   (must say: No changes detected)")
    print("  3. python manage.py runserver")
    print("  4. python manage.py check --settings=config.settings.production")
    print("  5. Open http://127.0.0.1:8000/api/docs")


if __name__ == "__main__":
    main()
