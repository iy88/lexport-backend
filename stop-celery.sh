#!/usr/bin/env sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNTIME_DIR=${CELERY_RUNTIME_DIR:-"$PROJECT_DIR/logs"}
STOP_TIMEOUT=${CELERY_STOP_TIMEOUT:-30}

WORKER_PIDFILE="$RUNTIME_DIR/worker.pid"
BEAT_PIDFILE="$RUNTIME_DIR/beat.pid"
STOP_FAILED=0

case "$STOP_TIMEOUT" in
    ''|*[!0-9]*)
        echo "CELERY_STOP_TIMEOUT must be a non-negative integer" >&2
        exit 1
        ;;
esac

read_pid() {
    pidfile=$1
    [ -r "$pidfile" ] || return 1
    pid=$(cat "$pidfile")
    case "$pid" in
        ''|*[!0-9]*) return 1 ;;
    esac
    printf '%s\n' "$pid"
}

is_expected_process() {
    pid=$1
    role=$2
    command=$(ps -p "$pid" -o command= 2>/dev/null || true)
    case "$command" in
        *celery*"$role"*) return 0 ;;
        *) return 1 ;;
    esac
}

signal_from_pidfile() {
    name=$1
    role=$2
    pidfile=$3

    if ! pid=$(read_pid "$pidfile"); then
        [ ! -e "$pidfile" ] || rm -f "$pidfile"
        echo "$name is not running (no valid PID file)."
        return
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$pidfile"
        echo "$name is not running (removed stale PID file)."
        return
    fi

    if ! is_expected_process "$pid" "$role"; then
        echo "Refusing to signal PID $pid: it is not the expected $name process." >&2
        STOP_FAILED=1
        return
    fi

    kill -TERM "$pid"
    echo "Stopping $name (PID $pid)..."
}

wait_from_pidfile() {
    name=$1
    role=$2
    pidfile=$3

    pid=$(read_pid "$pidfile" 2>/dev/null || true)
    [ -n "$pid" ] || return
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$pidfile"
        echo "$name stopped."
        return
    fi
    if ! is_expected_process "$pid" "$role"; then
        echo "PID $pid changed before shutdown completed; leaving the PID file for review." >&2
        STOP_FAILED=1
        return
    fi

    elapsed=0
    while kill -0 "$pid" 2>/dev/null && [ "$elapsed" -lt "$STOP_TIMEOUT" ]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done

    if kill -0 "$pid" 2>/dev/null; then
        echo "$name did not stop within ${STOP_TIMEOUT}s; PID $pid was left running." >&2
        STOP_FAILED=1
        return
    fi

    rm -f "$pidfile"
    echo "$name stopped."
}

# Stop the scheduler first so it cannot enqueue new work during shutdown.
signal_from_pidfile "Celery beat" "beat" "$BEAT_PIDFILE"
signal_from_pidfile "Celery worker" "worker" "$WORKER_PIDFILE"

wait_from_pidfile "Celery beat" "beat" "$BEAT_PIDFILE"
wait_from_pidfile "Celery worker" "worker" "$WORKER_PIDFILE"

exit "$STOP_FAILED"
