#!/usr/bin/env python3
"""Idempotent, resumable migration of law files from local disk to OSS.

Commands:
  preflight          Dry-run: validate every law, write manifest.
  apply              Upload to OSS and update DB (use --batch-size).
  verify             HEAD-check OSS objects against manifest + DB.
  cleanup-local      Delete successfully migrated local source files.

Flow:
  1. Stop backend, backup database and uploads/laws/.
  2. Run bits/check-dangling.py (legacy mode) — fix missing files first.
  3. Execute sql/migrations/001_expand.sql.
  4. Run `preflight` — fix issues, repeat until clean.
  5. Run `apply --batch-size 50`.
  6. Run `verify`.
  7. Execute sql/migrations/002_contract.sql; deploy new code.
  8. Run `cleanup-local` (optional).

The manifest is written to <UPLOAD_PATH>/migration-manifest.jsonl.
Each line is a JSON record tracking a single law's status.
"""

import argparse
import json
import os
import shutil
import sys
import uuid

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.draft import LawDraft
from app.models.law import Law
from app.services.law_service import _build_object_name
from app.utils.oss_utils import (
    head_object,
    object_exists,
    upload_file,
)

app = create_app()

BUCKET = 'LAW_OSS_BUCKET_NAME'


def _upload_dir():
    return os.path.join(app.config['UPLOAD_PATH'], 'laws')


def _tmp_dir():
    path = os.path.join(app.config['UPLOAD_PATH'], 'tmp', 'laws')
    os.makedirs(path, exist_ok=True)
    return path


def _manifest_path():
    return os.path.join(app.config['UPLOAD_PATH'], 'migration-manifest.jsonl')


def _load_manifest():
    """Load existing manifest as a dict keyed by law_id."""
    m = {}
    mp = _manifest_path()
    if not os.path.isfile(mp):
        return m
    with open(mp, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                m[rec['law_id']] = rec
            except json.JSONDecodeError:
                pass
    return m


def _write_manifest(rec):
    with open(_manifest_path(), 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')


def _update_manifest(rec):
    """Rewrite the manifest with the updated record for rec['law_id']."""
    mp = _manifest_path()
    if not os.path.isfile(mp):
        return
    lines = []
    with open(mp, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if r.get('law_id') == rec['law_id']:
                lines.append(json.dumps(rec, ensure_ascii=False))
            else:
                lines.append(json.dumps(r, ensure_ascii=False))
    tmp_path = mp + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    os.replace(tmp_path, mp)


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

def cmd_preflight():
    """Scan all Law/LawDraft records and write a manifest."""
    print('🔍 Preflight: scanning laws...')

    if os.path.isfile(_manifest_path()):
        print('❌ Manifest already exists; remove or archive it before a fresh preflight.')
        return False

    laws = Law.query.order_by(Law.id).all()

    # Load old filename values via raw SQL (model no longer has the column).
    filename_map = {}
    try:
        rows = db.session.execute(text('SELECT id, filename FROM laws')).fetchall()
        filename_map = {r[0]: r[1] for r in rows}
    except Exception:
        pass  # filename column might already be dropped

    records = []
    target_owners = {}

    for law in laws:
        # pending_file_name is the renamed secure_name column.
        secure = law.pending_file_name
        filename = filename_map.get(law.id)

        draft = LawDraft.query.filter_by(law_id=law.id).first()

        # Determine source file path
        src_path = None
        if secure:
            p = os.path.join(_upload_dir(), secure)
            if os.path.isfile(p):
                src_path = p

        ext = ''
        if secure:
            ext = os.path.splitext(secure)[1].lower()
        elif filename:
            ext = os.path.splitext(filename)[1].lower()

        # Compute the current main version's target object name.  Proposed draft
        # titles must not rename the live object before approval.
        target_key = None
        build_error = None
        if filename or secure:
            cn = law.title_cn or ''
            en = law.title_en or ''
            if cn and ext:
                try:
                    target_key = _build_object_name(cn, en, ext)
                except Exception as e:
                    build_error = getattr(e, 'message', str(e))
            elif not cn:
                build_error = 'title_cn is empty'
            elif not ext:
                build_error = 'no extension'
            if filename and not secure and not build_error:
                build_error = 'filename exists but secure_name is missing'

        draft_secure = None
        draft_local_path = None
        if draft and isinstance(draft.data, dict):
            draft_secure = draft.data.get('secure_name')
            if draft_secure and draft_secure != secure:
                candidate = os.path.join(_upload_dir(), draft_secure)
                if os.path.isfile(candidate):
                    draft_local_path = candidate
                elif not build_error:
                    build_error = 'draft local file missing'

        if target_key:
            target_owners.setdefault(target_key, []).append(law.id)

        rec = {
            'law_id': law.id,
            'status': law.status,
            'title_cn': law.title_cn,
            'title_en': law.title_en,
            'has_draft': draft is not None,
            'old_secure_name': secure,
            'old_filename': filename,
            'local_path': src_path,
            'draft_local_path': draft_local_path,
            'old_draft_secure_name': draft_secure,
            'file_size': os.path.getsize(src_path) if src_path else None,
            'target_key': target_key,
            'phase': 'preflight',
            'error': build_error,
            'oss_uploaded': False,
            'db_applied': False,
            'verified': False,
        }

        if build_error or (secure and not src_path):
            rec['error'] = build_error or 'local file missing'
        records.append(rec)

    # Reject duplicate generated keys before touching OSS or the database.
    for rec in records:
        key = rec.get('target_key')
        owners = target_owners.get(key, []) if key else []
        if len(owners) > 1:
            rec['error'] = f'duplicate target key used by laws {owners}'

    # An object that pre-dates this fresh manifest is a collision, not a
    # resumable upload owned by the migration.
    for rec in records:
        if rec.get('error') or not rec.get('target_key'):
            continue
        try:
            if object_exists(rec['target_key'], bucket_name=BUCKET):
                rec['error'] = 'target object already exists in OSS'
        except Exception as exc:
            rec['error'] = (
                'OSS preflight failed: '
                f'{getattr(exc, "message", str(exc))}'
            )

    issues = 0
    for rec in records:
        if rec.get('error'):
            issues += 1
            print(f'  ❌ law:{rec["law_id"]} {rec["title_cn"]} — {rec["error"]}')
        _write_manifest(rec)

    print(f'\nPreflight done: {len(records)} laws, {issues} issues')
    if issues:
        print('⚠️  Fix issues before running apply.')
    return issues == 0


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def cmd_apply(batch_size=50):
    """Upload files to OSS and update DB, resuming from manifest."""
    manifest = _load_manifest()
    if not manifest:
        print('❌ No manifest found. Run preflight first.')
        return False

    validation_errors = [
        rec for rec in manifest.values()
        if rec.get('phase') == 'preflight' and rec.get('error')
    ]
    if validation_errors:
        print('❌ Manifest contains preflight errors; apply has been aborted.')
        return False

    pending = [
        (lid, rec) for lid, rec in manifest.items()
        if (
            (rec.get('phase') == 'preflight' and not rec.get('error'))
            or rec.get('phase') == 'apply_failed'
        )
    ]

    if not pending:
        print('✅ All records already applied.')
        return True

    print(f'📦 Applying {len(pending)} records (batch size {batch_size})...')

    failed = False
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        print(f'  Batch {i // batch_size + 1}: laws {batch[0][0]}–{batch[-1][0]}')
        db.session.expire_all()

        for lid, rec in batch:
            rec['error'] = None
            try:
                law = Law.query.get(lid)
                if not law:
                    failed = True
                    rec['error'] = 'law deleted'
                    rec['phase'] = 'apply_failed'
                    _update_manifest(rec)
                    continue

                draft = LawDraft.query.filter_by(law_id=lid).first()

                def ensure_uploaded():
                    if not rec.get('local_path') or not rec.get('target_key'):
                        return
                    if rec.get('oss_uploaded'):
                        metadata = head_object(rec['target_key'], bucket_name=BUCKET)
                        if metadata.get('content_length') != rec.get('file_size'):
                            raise RuntimeError('resumable OSS object size mismatch')
                        return
                    if object_exists(rec['target_key'], bucket_name=BUCKET):
                        raise RuntimeError('target object exists but is not owned by this manifest')
                    upload_file(rec['local_path'], rec['target_key'], bucket_name=BUCKET)
                    rec['oss_uploaded'] = True
                    _update_manifest(rec)
                    print(f'    ⬆️  Uploaded {rec["target_key"]}')

                if law.status == 'published' and not draft:
                    # Published, no draft: upload to OSS directly.
                    if rec['local_path'] and rec['target_key']:
                        ensure_uploaded()
                        law.object_name = rec['target_key']
                        law.pending_file_name = None
                    else:
                        law.pending_file_name = None

                elif law.status == 'draft' and draft:
                    # "Published but pending review" in old impl.
                    # Upload main version, restore published.
                    if rec['local_path'] and rec['target_key']:
                        ensure_uploaded()
                        law.object_name = rec['target_key']

                    # Handle draft's separate file
                    draft_secure = rec.get('old_draft_secure_name')
                    if draft_secure and draft_secure != rec.get('old_secure_name'):
                        src = rec.get('draft_local_path')
                        if not src or not os.path.isfile(src):
                            raise RuntimeError('draft local file missing')
                        ext = os.path.splitext(draft_secure)[1].lower()
                        pending_name = rec.get('new_draft_pending_name')
                        if not pending_name:
                            pending_name = str(uuid.uuid4()) + ext
                            rec['new_draft_pending_name'] = pending_name
                            _update_manifest(rec)
                        dst = os.path.join(_tmp_dir(), pending_name)
                        if not os.path.isfile(dst):
                            shutil.copy2(src, dst)
                        draft.pending_file_name = pending_name
                        print(f'    📁 Staged draft file → tmp/laws/{pending_name}')

                    # Clean draft data
                    if isinstance(draft.data, dict):
                        draft_data = dict(draft.data)
                        for k in ('filename', 'secure_name', 'object_name'):
                            draft_data.pop(k, None)
                        draft.data = draft_data

                    law.status = 'published'
                    law.pending_file_name = None

                elif law.status == 'draft' and not draft:
                    # Draft: don't upload; copy to tmp and retain the source
                    # until the explicit verified cleanup step.
                    if rec['local_path'] and rec.get('old_secure_name'):
                        ext = os.path.splitext(rec['old_secure_name'])[1].lower()
                        pending_name = rec.get('new_pending_name')
                        if not pending_name:
                            pending_name = str(uuid.uuid4()) + ext
                            rec['new_pending_name'] = pending_name
                            _update_manifest(rec)
                        dst = os.path.join(_tmp_dir(), pending_name)
                        if not os.path.isfile(dst):
                            shutil.copy2(rec['local_path'], dst)
                        law.pending_file_name = pending_name
                        law.object_name = None
                        print(f'    📁 Staged draft file → tmp/laws/{pending_name}')
                    else:
                        law.pending_file_name = None
                        law.object_name = None

            except Exception as exc:
                db.session.rollback()
                failed = True
                rec['phase'] = 'apply_failed'
                rec['error'] = getattr(exc, 'message', str(exc))
                print(f'    ❌ law:{lid} — {rec["error"]}')
            else:
                try:
                    db.session.commit()
                    rec['phase'] = 'applied'
                    rec['db_applied'] = True
                    rec['error'] = None
                except Exception as exc:
                    db.session.rollback()
                    failed = True
                    rec['phase'] = 'apply_failed'
                    rec['error'] = f'db commit: {exc}'
                    print(f'    ❌ law:{lid} — DB commit failed: {exc}')

            _update_manifest(rec)

    print('\nApply complete.')
    return not failed


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def cmd_verify():
    """Verify OSS/DB state and staged draft files for every applied record."""
    manifest = _load_manifest()
    applied = [
        (lid, rec) for lid, rec in manifest.items()
        if rec.get('phase') in ('applied', 'verified')
    ]

    if not applied:
        print('✅ No records to verify.')
        return

    ok = 0
    fail = 0

    for lid, rec in applied:
        law = Law.query.get(lid)
        try:
            if not law:
                raise RuntimeError('law missing from database')

            target_key = rec.get('target_key')
            if rec.get('oss_uploaded'):
                obj = head_object(target_key, bucket_name=BUCKET)
                expected_size = rec.get('file_size')
                actual_size = obj.get('content_length')
                if expected_size is not None and actual_size != expected_size:
                    raise RuntimeError(
                        f'OSS size mismatch: local={expected_size} OSS={actual_size}'
                    )
                if law.object_name != target_key:
                    raise RuntimeError(
                        f'DB object_name mismatch: DB={law.object_name} manifest={target_key}'
                    )

            if rec.get('new_pending_name'):
                pending_path = os.path.join(_tmp_dir(), rec['new_pending_name'])
                if law.pending_file_name != rec['new_pending_name']:
                    raise RuntimeError('main draft pending_file_name mismatch')
                if not os.path.isfile(pending_path):
                    raise RuntimeError('main draft staged file missing')

            if rec.get('new_draft_pending_name'):
                draft = LawDraft.query.filter_by(law_id=lid).first()
                pending_path = os.path.join(
                    _tmp_dir(), rec['new_draft_pending_name'],
                )
                if not draft or draft.pending_file_name != rec['new_draft_pending_name']:
                    raise RuntimeError('LawDraft pending_file_name mismatch')
                if not os.path.isfile(pending_path):
                    raise RuntimeError('LawDraft staged file missing')

            rec['verified'] = True
            rec['phase'] = 'verified'
            rec['error'] = None
            _update_manifest(rec)
            ok += 1
        except Exception as exc:
            print(f'  ❌ law:{lid} — {exc}')
            rec['verified'] = False
            rec['error'] = f'verify: {exc}'
            _update_manifest(rec)
            fail += 1

    print(f'\nVerify: {ok} OK, {fail} failed')
    return fail == 0


# ---------------------------------------------------------------------------
# Cleanup local
# ---------------------------------------------------------------------------

def cmd_cleanup_local():
    """Delete local source files for successfully applied+verified records."""
    manifest = _load_manifest()
    to_clean = [
        (lid, rec) for lid, rec in manifest.items()
        if rec.get('phase') == 'verified' and rec.get('verified')
        and not rec.get('error')
        and rec.get('local_path') and os.path.isfile(rec['local_path'])
    ]

    if not to_clean:
        print('✅ Nothing to clean up.')
        return

    print(f'🗑️  Deleting {len(to_clean)} local source files...')

    for lid, rec in to_clean:
        paths = [rec['local_path']]
        if rec.get('draft_local_path'):
            paths.append(rec['draft_local_path'])
        for path in dict.fromkeys(paths):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    print(f'  ✓ Deleted {path}')
            except OSError as exc:
                print(f'  ❌ law:{lid} — {exc}')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Law OSS migration tool')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('preflight', help='Dry-run validation and manifest generation')

    ap = sub.add_parser('apply', help='Upload to OSS and update DB')
    ap.add_argument('--batch-size', type=int, default=50, help='Batch size (default 50)')

    sub.add_parser('verify', help='HEAD-check OSS objects')

    sub.add_parser('cleanup-local', help='Delete successfully migrated local files')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    with app.app_context():
        if args.command == 'preflight':
            ok = cmd_preflight()
            sys.exit(0 if ok else 1)
        elif args.command == 'apply':
            ok = cmd_apply(batch_size=args.batch_size)
            sys.exit(0 if ok else 1)
        elif args.command == 'verify':
            ok = cmd_verify()
            sys.exit(0 if ok else 1)
        elif args.command == 'cleanup-local':
            cmd_cleanup_local()


if __name__ == '__main__':
    main()
