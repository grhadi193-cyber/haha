# NEW_PROMPT_BANK — Enhancement Phases (12–16)

این بانک پرامپت برای اعمال تغییرات جدید روی بک‌اند کامل شده (11 فاز) طراحی شده است.

## چطور استفاده کنی

### شروع هر سشن
1. یک چت جدید با Claude باز کن
2. ابتدا محتوای `00_CONTEXT/SESSION_PROMPT.md` را paste کن
3. سپس این فایل‌ها را ضمیمه کن (یا paste کن):
   - `00_CONTEXT/ARCHITECTURE.md`
   - `00_CONTEXT/CURRENT_STATE.md`
   - `00_CONTEXT/DECISIONS.md`
   - `00_CONTEXT/FILE_REGISTRY.md`
4. بعد محتوای فاز مورد نظر از `02_PHASES/` را paste کن

### ترتیب اجرا (مهم!)
فازها باید به ترتیب اجرا شوند چون وابستگی دارند:

```
Phase 12 → Phase 13 → Phase 14 → Phase 15 → Phase 16
```

- Phase 12 باید قبل از Phase 16 اجرا شود (tracking_number روی Order)
- Phase 15 باید قبل از Phase 16 اجرا شود (AdminBearer pattern)
- Phase 13 و 14 مستقل هستند (می‌توانند در هر ترتیبی بعد از 12 اجرا شوند)

## ساختار فایل‌ها

```
NEW_PROMPT_BANK/
├── 00_CONTEXT/
│   ├── SESSION_PROMPT.md      ← اول paste کن
│   ├── ARCHITECTURE.md        ← معماری پروژه
│   ├── CURRENT_STATE.md       ← وضعیت فعلی + چک‌لیست فازها
│   ├── DECISIONS.md           ← تصمیمات طراحی هر فاز
│   └── FILE_REGISTRY.md       ← فایل‌های تغییرپذیر هر فاز
├── 01_SHARED_RULES/
│   ├── OUTPUT_CONTRACT.md     ← فرمت خروجی اجباری
│   └── CORE_FILES_ALLOWLIST.md
├── 02_PHASES/
│   ├── phase-12-user-profile-order-tracking.md
│   ├── phase-13-smart-shipping-calculator.md
│   ├── phase-14-multi-image-products.md
│   ├── phase-15-blog-publish-fix.md
│   └── phase-16-admin-panel-api.md
└── 03_RUNBOOK/
    ├── AFTER_EACH_PHASE.md    ← مراحل بعد از هر فاز
    ├── PHASE_CHECKLIST.md     ← چک‌لیست کلی
    └── BUG_REPORT_TEMPLATE.md

```

## خلاصه تغییرات هر فاز

| فاز | عنوان | تغییرات اصلی |
|-----|-------|--------------|
| 12 | پروفایل کاربر و ردیابی سفارش | email روی User، tracking_number روی Order، /auth/profile، /auth/orders |
| 13 | حساب‌گر هوشمند ارسال | ShippingZoneRule، وزن+استان، /shipping/estimate |
| 14 | چند تصویر برای محصول | ProductImage، gallery در detail API، inline در admin |
| 15 | رفع باگ انتشار بلاگ | CRUD admin API برای پست، AdminBearer، published_at auto-set |
| 16 | API پنل مدیریت | app جدید admin_panel، مدیریت کاربر/محصول/سفارش/آمار/SiteConfig |
