# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with real values

# Run development server (port 6768)
python run.py

# Seed/reset database with sample data
python seed.py

# Run tests
pytest tests/ -v

# Run a single test file
pytest tests/test_auth.py -v

# Run with coverage
pip install pytest-cov
pytest --cov=app tests/
```

`run.py` reads `FLASK_ENV` to select config: `development` (default), `production`, or `testing`.

## Architecture

This is the backend for **律航出海 (LexPort)**, a legal AI platform for Chinese manufacturers expanding into Africa.
It's a Flask REST API serving a React SPA frontend (in `../lexport-frontend`).

**Core stack**: Python 3.12, Flask 3.x, MySQL + SQLAlchemy ORM, PyJWT for auth, bcrypt for password hashing, dotenv for
configuration.

### Project Structure

```
run.py                    # Entry point
config.py                 # Config classes (Dev/Prod/Test) from env vars
seed.py                   # Seed DB from ../lexport-frontend/docs/data.json
app/
  __init__.py             # create_app() factory
  extensions.py           # db, mail instances (lazy-init pattern)
  models/                 # SQLAlchemy models (one file per table)
  routes/                 # Flask blueprints (one file per resource group)
  services/               # Business logic layer (routes delegate to services)
  utils/                  # JWT helpers, validators, decorators, custom error classes
docs/
  db.md                   # Database schema docs
  api.md                  # API endpoint docs with request/response tables
tests/                    # pytest tests
```

### Key Patterns

- **App factory**: `create_app()` in `app/__init__.py` — creates Flask app, loads config, inits extensions, registers
  blueprints, creates `platform_stats` VIEW, and registers global error handlers. Enables per-test app instances with
  different configs.
- **Service layer**: Routes parse HTTP input and format JSON output. All business logic lives in `app/services/`.
  Services raise `AppError` subclasses; a global error handler (`@app.errorhandler(AppError)`) converts them to JSON.
- **Response envelope**: All responses use `{ "success": bool, "data": ..., "message": "..." }`. Errors use
  `{ "success": false, "error": { "code": "...", "message": "..." } }`.
- **Blueprint URL prefixes**: Each resource group is a Blueprint with its own prefix (`/api/auth`, etc.). Registered in
  `app/routes/__init__.py`. Blueprint variable name and `url_prefix` are independent — always check `register_blueprints()` for the actual mapping.
- **JWT token types**: Two types — `"access"` (login sessions, 1hr default) and `"verify_email"` (email verification,
  30min). The `type` claim prevents token type confusion.

### Error Handling

Custom exception hierarchy in `app/utils/errors.py`:
```
AppError(code, message, http_status=400)
├── ValidationError   (400) — input validation failures
├── AuthenticationError (401/403) — auth failures, supports role-based 403
├── ConflictError     (409) — duplicate username/email
└── NotFoundError     (404) — resource not found
```

Services raise these; the global handler in `create_app()` catches `AppError` and calls `error.to_response()`. A
catch-all 500 handler returns the generic envelope for unexpected errors.

### Auth Flow

- Login accepts username OR email in a single `login_id` field (determined by presence of `@`).
- Email is optional on registration. If provided, a verification JWT is emailed in a background thread.
- Passwords must be 8+ chars with both letters and digits.
- Usernames: 3-50 chars, alphanumeric + underscores only.

**JWT decorator** (`app/utils/auth_utils.py`):
```python
@jwt_required           # any authenticated user
@jwt_required(role='admin')  # admin only (returns 403 for others)
```
Sets `g.current_user` to the `User` model instance. Can be used as `@jwt_required` or `@jwt_required()`.

### Role-Based Access Control

Three roles on `users.role`: `user`, `editor`, `admin`.

- **user**: Regular end-user, can access public endpoints and their own profile.
- **editor**: Can create/update content via admin APIs, but changes go to `draft` status (pending admin review).
- **admin**: Full CRUD, changes publish immediately (`published` status), can approve drafts via
  `POST /api/admin/{resource}/{id}/approve`, and can manage user roles (except other admins).

### Admin CRUD + Draft/Publish Workflow

`/api/admin/{resource}` supports `laws`, `news`, `agencies`. Key behavior:
- `admin` creates/updates → status = `published` directly.
- `editor` creates/updates → status = `draft` automatically.
- `GET /api/admin/{resource}?status=draft` lists pending items.
- `POST /api/admin/{resource}/{id}/approve` (admin only) publishes a draft.
- `DELETE` is admin-only; editors get 403.

Implementation: `routes/admin.py` delegates to `services/admin_service.py`, which uses reflection-based
`_admin_to_dict()` to serialize any model generically (iterates `item.__table__.columns`).

### Models with `to_dict()` + Content Tables

Each model defines `to_dict()` returning a dict of public fields. Special models:
- **`LawText` / `NewsText`** (`models/content.py`) — separate 1:1 tables storing uploaded document references
  for laws and news (currently `filename` field), keeping the main tables lightweight for list queries.
  `law_id` / `news_id` as PK + FK with CASCADE delete.

### Database

- MySQL accessed via SQLAlchemy with `pymysql` driver (pure Python, no mysqlclient C dependency).
- Connection URI format: `mysql+pymysql://user:pass@host:port/dbname`
- For development, `db.create_all()` creates tables on startup plus a `platform_stats` VIEW. For production, use
  Flask-Migrate/Alembic.
- All string columns should use `utf8mb4_unicode_ci` collation.

### Seed Data

`seed.py` reads `../lexport-frontend/docs/data.json` and populates all reference/lookup tables plus sample content.
Runs in FK dependency order and clears existing data first. Requires the frontend repo to be cloned alongside.

### Frontend Relationship

The frontend (`../lexport-frontend`) is a React SPA. All auth and data APIs are served by this backend. The
`src/services/` directory in the frontend is ready for API client modules. Frontend-to-backend traffic goes through a
reverse proxy (no CORS needed).
