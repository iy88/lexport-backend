# LexPort Backend MVP Production Fix Plan

## 1. Purpose and delivery boundary

This document is the implementation specification for hardening the existing Flask backend for a public MVP. It is self-contained: an implementation agent should be able to execute it without relying on prior conversations.

The implementation must preserve the current Flask, SQLAlchemy, MySQL, Redis, Celery, Alibaba Cloud OSS, Bailian, JWT, and SMTP architecture. It must not introduce a migration framework, an attachment persistence table, Gunicorn/Nginx configuration, health endpoints, structured logging, or a new token storage mechanism.

The work is complete only when the database migration artifacts, backend behavior, automated API tests, and existing backend documentation agree with this specification.

### 1.1 Locked product decisions

- `user` may use public APIs, manage their profile, and access only their own compliance reports.
- `editor` may access the content backend, jointly edit any editor draft, and read/create/update reference data.
- `admin` has all backend permissions.
- Editors share drafts. Draft ownership and `created_by` fields must not be introduced.
- Reference-data deletion, content approval/suspension/draft discard, user management, and backend report management are admin-only.
- New registration requires an email address. A verified email is required to create a compliance report.
- Registration is open and does not use invitation codes.
- Login is not rate-limited.
- Reports have no daily quota and no active-task-count quota.
- Report creation is limited to five requests per minute per non-admin user; admins are exempt only from this report limit.
- Report creation uses database-backed idempotency.
- Compliance attachments remain temporary OSS objects. No attachment table is added; the OSS bucket lifecycle deletes them after one day.
- MySQL may continue to use the `root` account. Production validation must not reject it.
- Application startup must stop executing automatic schema DDL.

## 2. Current defects to fix

The implementation must address all of the following concrete defects.

1. Many `/api/admin/*` routes use only `@jwt_required`, allowing a registered `user` to call content and reference-data administration APIs.
2. Service code treats every non-admin account as an editor instead of explicitly authorizing the `editor` role.
3. Public news detail loads a row by ID without requiring `status='published'`, exposing drafts through ID enumeration.
4. When an editor updates published news, metadata is drafted but `news_text` and tag relations are changed immediately, bypassing approval.
5. Generic News/Agency draft handling changes a published main row to `draft`, removing the old published version from public APIs while a change is pending.
6. News and Agency cannot represent `published + pending draft` consistently in list responses or filters.
7. Production accepts fixed development secrets, unknown environment names silently fall back to development, and the MySQL URI is assembled by unsafe string interpolation.
8. API, Celery worker, Celery Beat, and utility-script startup can run `db.create_all()` and recreate `platform_stats`.
9. Registration, verification-email sending, and paid report creation lack the agreed rate limits.
10. A timed-out report POST can be retried after Bailian has already accepted the first request, creating duplicate paid tasks.
11. Partial OSS uploads and later Bailian/database failures can leave temporary orphan objects until bucket cleanup.
12. Pagination is not uniformly bounded; news tag metadata queries load all matching IDs before pagination.
13. `news_tag_relations.news_id` does not consistently cascade on news deletion.
14. Malformed JWT subject values can cause internal errors instead of authentication failures.
15. Automated tests cover primarily the Law OSS workflow, not the public/admin API security boundary.

## 3. Authorization contract

### 3.1 Permission matrix

| Capability | user | editor | admin |
|---|---:|---:|---:|
| Public laws/news/agencies/stats | Yes | Yes | Yes |
| Profile and email management | Own | Own | Own |
| Compliance reports | Own | Own | Any through admin API |
| Content backend list/detail | No | Yes | Yes |
| Create content | No | Draft | Published directly |
| Edit a main-table draft | No | Yes, shared | Yes |
| Propose changes to published content | No | Yes, shared Draft | Yes |
| Approve/batch approve | No | No | Yes |
| Suspend published content | No | No | Yes |
| Discard pending Draft | No | No | Yes |
| Reference-data list/detail | No | Yes | Yes |
| Reference-data create/update | No | Yes | Yes |
| Reference-data delete | No | No | Yes |
| User administration | No | No | Yes |
| All-report administration | No | No | Yes |

Reference data means exactly these resources:

- `countries`
- `compliance-scenes`
- `news-tags`
- `agency-categories`
- `agency-scenes`

### 3.2 JWT decorator behavior

Extend the authentication decorator to accept either one role or a collection of roles. The intended usage is equivalent to:

```python
@jwt_required(roles=('admin', 'editor'))
@jwt_required(role='admin')
```

Requirements:

- Missing/invalid/expired access token: 401 `AUTH_ERROR`.
- Valid user with a disallowed database role: 403 `AUTH_ERROR`.
- Convert the JWT `sub` to an integer inside the invalid-token boundary. Missing, non-string, non-numeric, zero, or otherwise invalid subjects return 401 rather than 500.
- Continue loading the User row on every request. Do not trust the role embedded in the JWT as the authorization source.
- Apply `admin/editor` authorization to every `/api/admin/*` route before service code executes, except routes already stricter at admin-only.

## 4. News and Agency review model

### 4.1 State invariants

The same invariants apply to News and Agency.

- An editor-created, never-published item is a main-table row with `status='draft'` and no separate Draft row.
- A published main row always remains `status='published'` while proposed changes are pending.
- Proposed changes to a published row live only in the corresponding Draft table.
- A Draft row must not affect public APIs before approval.
- Editors share Draft rows: any editor can update the pending snapshot.
- Only admin can approve, batch approve, suspend, or discard a Draft.
- Admin direct update of a published item applies immediately unless a pending Draft exists; in that case return 409 and require approval/discard first, matching the Law behavior.

### 4.2 NewsDraft payload

`NewsDraft.data` is a complete prospective snapshot. It must contain:

- all editable News business columns;
- `content`, containing the prospective `news_text.content` value or `null`;
- `tag_ids`, containing the complete prospective list of tag IDs.

Do not write `content` or tag relations to their live tables when an editor modifies published news.

Approval must perform all of the following in one database transaction:

1. validate the draft fields and tag IDs;
2. copy News fields to the main row;
3. upsert or delete `news_text` according to the draft snapshot;
4. replace all NewsTagRelation rows;
5. delete NewsDraft;
6. set/retain the main row as `published`;
7. commit once.

Any error rolls back every step. Admin direct create/update must also commit News, content, and tag relations as one transaction.

### 4.3 Public isolation

- Public news list and detail must require `News.status == 'published'`.
- Public Agency and Law behavior remains published-only.
- Public serializers must never merge Draft data.

### 4.4 Admin response fields

News and Agency list/detail items must include:

```json
{
  "status": "published",
  "has_draft": true,
  "review_status": "pending"
}
```

Rules:

- `review_status='pending'` when the main row is draft or a separate Draft exists.
- `review_status='none'` only when the main row is published and no Draft exists.
- Detail responses merge pending fields for editor/admin preview while preserving the live `status` value.
- News detail preview merges draft `content` and `tag_ids`; it should also expose the normal `tags` objects resolved from those IDs for existing UI compatibility.

Admin list endpoints accept `review_status=pending|none`. Invalid values return 400. Batch approval operates on pending items, including published rows with a Draft.

### 4.5 API additions

Add admin-only Draft discard operations:

```http
DELETE /api/admin/news/{id}/draft
DELETE /api/admin/agencies/{id}/draft
Authorization: Bearer <admin-token>
```

Success, 200:

```json
{
  "success": true,
  "data": {"item": {"id": 1, "status": "published", "has_draft": false, "review_status": "none"}},
  "message": "草稿已丢弃"
}
```

Errors:

- 401 missing/invalid token;
- 403 editor/user;
- 404 item not found;
- 400 `VALIDATION_ERROR` if the main item exists but no separate Draft exists.

Discarding a main-table, never-published draft is not supported by this endpoint; use the existing item DELETE operation.

## 5. Email verification flow

Email verification continues using signed, expiring JWTs. Do not add a verification-token table.

### 5.1 Registration

`POST /api/auth/register`

Request:

```json
{
  "username": "example_user",
  "password": "example123",
  "email": "user@example.com"
}
```

- Email is mandatory and validated before inserting the user.
- Commit the user before sending email so SMTP failure never creates a registration retry conflict.
- Send the verification email synchronously after commit.
- Registration remains successful if SMTP fails. Never roll back the user for email delivery failure.

Success with email sent, 201:

```json
{
  "success": true,
  "data": {
    "user": {},
    "access_token": "...",
    "verification_email_sent": true
  },
  "message": "注册成功，请验证邮箱"
}
```

Success with email delivery failure, 201:

```json
{
  "success": true,
  "data": {
    "user": {},
    "access_token": "...",
    "verification_email_sent": false
  },
  "message": "账号已创建，但验证邮件发送失败，请登录后重试"
}
```

Log the underlying SMTP exception server-side, but never include hostnames, credentials, exception strings, or provider details in the API response.

### 5.2 Bind or replace email

`PUT /api/user/email`, access JWT required.

Request:

```json
{"email": "new@example.com", "password": "current-password"}
```

Behavior:

- verify the current password;
- validate and normalize the email consistently with registration;
- reject an email owned by another user with 409;
- if it equals the current verified email, return 409 with an explanatory message;
- update the email and set `email_verified=false`, then commit;
- synchronously send a verification email;
- preserve the email change if delivery fails and return 200 with `verification_email_sent=false` so the user can use resend.

Response data contains the updated serialized `user` and `verification_email_sent`.

### 5.3 Resend verification

`POST /api/user/email/resend-verification`, access JWT required, no body.

- No email: 400 `VALIDATION_ERROR`.
- Already verified: 409 `CONFLICT`.
- Delivery success: 200.
- SMTP failure: 502 `EMAIL_SEND_FAILED` with a safe message.
- Limit the combined verification-email sending scope to five requests per hour per user. Registration has its separate IP limit.

### 5.4 Verify email

Keep `POST /api/auth/verify-email` with `{ "token": "..." }`.

- Continue checking token type, expiry, user ID, and token email against the current User email.
- Changing the account email automatically invalidates older tokens because their email no longer matches.
- Re-verifying an already verified current email is idempotent and returns 200.

### 5.5 Report gate

Before file processing, OSS access, idempotency reservation, or Bailian access, report creation must require a current email with `email_verified=true`.

Failure, 403:

```json
{
  "success": false,
  "error": {
    "code": "EMAIL_VERIFICATION_REQUIRED",
    "message": "请先验证邮箱后再创建合规报告"
  }
}
```

## 6. Rate limiting

Use `Flask-Limiter==4.1.1` with the configured Redis URL. TestingConfig may use memory storage; production must not silently fall back to per-process memory.

| Scope | Limit key | Limit | Admin exemption |
|---|---|---:|---:|
| Register | remote IP | 5/hour | No |
| Login | none | unlimited | N/A |
| Bind/change/resend verification email | authenticated user ID | shared 5/hour | No |
| Create report | authenticated user ID | 5/minute | Yes |

Do not add daily report limits, active-task limits, or invitation checks.

All breaches return 429 in the standard envelope:

```json
{
  "success": false,
  "error": {"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后重试"}
}
```

## 7. Report creation idempotency

### 7.1 Problem being solved

An HTTP response may time out after OSS upload and Bailian task creation. The browser then cannot know whether the request succeeded. Retrying without an idempotency key creates another paid Bailian task and duplicate report. UI button disabling alone cannot handle response loss, refresh, proxy retry, or concurrent duplicate requests.

### 7.2 Request contract

`POST /api/compliance-reports` requires:

```http
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
```

- Accept a canonical UUID string and store at most 64 characters.
- Missing or invalid key: 400 `VALIDATION_ERROR`.
- A new intentional generation, including “regenerate,” must use a new UUID.

### 7.3 Fingerprint

Calculate SHA-256 over a canonical representation containing:

1. trimmed values of all required text fields in a fixed field-name order;
2. for each attachment in submitted order: original filename, byte size, and content SHA-256.

Do not include signed URLs, generated secure names, timestamps, or multipart boundaries. The same logical payload must produce the same fingerprint across retries.

### 7.4 Reservation and duplicate behavior

After validating config, user verification, form fields, files, and fingerprint—but before OSS upload or Bailian access—insert and commit a DiagnosisRecord with:

- `status='submitting'`;
- `idempotency_key`;
- `request_fingerprint`;
- request metadata sufficient for normal serialization;
- `task_id=NULL`.

The database unique constraint on `(user_id, idempotency_key)` arbitrates races.

On duplicate:

- Same fingerprint: clean current local temp files, do no external work, and return the existing report.
- Different fingerprint: clean current temp files and return 409 `IDEMPOTENCY_CONFLICT`.
- Existing failed/cancelled record: return it; never retry external work with the same key.

HTTP status for an idempotent replay:

- `submitting`, `queued`, `in_progress`: 202;
- `completed`, `failed`, `cancelled`: 200.

### 7.5 Completion and failure

- After Bailian accepts the task, set `task_id` and the returned active/terminal status, then commit.
- Any failure after reservation marks the record `failed`; it does not delete the idempotency reservation.
- Track successfully uploaded object names in request scope. On later failure, attempt to delete all of them; log deletion failures and rely on the one-day OSS lifecycle as the final fallback.
- Always remove local temp files.
- Do not add an attachment model or persist attachment lifecycle state.
- Extend the existing polling task to include `submitting`: records with no task ID older than 300 seconds become failed; younger records are skipped.

## 8. Production configuration and startup

### 8.1 Validation

Development/testing defaults may remain convenient, but production must fail before serving requests when configuration is unsafe.

Production requirements:

- `SECRET_KEY` and `JWT_SECRET_KEY` are at least 32 characters and are not known example/default values.
- DB host, port, name, user, and password are present. `DB_USER=root` is allowed.
- Redis URL is present.
- SMTP server, port, username, password, and sender are present.
- OSS credentials, region, endpoint, report bucket, and Law bucket are present.
- Bailian API key, app ID, AI version, and data cutoff date are present.
- Frontend URL exists and uses HTTPS.
- Unknown `FLASK_ENV` raises a startup configuration error; it must not fall back to DevelopmentConfig.
- Production rejects `CELERY_AUTO_START=true` because automatic child processes are a development feature.

### 8.2 Database URL and pool

- Construct the MySQL URI with SQLAlchemy `URL.create()`, not string interpolation.
- Specify `mysql+pymysql` and `charset=utf8mb4`.
- Configure `pool_pre_ping=True`, `pool_recycle=1800`, and `pool_timeout=10` for MySQL.
- TestingConfig continues using SQLite and must not receive incompatible MySQL pool options.

### 8.3 Remove automatic DDL

- `create_app()` must never call `db.create_all()` or create/replace `platform_stats`.
- Remove the `initialize_database` parameter rather than leaving an accidental production switch.
- Update run, Celery, tests, and bits utilities for the new factory signature.
- Tests explicitly create/drop their SQLite schema in fixtures.
- Seed/migration utilities assume the target schema was prepared separately.

This work does not add a WSGI server, reverse proxy configuration, health endpoints, request IDs, structured logs, audit tables, or Alembic/Flask-Migrate.

## 9. Database migration design

The future implementation must add these tracked artifacts:

- `sql/migrations/003_mvp_production_fixes.sql`
- `bits/migrate-mvp-production-fixes.py`

Update `.gitignore` so database dumps remain ignored while `sql/migrations/*.sql` is tracked.

### 9.1 Required schema changes

```sql
ALTER TABLE diagnosis_records
  ADD COLUMN idempotency_key VARCHAR(64) NULL,
  ADD COLUMN request_fingerprint CHAR(64) NULL,
  ADD UNIQUE KEY uq_diagnosis_user_idempotency (user_id, idempotency_key),
  ADD KEY idx_diagnosis_user_deleted_created (user_id, deleted, created_at);

CREATE INDEX idx_laws_status_created ON laws (status, created_at);
CREATE INDEX idx_news_status_date ON news (status, date);
CREATE INDEX idx_agencies_status_sort ON agencies (status, sort_order);
```

Replace the foreign key from `news_tag_relations.news_id` to `news.id` with the same column relationship plus `ON DELETE CASCADE`. The Python script must discover the actual constraint name from `information_schema`; it must not assume an auto-generated name.

No user, Draft-ownership, attachment, verification-token, quota, or audit columns are added.

### 9.2 Python migration commands

The script exposes exactly:

```text
python bits/migrate-mvp-production-fixes.py preflight
python bits/migrate-mvp-production-fixes.py apply
python bits/migrate-mvp-production-fixes.py verify
```

- `preflight`: read-only; connect using existing DB environment variables, inspect columns/indexes/FKs/MySQL version, and report schema drift. Exit 0 when safe to apply, 1 for detected incompatibility, 2 for config/connection failure.
- `apply`: inspect before every step and apply only missing changes. MySQL DDL is not globally transactional, so print and record each completed step. Abort on unexpected definitions rather than replacing them silently.
- `verify`: assert exact column types/nullability, unique/index column order, and cascade FK behavior. Exit 0 only when the complete target schema exists.

The SQL file is the transparent one-shot equivalent for manual execution. It must include preflight queries, a backup/stop-write warning, explicit statements, and a note that it is not rerunnable. The Python script is the idempotent path.

## 10. Data access and validation

- Normalize every paginated route to `page >= 1` and `1 <= per_page <= 100`, including public content, admin content, users, and reports.
- Reject invalid status/review-status/date filters with 400 rather than silently returning surprising data.
- In public news queries, count first, load only the requested page, then batch-load tag relations for current-page IDs. Metadata tag options may come from the small NewsTag reference table directly; never enumerate all matching News IDs.
- Replace generic unrestricted `model(**data)` and arbitrary `hasattr` updates with resource-specific allowed-field sets and validation.
- Convert user-caused `IntegrityError` cases to stable 400/409 AppErrors and roll back the session.
- Validate reference foreign keys before content commits where a clear 400 is possible.
- Preserve the existing maximum of five compliance files and 20 MiB each.
- Add lightweight standard-library signature checks: PDF header, OLE DOC header, ZIP/DOCX contents, and binary-content rejection for TXT/HTML. Extension and signature must agree.
- Do not persist file hashes or attachment rows beyond the report request fingerprint.

## 11. Unified backend API test plan

Add development-only pytest dependencies in `requirements-dev.txt`. The single supported command is:

```bash
python -m pytest tests -v
```

Tests must never connect to real Redis, SMTP, OSS, Bailian, or production MySQL. Mock external clients and use resettable memory rate-limit storage under TestingConfig.

### 11.1 Required scenarios

Authorization:

- missing/expired/invalid/malformed-sub JWT;
- complete user/editor/admin matrix across every admin route;
- editor reference create/update allowed and delete denied;
- editor approval/suspend/discard/user/report administration denied;
- current database role overrides JWT role claim.

Draft workflow:

- editor creates News/Agency main draft;
- multiple editors update the same main draft and same published-item Draft;
- published public representation remains unchanged while Draft exists;
- public news detail returns 404 for draft ID;
- News Draft preview includes prospective content/tags;
- approval atomically publishes metadata/content/tags;
- forced commit failure rolls everything back;
- discard preserves published content;
- batch approval includes published rows with Draft;
- admin direct edit conflicts with pending Draft.

Email:

- registration requires email;
- successful email delivery;
- SMTP failure returns 201, preserves account/token, and reports `verification_email_sent=false`;
- bind/change requires current password and uniqueness;
- email change invalidates old token;
- resend success/failure/already-verified/no-email behavior;
- verification-email shared limit;
- unverified report request is rejected before local/OSS/Bailian work.

Rate limits:

- sixth registration request in an hour returns 429;
- login remains unlimited;
- sixth report request in a minute returns 429 for user/editor;
- admin report requests are exempt;
- error envelope is stable.

Idempotency:

- missing/invalid key;
- first submission reserves before external calls;
- sequential same-payload replay makes only one OSS/Bailian call;
- database unique race resolves to one record/task;
- same key with different field or file returns conflict;
- failed key returns original failure without retry;
- new key creates a new report;
- replay HTTP status follows report state;
- stale submitting transitions to failed;
- uploaded objects are best-effort deleted on later failure.

Data behavior:

- report ownership and soft-delete isolation;
- all pagination minimum/maximum boundaries;
- News query does not fetch all matching IDs;
- News deletion cascades tag relations;
- invalid payload and FK/unique errors use standard responses;
- file signature mismatch is rejected and temp files are removed;
- existing Law OSS suite remains green.

## 12. Implementation sequence and completion gates

Implement in this order so each stage has a stable dependency boundary.

1. **Models and migration artifacts**: model fields/indexes match the documented SQL; preflight/apply/verify are implemented; no migration is automatically executed.
2. **Factory/config cleanup**: strict production validation, safe URL/pool options, and removal of startup DDL are tested.
3. **RBAC**: every admin endpoint has an explicit role requirement and the authorization matrix passes.
4. **News/Agency Draft workflow**: public isolation, review fields/filters, approval, and discard pass transactional tests.
5. **Email flow**: registration, email change, resend, and report gate pass with SMTP mocked.
6. **Rate limiting**: agreed limits and exemptions pass deterministic tests.
7. **Report idempotency/OSS compensation**: uniqueness, replay semantics, status transitions, and cleanup pass.
8. **Pagination/data validation**: bounded queries, cascade, whitelist, and upload signature checks pass.
9. **Documentation sync**: update README, `docs/api.md`, `docs/db.md`, and `.env.example` to match implemented behavior and migration order.

Final acceptance requires:

- migration `preflight`, `apply`, and `verify` succeed against a representative MySQL schema;
- `python -m pytest tests -v` passes in full;
- ordinary users cannot reach any admin endpoint;
- a News/Agency proposed edit is not public until approval;
- unverified accounts cannot create reports;
- a repeated Idempotency-Key never creates a second Bailian task;
- no API/worker/beat/script startup performs schema DDL;
- implementation and public documentation expose the same request, response, status, and error contracts.
