#!/usr/bin/env python3
"""Check for dangling/unreferenced law files (bidirectional orphan check).

Legacy mode (laws.secure_name, laws_drafts.data.secure_name) vs.
New-schema mode (laws.pending_file_name, laws_drafts.pending_file_name).

Auto-detects the current schema by inspecting the laws table columns.

Exit codes:
  0 — clean (no dangling or missing files)
  1 — differences found
  2 — configuration or database error

This script is READ-ONLY.  It never deletes files.
"""

import argparse
import json
import os
import sys

from sqlalchemy import inspect, text

# ---------------------------------------------------------------------------
# Bootstrap Flask app
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.draft import LawDraft
from app.models.law import Law

app = create_app(initialize_database=False)


def _resolve_upload_path(subdir=''):
    path = os.path.join(app.config['UPLOAD_PATH'], subdir)
    return os.path.normpath(path)


def _regular_files(path):
    if not os.path.isdir(path):
        return set()
    return {
        name for name in os.listdir(path)
        if os.path.isfile(os.path.join(path, name))
    }


def _human_output(ok, detail):
    if ok:
        print('✅ 无悬垂/丢失文件')
        return
    for section, entries in detail.items():
        if not entries:
            continue
        print(f'\n--- {section} ({len(entries)}) ---')
        for e in sorted(entries):
            print(f'  {e}')


def _json_output(ok, detail):
    print(json.dumps({'clean': ok, **detail}, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Schema detection
# ---------------------------------------------------------------------------

def _detect_mode():
    """Return 'new' if the laws table has a pending_file_name column, else 'legacy'."""
    cols = {c['name'] for c in inspect(db.engine).get_columns('laws')}
    if 'pending_file_name' in cols:
        return 'new'
    return 'legacy'


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def _check_legacy():
    """Check legacy schema: secure_name vs uploads/laws/."""
    upload_dir = _resolve_upload_path('laws')
    disk_files = _regular_files(upload_dir)

    # Database references: laws.secure_name
    db_refs = {}
    rows = db.session.execute(text(
        'SELECT id, secure_name FROM laws WHERE secure_name IS NOT NULL'
    )).fetchall()
    for row in rows:
        db_refs[row[1]] = db_refs.get(row[1], []) + [f'law:{row[0]}']

    # Draft data references: laws_drafts.data.secure_name
    drafts = db.session.execute(text(
        'SELECT id, law_id, data FROM laws_drafts'
    )).fetchall()
    for draft_id, law_id, data in drafts:
        if not data:
            continue
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}
        sn = data.get('secure_name') if isinstance(data, dict) else None
        if sn:
            db_refs[sn] = db_refs.get(sn, []) + [f'draft:{draft_id}(law:{law_id})']

    db_files = set(db_refs.keys())

    missing_local = db_files - disk_files
    unreferenced_local = disk_files - db_files

    # Duplicate / unsafe references
    duplicates = {k: v for k, v in db_refs.items() if len(v) > 1}
    unsafe = {k: v for k, v in db_refs.items()
              if os.path.basename(k) != k or '..' in k or '/' in k or '\\' in k}

    ok = not (missing_local or unreferenced_local or duplicates or unsafe)
    detail = {
        'mode': 'legacy',
        'scan_dir': upload_dir,
        'disk_count': len(disk_files),
        'db_count': len(db_files),
        'missing_local': sorted(missing_local),
        'unreferenced_local': sorted(unreferenced_local),
        'duplicate_references': {k: sorted(v) for k, v in sorted(duplicates.items())},
        'unsafe_references': {k: sorted(v) for k, v in sorted(unsafe.items())},
    }
    return ok, detail


def _check_new():
    """Check new schema: pending_file_name vs uploads/tmp/laws/."""
    tmp_dir = _resolve_upload_path('tmp/laws')
    disk_files = _regular_files(tmp_dir)

    # Database references: laws.pending_file_name
    db_refs = {}
    for row in db.session.query(Law.id, Law.pending_file_name).filter(
        Law.pending_file_name.isnot(None)
    ).all():
        db_refs[row.pending_file_name] = (
            db_refs.get(row.pending_file_name, []) + [f'law:{row.id}']
        )

    # Draft pending_file_name
    drafts = LawDraft.query.filter(LawDraft.pending_file_name.isnot(None)).all()
    for d in drafts:
        pn = d.pending_file_name
        db_refs[pn] = db_refs.get(pn, []) + [f'draft:{d.id}(law:{d.law_id})']

    db_files = set(db_refs.keys())

    missing_local = db_files - disk_files
    unreferenced_local = disk_files - db_files

    duplicates = {k: v for k, v in db_refs.items() if len(v) > 1}
    unsafe = {k: v for k, v in db_refs.items()
              if os.path.basename(k) != k or '..' in k or '/' in k or '\\' in k}

    # Also flag any residual files in the old uploads/laws/ directory.
    legacy_dir = _resolve_upload_path('laws')
    legacy_files = sorted(_regular_files(legacy_dir))

    ok = not (missing_local or unreferenced_local or duplicates
              or unsafe or legacy_files)
    detail = {
        'mode': 'new',
        'scan_dir': tmp_dir,
        'disk_count': len(disk_files),
        'db_count': len(db_files),
        'missing_local': sorted(missing_local),
        'unreferenced_local': sorted(unreferenced_local),
        'duplicate_references': {k: sorted(v) for k, v in sorted(duplicates.items())},
        'unsafe_references': {k: sorted(v) for k, v in sorted(unsafe.items())},
        'legacy_local_files': legacy_files,
    }
    return ok, detail


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Bidirectional law file orphan check')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    try:
        with app.app_context():
            mode = _detect_mode()
            if mode == 'new':
                ok, detail = _check_new()
            else:
                ok, detail = _check_legacy()

            if args.json:
                _json_output(ok, detail)
            else:
                _human_output(ok, detail)

            sys.exit(0 if ok else 1)

    except Exception as exc:
        msg = {'error': str(exc)} if args.json else f'FATAL: {exc}'
        print(msg, file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
