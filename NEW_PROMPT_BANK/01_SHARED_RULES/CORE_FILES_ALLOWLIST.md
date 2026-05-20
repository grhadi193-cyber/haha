# CORE FILES ALLOWLIST

These files may be rewritten in any phase if needed:
- manage.py
- config/settings/base.py
- config/settings/local.py
- config/settings/production.py
- config/urls.py
- requirements/base.txt
- requirements/local.txt
- requirements/production.txt
- .env.example

Per-app support files allowed when necessary:
- {app}/admin.py
- {app}/apps.py
- {app}/managers.py
- {app}/permissions.py
- {app}/tests.py
- {app}/utils.py
- {app}/migrations/__init__.py
- {app}/__init__.py

## Migration Rules
- Every model change requires a migration file in the patch script
- Migration file must be a valid Django migration (not just a stub)
- Migrations must include correct dependencies chain
- Use sequential numbering: 0004_, 0005_, etc.
