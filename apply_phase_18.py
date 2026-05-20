# apply_phase_18.py
# Phase 18 — SiteSettings کامل
# اجرا: python apply_phase_18.py  (از ریشه پروژه)

import pathlib, sys

ROOT = pathlib.Path(__file__).parent
created = []

def w(rel, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    created.append(str(rel))

# ─────────────────────────────────────────────────────────────────────────────
# 1. core/models.py
# ─────────────────────────────────────────────────────────────────────────────
w("core/models.py", '''\
from django.db import models


class SiteSettings(models.Model):
    # ── فیلدهای جدید (فاز 18) ─────────────────────────────────────────────
    site_name        = models.CharField(max_length=200, default="فروشگاه من")
    logo             = models.ImageField(upload_to="site/", null=True, blank=True)
    banner_text      = models.CharField(max_length=500, blank=True)
    announcement     = models.TextField(blank=True)
    primary_color    = models.CharField(max_length=7, default="#01696f")
    maintenance_mode = models.BooleanField(default=False)
    social_instagram = models.URLField(blank=True)
    social_telegram  = models.URLField(blank=True)
    support_phone    = models.CharField(max_length=20, blank=True)

    # ── فیلدهای قدیمی — نگه‌داری شده ────────────────────────────────────
    hero_title  = models.CharField(max_length=200, blank=True, default="Welcome to our store")
    hero_text   = models.TextField(blank=True, default="Best products at best prices.")
    hero_banner = models.ImageField(upload_to="banners/", null=True, blank=True)
    about_us    = models.TextField(blank=True)

    class Meta:
        verbose_name        = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return "تنظیمات اصلی سایت"

    @classmethod
    def get(cls):
        """Singleton getter — همیشه ردیف pk=1 را برمی‌گرداند."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
''')

# ─────────────────────────────────────────────────────────────────────────────
# 2. core/migrations/0002_site_settings_complete.py
# ─────────────────────────────────────────────────────────────────────────────
w("core/migrations/0002_site_settings_complete.py", '''\
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="site_name",
            field=models.CharField(default="\\u0641\\u0631\\u0648\\u0634\\u06af\\u0627\\u0647 \\u0645\\u0646", max_length=200),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="logo",
            field=models.ImageField(blank=True, null=True, upload_to="site/"),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="banner_text",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="announcement",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="primary_color",
            field=models.CharField(default="#01696f", max_length=7),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="maintenance_mode",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="social_instagram",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="social_telegram",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="support_phone",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
''')

# ─────────────────────────────────────────────────────────────────────────────
# 3. core/api.py
# ─────────────────────────────────────────────────────────────────────────────
w("core/api.py", '''\
from typing import Optional

from ninja import Router
from pydantic import BaseModel

from core.exceptions import NotFoundError

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


@router.get("/error-test", summary="Exception handler smoke-test")
def error_test(request):
    """
    Raises NotFoundError so you can verify the global handler
    returns structured JSON instead of an HTML 500.
    Remove or guard this endpoint before going to production.
    """
    raise NotFoundError("This is a test error from the global handler.")


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
''')

# ─────────────────────────────────────────────────────────────────────────────
# 4. core/admin.py
# ─────────────────────────────────────────────────────────────────────────────
w("core/admin.py", '''\
from django.contrib import admin

from core.models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """
    SiteSettings singleton — در پنل ادمین Django قابل ویرایش.
    کاربر نمی‌تواند ردیف جدید اضافه یا حذف کند؛ فقط ردیف pk=1 موجود است.
    """

    fieldsets = (
        ("هویت سایت", {
            "fields": ("site_name", "logo", "primary_color"),
        }),
        ("محتوای صفحه اصلی", {
            "fields": ("banner_text", "announcement", "hero_title", "hero_text", "hero_banner", "about_us"),
        }),
        ("شبکه‌های اجتماعی و پشتیبانی", {
            "fields": ("social_instagram", "social_telegram", "support_phone"),
        }),
        ("وضعیت سایت", {
            "fields": ("maintenance_mode",),
        }),
    )

    def has_add_permission(self, request):
        """فقط یک ردیف مجاز است."""
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
''')

# ─────────────────────────────────────────────────────────────────────────────
# 5. admin_panel/api.py — اضافه کردن settings endpoints به انتهای فایل موجود
# ─────────────────────────────────────────────────────────────────────────────
ADMIN_API_PATH = ROOT / "admin_panel" / "api.py"
existing = ADMIN_API_PATH.read_text(encoding="utf-8")

SETTINGS_BLOCK = '''

# ─────────────────────────────────────────────────────────────────────────────
# SiteSettings  (Phase 18)
# ─────────────────────────────────────────────────────────────────────────────

class AdminSiteSettingsOut(BaseModel):
    site_name:        str
    banner_text:      str
    announcement:     str
    primary_color:    str
    maintenance_mode: bool
    social_instagram: str
    social_telegram:  str
    support_phone:    str
    logo:             Optional[str] = None
    hero_title:       str
    hero_text:        str
    hero_banner:      Optional[str] = None
    about_us:         str

    model_config = {"from_attributes": True}


class AdminSiteSettingsUpdateIn(BaseModel):
    site_name:        Optional[str]  = None
    banner_text:      Optional[str]  = None
    announcement:     Optional[str]  = None
    primary_color:    Optional[str]  = None
    maintenance_mode: Optional[bool] = None
    social_instagram: Optional[str]  = None
    social_telegram:  Optional[str]  = None
    support_phone:    Optional[str]  = None
    hero_title:       Optional[str]  = None
    hero_text:        Optional[str]  = None
    about_us:         Optional[str]  = None


def _settings_to_out(s, request) -> AdminSiteSettingsOut:
    def _url(field):
        if field and hasattr(field, "url"):
            try:
                return request.build_absolute_uri(field.url)
            except Exception:
                return None
        return None

    return AdminSiteSettingsOut(
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


@router.get(
    "/settings/",
    auth=_auth,
    response=AdminSiteSettingsOut,
    summary="دریافت تنظیمات سایت (ادمین)",
)
def admin_get_settings(request):
    """تنظیمات کامل سایت را برمی‌گرداند."""
    from core.models import SiteSettings
    return _settings_to_out(SiteSettings.get(), request)


@router.put(
    "/settings/",
    auth=_auth,
    response=AdminSiteSettingsOut,
    summary="بروزرسانی تنظیمات سایت (ادمین)",
)
def admin_update_settings(request, payload: AdminSiteSettingsUpdateIn):
    """
    هر فیلدی که در body ارسال شود (غیر از None) آپدیت می‌شود.
    فیلدهای ارسال‌نشده یا None تغییر نمی‌کنند.
    آپلود لوگو/بنر از این endpoint پشتیبانی نمی‌شود — از /admin Django بارگذاری کنید.
    """
    from core.models import SiteSettings
    s = SiteSettings.get()

    updatable_fields = [
        "site_name", "banner_text", "announcement", "primary_color",
        "maintenance_mode", "social_instagram", "social_telegram",
        "support_phone", "hero_title", "hero_text", "about_us",
    ]
    update_fields = []
    for field in updatable_fields:
        value = getattr(payload, field, None)
        if value is not None:
            setattr(s, field, value)
            update_fields.append(field)

    if update_fields:
        s.save(update_fields=update_fields)

    return _settings_to_out(s, request)
'''

# guard: فقط یک بار اضافه کن
if "admin_get_settings" not in existing:
    new_content = existing.rstrip() + "\n" + SETTINGS_BLOCK + "\n"
    ADMIN_API_PATH.write_text(new_content, encoding="utf-8")
    created.append("admin_panel/api.py")
else:
    print("admin_panel/api.py — settings block already present, skipped.")

# ─────────────────────────────────────────────────────────────────────────────
print("\n✅  Phase 18 applied. Files written:")
for f in created:
    print(f"    {f}")
print("\nNext steps:")
print("  pip install -r requirements/local.txt")
print("  python manage.py check")
print("  python manage.py makemigrations --check")
print("  python manage.py migrate")
print("  python manage.py runserver")
