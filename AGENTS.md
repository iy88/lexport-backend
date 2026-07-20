# Repository Guidelines

## Project Structure & Module Organization

`run.py` starts the Flask application; `config.py` defines development, production, and in-memory testing configurations. Application code lives under `app/`: models map SQLAlchemy tables, routes expose resource-specific Blueprints, services contain business logic, and utils provide JWT, validation, authorization, and error helpers. Register new Blueprints in `app/routes/__init__.py`. Keep API and schema documentation in `docs/`. `bits/` contains one-off data utilities, while `sql/` and `uploads/` contain local data artifacts and are ignored by Git.

## Setup, Run, and Verification Commands

Use Python 3.12 and an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

The server defaults to `0.0.0.0:6768`. Configure MySQL, SMTP, JWT secrets, and upload storage in `.env`. Set `FLASK_ENV=production` or `FLASK_ENV=testing` to select another configuration. There is no compile/build step.

## Coding Style & Naming Conventions

Follow PEP 8 with four-space indentation. Use `snake_case` for modules, functions, variables, and API helpers; use `PascalCase` for model and configuration classes. Keep routes thin: parse HTTP input, call `app/services/`, and format the standard `{success, data, message}` response. Put reusable failures in `app/utils/errors.py`. Prefer one resource per matching model, route, and service module (for example, `law.py`). No formatter or linter is currently configured, so keep imports grouped and changes consistent with nearby code.

## Testing Guidelines

The app factory provides `TestingConfig` with an in-memory SQLite database, but no tests are currently committed. Add pytest tests under `tests/`, named `test_<feature>.py`, and use `create_app('testing')` in fixtures. Install pytest as a development dependency, then run `python -m pytest tests/ -v`; for coverage, use `python -m pytest --cov=app tests/`. Cover service behavior, authorization boundaries, validation failures, and response schemas.

## Commit & Pull Request Guidelines

Recent history primarily uses Conventional Commit prefixes such as `feat:`, `fix:`, `refactor:`, and `chore:`. Keep commits focused and subjects imperative. Pull requests should explain the behavior change, list configuration or schema impacts, link relevant issues, and include test commands/results. For API changes, update `docs/api.md` and provide representative request/response examples; include screenshots only when rendered output is affected.

## Security & Configuration

Never commit `.env`, credentials, JWT secrets, database dumps, or uploaded documents. Add new settings to `.env.example` with safe placeholders. Validate filenames and authorization before exposing files from `UPLOAD_PATH`.
