<img width="1366" height="603" alt="Screenshot (4)" src="https://github.com/user-attachments/assets/36de532a-264d-409f-8575-bec3bc0a6bef" />
# Ledgerly — Personal Finance & Spending Analytics

A Flask application for private, database-backed income and expense tracking. The initial implementation includes account registration and password reset tokens, owner-scoped transaction CRUD and CSV export, user budgets, date-filtered personal dashboards/reports, administrator-managed categories and reasons, account status management, audit events, and privacy-suppressed aggregate age-band analytics for administrators and the community.

## Architecture and data model

```text
User 1 ─── * Transaction * ─── 1 Category 1 ─── * Reason
  │               │
  ├── 1 ─── * Budget ────────────────┘
  └── 1 ─── * AuditLog (actor; nullable when an account is removed)
```

`transactions` contain a positive `DECIMAL(12,2)` amount, type, date, owner, category, reason, optional notes/payment method/recurring reference, and UTC event timestamps. Category/reason references use restrictive deletion so historical transactions remain interpretable; categories and reasons can be deactivated or archived rather than removed. Budgets are unique per user/category/month and hold a configurable threshold. Birth dates are stored (not age); age bands are calculated as of the report end date.

The app factory in `app/__init__.py` configures shared extensions and Blueprints. SQLAlchemy models and analytics services are separated from route handlers. MySQL 8 is the production database; SQLite is used only for isolated tests. The admin analytics endpoints return aggregates, suppress groups with fewer than ten participants, and disclose coverage/sample size and the participating-user limitation. Migrations are maintained by Flask-Migrate.

Authenticated users can open **Community insights** at `/community/`. The page aggregates existing income and expense transactions for active, non-administrator users who have a recorded date of birth showing age 18 or older and at least one transaction in the selected period and currency. Age comparisons are calculated as of the current application-local date; users without a date of birth, users under 18, inactive accounts, administrators, and period non-contributors are excluded. Per-person averages divide by distinct eligible contributors, including zero income or spending for a contributor who recorded only the other transaction type. Amounts in different preferred currencies are never added or converted. The default privacy cohort minimum is 10, configurable with `COMMUNITY_ANALYTICS_MIN_GROUP_SIZE`; `COMMUNITY_ANALYTICS_CATEGORY_LIMIT` controls how many top categories appear before safely eligible remainder categories are combined as “Other.” Small category groups are withheld as a whole, and time series and overview totals are withheld when a reporting interval is below the cohort threshold. This application records positive `income` and `expense` transaction types only; it has no separate transfer, refund, or transaction-status model, so all non-deleted records of those two types are included.

## Requirements

- Python 3.10+
- MySQL 8.0+
- pip and a virtual environment

## Local setup (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set a cryptographically random `SECRET_KEY` (for example, `python -c "import secrets; print(secrets.token_urlsafe(48))"`), `DATABASE_URL`, and local mail settings. Never commit `.env` or use the sample database credential in production.
For local HTTP development with `flask run`, set `SESSION_COOKIE_SECURE=0`; retain `1` behind HTTPS in production.

Create the MySQL database and restricted application account as a DBA:

```sql
CREATE DATABASE personal_finance
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'finance_user'@'localhost' IDENTIFIED BY 'replace-with-a-strong-secret';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON personal_finance.* TO 'finance_user'@'localhost';
CREATE USER 'finance_migrator'@'localhost' IDENTIFIED BY 'use-a-separate-strong-secret';
GRANT ALL PRIVILEGES ON personal_finance.* TO 'finance_migrator'@'localhost';
```

Set `DATABASE_URL=mysql+pymysql://finance_user:<URL-ENCODED-PASSWORD>@localhost:3306/personal_finance?charset=utf8mb4`. For a local-only SQLite smoke test, set `DATABASE_URL=sqlite:///instance/finance.sqlite`.

## Database and initial accounts

```powershell
$env:FLASK_APP = "run.py"
$env:DATABASE_URL = "mysql+pymysql://finance_migrator:<URL-ENCODED-PASSWORD>@localhost:3306/personal_finance?charset=utf8mb4"
flask db upgrade
$env:DATABASE_URL = "mysql+pymysql://finance_user:<URL-ENCODED-PASSWORD>@localhost:3306/personal_finance?charset=utf8mb4"
flask create-admin
```

The initial schema revision is checked in. For subsequent model changes, create and review a new revision with `flask db migrate -m "Describe schema change"` and apply it with `flask db upgrade`. `create-admin` prompts securely for email, name, and a password; it never creates a default credential. `flask seed-dev` adds baseline categories/reasons and is for development only. `flask db-check` checks configured database connectivity. Commit reviewed migration revisions to Git; do not commit local database files.
Use the separate migration account only for migration commands; keep the restricted `finance_user` URL in the deployed application's environment.

## Run and test

```powershell
flask run
python -m pytest -q
```

Tests create a separate in-memory SQLite database per test app. Test values are synthetic. MySQL-specific deployment/migration validation should additionally run against a disposable MySQL 8 database before release.

## Security and privacy notes

- All browser forms use Flask-WTF CSRF protection; state changes are POST-only.
- Authentication routes are rate-limited. Passwords are Werkzeug hashes; reset tokens are signed and expire after 30 minutes.
- Session cookies are HTTP-only, SameSite=Lax and Secure by default. Set `SESSION_COOKIE_SECURE=0` only for local HTTP development.
- Every user financial-data query scopes to the signed-in user's ID. The admin UI has account-management access but no individual transaction-history UI.
- Admin aggregate charts suppress age/category/reason groups below ten participants. Results describe registered participating users, not the general population. Admin selects one preferred currency at a time; amounts are not converted between currencies. A user's preferred currency cannot be changed after financial records exist, preventing old values from being relabeled as a different currency.
- Community insights are available to authenticated users and return aggregate-only responses. The community cohort and each date-filtered category, age-group, and time-series breakdown are subject to minimum-group suppression; no individual financial records or identifying user fields are sent to the browser.
- Configure SMTP (`MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`) to deliver password reset links; without mail configuration, reset URLs are not exposed to production responses.
- Use HTTPS, a production WSGI server, managed secrets, backups, monitoring, and a durable shared rate-limit store in deployment. The default in-memory limiter is for local development and single-process tests only. Review proxy/network configuration before trusting client IPs for rate limits.
- Configure the host and app timezone deliberately. Transaction dates are local calendar dates; event timestamps are UTC.

## Known implementation boundaries

The daily period report supports custom/today/month/year range filters and CSV export; date grouping is SQL-based. User transaction records are never included in admin analytics. Multi-currency conversion, bank synchronization, recurring transaction execution, and emailed reset delivery are not enabled unless SMTP is configured; currency denotes the user's display preference and is not an exchange-rate conversion.
