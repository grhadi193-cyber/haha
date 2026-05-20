# fix_phase12_migration_merge.py
from pathlib import Path

files = {}

# accounts migration
files["accounts/migrations/0004_user_email.py"] = '''\
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_address_options_alter_user_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
    ]
'''

# store migration
files["store/migrations/0005_order_tracking_fields.py"] = '''\
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0004_alter_category_name_alter_category_slug_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="tracking_number",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="order",
            name="postal_tracking",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
'''

# delete conflicting phase12 root migrations if present
for rel in [
    "accounts/migrations/0001_phase12_user_email.py",
    "store/migrations/0001_phase12_order_tracking_fields.py",
]:
    p = Path(rel)
    if p.exists():
        p.unlink()
        print(f"  🗑️  deleted {p}")

for path_str, content in files.items():
    p = Path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"  ✅  written {p}")

print("\nDone. Now run:")
print("    python manage.py makemigrations")
print("    python manage.py migrate")