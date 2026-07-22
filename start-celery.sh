#!/usr/bin/env sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNTIME_DIR=${CELERY_RUNTIME_DIR:-"$PROJECT_DIR/logs"}
PYTHON_BIN=${PYTHON_BIN:-python}
LOG_LEVEL=${CELERY_LOG_LEVEL:-INFO}
WORKER_CONCURRENCY=${CELERY_WORKER_CONCURRENCY:-1}

WORKER_PIDFILE="$RUNTIME_DIR/worker.pid"
BEAT_PIDFILE="$RUNTIME_DIR/beat.pid"
WORKER_LOGFILE="$RUNTIME_DIR/worker.log"
BEAT_LOGFILE="$RUNTIME_DIR/beat.log"

case "$WORKER_CONCURRENCY" in
    ''|*[!0-9]*|0)
        echo "CELERY_WORKER_CONCURRENCY must be a positive integer" >&2
        exit 1
        ;;
esac

mkdir -p "$RUNTIME_DIR"
cd "$PROJECT_DIR"

pid_is_running() {
    pidfile=$1
    role=$2
    [ -r "$pidfile" ] || return 1
    pid=$(cat "$pidfile")
    case "$pid" in
        ''|*[!0-9]*) return 1 ;;
    esac
    kill -0 "$pid" 2>/dev/null || return 1
    command=$(ps -p "$pid" -o command= 2>/dev/null || true)
    case "$command" in
        *celery*"$role"*) return 0 ;;
        *) return 1 ;;
    esac
}

clear_stale_pidfile() {
    pidfile=$1
    role=$2
    if [ -e "$pidfile" ] && ! pid_is_running "$pidfile" "$role"; then
        rm -f "$pidfile"
    fi
}

clear_stale_pidfile "$WORKER_PIDFILE" "worker"
clear_stale_pidfile "$BEAT_PIDFILE" "beat"

worker_started=false

if pid_is_running "$WORKER_PIDFILE" "worker"; then
    echo "Celery worker is already running (PID $(cat "$WORKER_PIDFILE"))."
else
    "$PYTHON_BIN" -m celery -A celery_app:celery_app worker \
        --loglevel="$LOG_LEVEL" \
        --concurrency="$WORKER_CONCURRENCY" \
        --logfile="$WORKER_LOGFILE" \
        --pidfile="$WORKER_PIDFILE" \
        --detach
    worker_started=true
    echo "Celery worker started (PID $(cat "$WORKER_PIDFILE"))."
fi

if pid_is_running "$BEAT_PIDFILE" "beat"; then
    echo "Celery beat is already running (PID $(cat "$BEAT_PIDFILE"))."
else
    if ! "$PYTHON_BIN" -m celery -A celery_app:celery_app beat \
        --loglevel="$LOG_LEVEL" \
        --logfile="$BEAT_LOGFILE" \
        --pidfile="$BEAT_PIDFILE" \
        --schedule="$RUNTIME_DIR/celerybeat-schedule" \
        --detach; then
        if [ "$worker_started" = true ] && pid_is_running "$WORKER_PIDFILE" "worker"; then
            kill -TERM "$(cat "$WORKER_PIDFILE")" 2>/dev/null || true
        fi
        echo "Failed to start Celery beat; the worker started by this run was stopped." >&2
        exit 1
    fi
    echo "Celery beat started (PID $(cat "$BEAT_PIDFILE"))."
fi

echo "Logs: $WORKER_LOGFILE and $BEAT_LOGFILE"
