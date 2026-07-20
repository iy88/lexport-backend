import os
from datetime import datetime, timedelta

import redis
from flask import current_app
from redis.exceptions import LockError

from app.extensions import db
from app.models.diagnosis import DiagnosisRecord, DiagnosisResult
from app.services.compliance_service import _get_bailian_client
from app.utils.report_utils import InvalidReportError, apply_report_metadata
from celery_app import celery_app

# Non-terminal statuses that should be polled
ACTIVE_STATUSES = ['queued', 'in_progress']


@celery_app.task(name='app.tasks.compliance_tasks.poll_reports')
def poll_reports():
    """Scan non-terminal diagnosis records and update their status via Bailian.

    Uses an ownership-token Redis lock to prevent duplicate polling across workers.
    Transient network errors are silently skipped — the next poll cycle picks them up.
    Records older than REPORT_TASK_TIMEOUT_SECONDS are marked as 'failed'.
    """
    redis_url = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    r = redis.Redis.from_url(redis_url)

    # redis-py's Lock uses an ownership token, so an expired owner cannot
    # accidentally release a lock subsequently acquired by another worker.
    lock_key = 'lexport:poll_reports_lock'
    poll_interval = int(os.environ.get('REPORT_POLL_INTERVAL_SECONDS', 10))
    lock_timeout = max(60, poll_interval * 6)
    lock = r.lock(lock_key, timeout=lock_timeout, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        return  # another worker is handling this cycle

    try:
        # Find records that need polling
        records = (
            DiagnosisRecord.query
            .filter(DiagnosisRecord.status.in_(ACTIVE_STATUSES))
            .all()
        )

        if not records:
            return

        timeout_seconds = int(os.environ.get('REPORT_TASK_TIMEOUT_SECONDS', 7200))
        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)
        client = _get_bailian_client(timeout=30, max_retries=0)

        for record in records:
            # Keep the lock alive while processing a potentially large batch.
            lock.extend(lock_timeout, replace_ttl=True)

            # MySQL CURRENT_TIMESTAMP is returned as a naive value in the
            # database/session timezone; compare it with a naive local value.
            created = record.created_at
            if created.tzinfo is not None:
                created = created.astimezone().replace(tzinfo=None)

            if created < cutoff:
                _mark_status(record, 'failed')
                continue

            try:
                response = client.responses.retrieve(record.task_id)
                status = response.status

                if status == 'completed':
                    _mark_completed(record, response)
                elif status == 'failed':
                    _mark_status(record, 'failed')
                elif status == 'cancelled':
                    _mark_status(record, 'cancelled')
                elif status in ACTIVE_STATUSES:
                    record.status = status
                    db.session.commit()
                # Unknown statuses remain active locally and are retried until
                # the configured timeout instead of being treated as success.

            except InvalidReportError:
                current_app.logger.exception(
                    'Invalid completed report JSON for record %s', record.id
                )
                _mark_status(record, 'failed')
            except Exception:
                # Transient error — skip, next poll cycle retries
                current_app.logger.exception(
                    'Failed to poll compliance report %s', record.id
                )
                continue

    finally:
        try:
            lock.release()
        except LockError:
            # The lock may expire during an unusually slow upstream call. Its
            # ownership token prevents us from deleting a newer owner's lock.
            pass


def _mark_completed(record, response):
    """Write result and update status in a single transaction."""
    try:
        report_meta = {}
        if isinstance(record.param, dict):
            candidate = record.param.get('report_meta', {})
            if isinstance(candidate, dict):
                report_meta = candidate
        result_data = apply_report_metadata(
            response.model_dump(mode='json'),
            record.id,
            report_meta.get('ai_version') or current_app.config['REPORT_AI_VERSION'],
            report_meta.get('data_cutoff_date') or current_app.config['REPORT_DATA_CUTOFF_DATE'],
        )
        result_row = db.session.get(DiagnosisResult, record.id)
        if result_row is None:
            result_row = DiagnosisResult(record_id=record.id)
            db.session.add(result_row)
        result_row.result = result_data
        record.status = 'completed'
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _mark_status(record, status):
    """Write a non-success terminal status without creating a result row."""
    try:
        record.status = status
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
