#!/usr/bin/env python3
"""Idempotent MVP production schema migration.

Commands:
  preflight  Read-only: report missing changes and incompatible drift.
  apply      Apply missing changes, aborting on incompatible definitions.
  verify     Assert the exact target schema exists.

Exit codes: 0 success, 1 schema drift, 2 configuration/connection failure.
"""

import argparse
import os
import sys

from sqlalchemy import inspect, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db


class SchemaDriftError(RuntimeError):
    """The database contains an object with an incompatible definition."""


def _quote_identifier(value):
    """Quote a discovered MySQL identifier without trusting its contents."""
    return '`' + str(value).replace('`', '``') + '`'


TARGET_COLUMNS = {
    'diagnosis_records': {
        'idempotency_key': {'type': 'VARCHAR', 'nullable': True, 'size': 64},
        'request_fingerprint': {'type': 'CHAR', 'nullable': True, 'size': 64},
    },
}

TARGET_INDEXES = {
    'diagnosis_records': [
        {'name': 'uq_diagnosis_user_idempotency', 'unique': True,
         'columns': ['user_id', 'idempotency_key']},
        {'name': 'idx_diagnosis_user_deleted_created', 'unique': False,
         'columns': ['user_id', 'deleted', 'created_at']},
    ],
    'laws': [
        {'name': 'idx_laws_status_created', 'unique': False,
         'columns': ['status', 'created_at']},
    ],
    'news': [
        {'name': 'idx_news_status_date', 'unique': False,
         'columns': ['status', 'date']},
    ],
    'agencies': [
        {'name': 'idx_agencies_status_sort', 'unique': False,
         'columns': ['status', 'sort_order']},
    ],
}

TARGET_FKS = {
    'news_tag_relations': {
        'news_id': {
            'referred_table': 'news',
            'referred_columns': ['id'],
            'ondelete': 'CASCADE',
            'fallback_name': 'fk_news_tag_relations_news_id',
        },
    },
}


def _inspector():
    return inspect(db.engine)


def _require_tables():
    actual = set(_inspector().get_table_names())
    required = set(TARGET_COLUMNS) | set(TARGET_INDEXES) | set(TARGET_FKS)
    required.update(spec['referred_table']
                    for fks in TARGET_FKS.values() for spec in fks.values())
    missing = sorted(required - actual)
    if missing:
        raise SchemaDriftError(f'required table(s) missing: {", ".join(missing)}')

    new_columns = {
        (table, column)
        for table, columns in TARGET_COLUMNS.items() for column in columns
    }
    required_columns = set()
    for table, indexes in TARGET_INDEXES.items():
        required_columns.update(
            (table, column)
            for index in indexes for column in index['columns']
            if (table, column) not in new_columns
        )
    for table, fks in TARGET_FKS.items():
        for column, target in fks.items():
            required_columns.add((table, column))
            required_columns.update(
                (target['referred_table'], referred)
                for referred in target['referred_columns']
            )
    missing_columns = [
        f'{table}.{column}' for table, column in sorted(required_columns)
        if _column(table, column) is None
    ]
    if missing_columns:
        raise SchemaDriftError(
            f'required base column(s) missing: {", ".join(missing_columns)}'
        )


def _column(table_name, column_name):
    return next((col for col in _inspector().get_columns(table_name)
                 if col['name'] == column_name), None)


def _column_mismatches(actual, target):
    actual_type = type(actual['type']).__name__.upper()
    mismatches = []
    if actual_type != target['type']:
        mismatches.append(f'type={actual_type}, expected {target["type"]}')
    if getattr(actual['type'], 'length', None) != target['size']:
        mismatches.append(
            f'length={getattr(actual["type"], "length", None)}, '
            f'expected {target["size"]}'
        )
    if bool(actual['nullable']) != target['nullable']:
        mismatches.append(
            f'nullable={actual["nullable"]}, expected {target["nullable"]}'
        )
    return mismatches


def _indexes(table_name):
    result = {}
    for idx in _inspector().get_indexes(table_name):
        result[idx['name']] = {
            'name': idx['name'],
            'unique': bool(idx.get('unique', False)),
            'columns': list(idx.get('column_names') or []),
        }
    for uq in _inspector().get_unique_constraints(table_name):
        if uq.get('name'):
            result[uq['name']] = {
                'name': uq['name'],
                'unique': True,
                'columns': list(uq.get('column_names') or []),
            }
    return result


def _index_mismatches(actual, target):
    mismatches = []
    if actual['unique'] != target['unique']:
        mismatches.append(
            f'unique={actual["unique"]}, expected {target["unique"]}'
        )
    if actual['columns'] != target['columns']:
        mismatches.append(
            f'columns={actual["columns"]}, expected {target["columns"]}'
        )
    return mismatches


def _foreign_key(table_name, column_name):
    matches = [fk for fk in _inspector().get_foreign_keys(table_name)
               if list(fk.get('constrained_columns') or []) == [column_name]]
    if len(matches) > 1:
        raise SchemaDriftError(
            f'{table_name}.{column_name} has multiple foreign keys'
        )
    return matches[0] if matches else None


def _fk_mismatches(actual, target, include_delete_rule=True):
    mismatches = []
    if actual.get('referred_table') != target['referred_table']:
        mismatches.append(
            f'target={actual.get("referred_table")}, '
            f'expected {target["referred_table"]}'
        )
    if list(actual.get('referred_columns') or []) != target['referred_columns']:
        mismatches.append(
            f'referred columns={actual.get("referred_columns")}, '
            f'expected {target["referred_columns"]}'
        )
    if include_delete_rule:
        ondelete = (actual.get('options') or {}).get('ondelete', '').upper()
        if ondelete != target['ondelete']:
            mismatches.append(
                f'ON DELETE={ondelete or "RESTRICT/default"}, '
                f'expected {target["ondelete"]}'
            )
    return mismatches


def _orphan_count(table, column, target):
    referred = target['referred_columns'][0]
    statement = text(
        f'SELECT COUNT(*) FROM `{table}` AS child '
        f'LEFT JOIN `{target["referred_table"]}` AS parent '
        f'ON child.`{column}` = parent.`{referred}` '
        f'WHERE child.`{column}` IS NOT NULL AND parent.`{referred}` IS NULL'
    )
    return db.session.execute(statement).scalar()


def _print_target_state():
    """Print schema state and return the number of incompatible objects."""
    issues = 0
    for table, columns in TARGET_COLUMNS.items():
        for name, target in columns.items():
            actual = _column(table, name)
            if actual is None:
                print(f'  ⚠️  {table}.{name} MISSING — will be added')
                continue
            mismatches = _column_mismatches(actual, target)
            if mismatches:
                print(f'  ❌ {table}.{name}: {"; ".join(mismatches)}')
                issues += 1
            else:
                print(f'  ✅ {table}.{name}')

    for table, targets in TARGET_INDEXES.items():
        actual_indexes = _indexes(table)
        for target in targets:
            actual = actual_indexes.get(target['name'])
            if actual is None:
                print(f'  ⚠️  {table}.{target["name"]} MISSING — will be added')
                continue
            mismatches = _index_mismatches(actual, target)
            if mismatches:
                print(f'  ❌ {table}.{target["name"]}: {"; ".join(mismatches)}')
                issues += 1
            else:
                print(f'  ✅ {table}.{target["name"]}')

    for table, fks in TARGET_FKS.items():
        for column, target in fks.items():
            actual = _foreign_key(table, column)
            if actual is None:
                orphan_count = _orphan_count(table, column, target)
                if orphan_count:
                    print(f'  ❌ {table}.{column} FK missing with '
                          f'{orphan_count} orphan row(s)')
                    issues += 1
                else:
                    print(f'  ⚠️  {table}.{column} FK MISSING — will be added')
                continue
            relationship_drift = _fk_mismatches(
                actual, target, include_delete_rule=False
            )
            if relationship_drift:
                print(f'  ❌ {table}.{column} FK: {"; ".join(relationship_drift)}')
                issues += 1
            elif _fk_mismatches(actual, target):
                print(f'  ⚠️  {table}.{column} FK lacks ON DELETE CASCADE '
                      '— will be replaced')
            else:
                print(f'  ✅ {table}.{column} FK ON DELETE CASCADE')
    return issues


def cmd_preflight():
    _require_tables()
    issues = _print_target_state()
    version = db.session.execute(text('SELECT VERSION()')).scalar()
    print(f'  ℹ️  MySQL version: {version}')
    if issues:
        print(f'\n❌ {issues} incompatible schema object(s) found.')
        return False
    print('\n✅ Preflight passed — safe to apply.')
    return True


def cmd_apply():
    _require_tables()

    for table, columns in TARGET_COLUMNS.items():
        for name, target in columns.items():
            actual = _column(table, name)
            if actual is not None:
                mismatches = _column_mismatches(actual, target)
                if mismatches:
                    raise SchemaDriftError(
                        f'{table}.{name}: {"; ".join(mismatches)}'
                    )
                print(f'  ⏭️  {table}.{name} already exact')
                continue
            nullable = 'NULL' if target['nullable'] else 'NOT NULL'
            statement = (
                f'ALTER TABLE `{table}` ADD COLUMN `{name}` '
                f'{target["type"]}({target["size"]}) {nullable}'
            )
            db.session.execute(text(statement))
            db.session.commit()
            print(f'  ✅ added {table}.{name}')

    for table, targets in TARGET_INDEXES.items():
        for target in targets:
            actual = _indexes(table).get(target['name'])
            if actual is not None:
                mismatches = _index_mismatches(actual, target)
                if mismatches:
                    raise SchemaDriftError(
                        f'{table}.{target["name"]}: {"; ".join(mismatches)}'
                    )
                print(f'  ⏭️  {table}.{target["name"]} already exact')
                continue
            columns = ', '.join(f'`{name}`' for name in target['columns'])
            unique = 'UNIQUE ' if target['unique'] else ''
            statement = (
                f'CREATE {unique}INDEX `{target["name"]}` '
                f'ON `{table}` ({columns})'
            )
            db.session.execute(text(statement))
            db.session.commit()
            print(f'  ✅ created {table}.{target["name"]}')

    for table, fks in TARGET_FKS.items():
        for column, target in fks.items():
            actual = _foreign_key(table, column)
            if actual is not None:
                relationship_drift = _fk_mismatches(
                    actual, target, include_delete_rule=False
                )
                if relationship_drift:
                    raise SchemaDriftError(
                        f'{table}.{column} FK: {"; ".join(relationship_drift)}'
                    )
                if not _fk_mismatches(actual, target):
                    print(f'  ⏭️  {table}.{column} FK already exact')
                    continue
                fk_name = actual.get('name')
                if not fk_name:
                    raise SchemaDriftError(
                        f'{table}.{column} FK has no discoverable constraint name'
                    )
                db.session.execute(text(
                    f'ALTER TABLE `{table}` DROP FOREIGN KEY '
                    f'{_quote_identifier(fk_name)}'
                ))
                db.session.commit()
            else:
                fk_name = target['fallback_name']
                orphan_count = _orphan_count(table, column, target)
                if orphan_count:
                    raise SchemaDriftError(
                        f'{table}.{column} has {orphan_count} orphan row(s); '
                        'cannot add foreign key safely'
                    )
                existing_names = {
                    fk.get('name') for fk in _inspector().get_foreign_keys(table)
                }
                if fk_name in existing_names:
                    raise SchemaDriftError(
                        f'{table} already has unrelated FK named {fk_name}'
                    )

            referred_columns = ', '.join(
                f'`{name}`' for name in target['referred_columns']
            )
            statement = (
                f'ALTER TABLE `{table}` ADD CONSTRAINT '
                f'{_quote_identifier(fk_name)} '
                f'FOREIGN KEY (`{column}`) '
                f'REFERENCES `{target["referred_table"]}` ({referred_columns}) '
                f'ON DELETE {target["ondelete"]}'
            )
            db.session.execute(text(statement))
            db.session.commit()
            print(f'  ✅ set {table}.{column} FK ON DELETE CASCADE')

    print('\nSchema changes applied; running exact verification.')
    return cmd_verify()


def cmd_verify():
    _require_tables()
    failures = _print_target_state()

    # In verification, a missing target object is a failure (unlike preflight).
    for table, columns in TARGET_COLUMNS.items():
        failures += sum(_column(table, name) is None for name in columns)
    for table, targets in TARGET_INDEXES.items():
        actual = _indexes(table)
        failures += sum(target['name'] not in actual for target in targets)
    for table, fks in TARGET_FKS.items():
        failures += sum(_foreign_key(table, column) is None for column in fks)

    # _print_target_state treats a repairable missing CASCADE as a warning.
    for table, fks in TARGET_FKS.items():
        for column, target in fks.items():
            actual = _foreign_key(table, column)
            if actual is not None and _fk_mismatches(actual, target):
                failures += 1

    if failures:
        print(f'\n❌ {failures} verification failure(s).')
        return False
    print('\n✅ Verify passed — schema matches target.')
    return True


def main():
    parser = argparse.ArgumentParser(description='MVP production schema migration')
    subparsers = parser.add_subparsers(dest='command')
    subparsers.add_parser('preflight', help='Read-only schema inspection')
    subparsers.add_parser('apply', help='Apply missing schema changes')
    subparsers.add_parser('verify', help='Assert exact target schema')
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    try:
        app = create_app()
        with app.app_context():
            command = {
                'preflight': cmd_preflight,
                'apply': cmd_apply,
                'verify': cmd_verify,
            }[args.command]
            return 0 if command() else 1
    except SchemaDriftError as exc:
        print(f'SCHEMA DRIFT: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        print(f'FATAL: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
