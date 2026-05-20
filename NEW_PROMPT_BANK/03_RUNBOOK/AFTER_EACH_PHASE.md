# بعد از هر فاز دقیقاً این مراحل را طی کن

## ۱. اجرای patch script
```
python apply_phase_XX.py
```
انتظار: لیست فایل‌های ساخته/آپدیت‌شده چاپ شود

## ۲. نصب پکیج‌ها (اگر requirements تغییر کرد)
```
pip install -r requirements/local.txt
```
انتظار: نصب بدون error

## ۳. بررسی سلامت پروژه
```
python manage.py check
```
انتظار: System check identified no issues

## ۴. مایگریشن
```
python manage.py makemigrations
python manage.py migrate
```
انتظار: OK — بدون conflicts

## ۵. اجرای سرور
```
python manage.py runserver
```
انتظار: سرور بدون crash روی ۸۰۰۰ بالا بیاید

## ۶. تست Swagger
آدرس: http://127.0.0.1:8000/api/docs
انتظار: endpoint‌های همان فاز دیده شوند

## ۷. تست دقیق
فقط endpoint‌های همان فاز را تست کن (طبق VERIFY_PHASE_XX.md)
endpoint‌های قبلی را یک بار spot-check کن تا regression نداشته باشی

## ۸. آپدیت CURRENT_STATE.md
patch script این کار رو خودکار انجام می‌ده.
فقط چک کن فایل درست آپدیت شده:
- فاز مربوطه چک‌مارک خورده باشه [x]
- Next Phase به فاز بعدی اشاره کنه

## ۹. گیت
```
git add .
git commit -m "phase XX complete: [توضیح کوتاه فارسی]"
```

## ۱۰. قدم بعدی
فقط بعد از پاس شدن تمام موارد بالا سراغ فاز بعدی برو
