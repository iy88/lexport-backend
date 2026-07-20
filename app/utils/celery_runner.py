"""
Celery subprocess runner for development convenience.

When CELERY_AUTO_START=true, run.py spawns worker + beat as child processes.
SIGINT / SIGTERM propagates to children for graceful shutdown.
"""
import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


_children: list[subprocess.Popen] = []
_project_root = Path(__file__).resolve().parents[2]


def _signal_process_group(process, sig):
    try:
        os.killpg(process.pid, sig)
    except OSError:
        pass


def _cleanup():
    """Send SIGTERM to all tracked children, wait briefly, then force-kill."""
    for p in _children:
        _signal_process_group(p, signal.SIGTERM)
    for p in _children:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _signal_process_group(p, signal.SIGKILL)
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
    _children.clear()


def _make_worker_cmd():
    return [
        sys.executable, '-m', 'celery', '-A', 'celery_app:celery_app',
        'worker', '--loglevel=INFO', '--concurrency=1',
    ]


def _make_beat_cmd():
    return [
        sys.executable, '-m', 'celery', '-A', 'celery_app:celery_app',
        'beat', '--loglevel=INFO',
    ]


def _handle_signal(signum, frame):
    _cleanup()
    # Re-raise the original signal after cleanup so Flask's own handler runs
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def start():
    """Spawn Celery worker and beat as background subprocesses."""
    if any(p.poll() is None for p in _children):
        raise RuntimeError('Celery worker/beat 已经启动')

    env = os.environ.copy()
    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        worker = subprocess.Popen(
            _make_worker_cmd(),
            env=env,
            cwd=_project_root,
            start_new_session=True,
        )
        _children.append(worker)

        beat = subprocess.Popen(
            _make_beat_cmd(),
            env=env,
            cwd=_project_root,
            start_new_session=True,
        )
        _children.append(beat)

        grace_seconds = float(os.environ.get('CELERY_AUTO_STARTUP_GRACE_SECONDS', 1.0))
        time.sleep(max(0.1, grace_seconds))
        failed = [p for p in _children if p.poll() is not None]
        if failed:
            codes = ', '.join(str(p.returncode) for p in failed)
            raise RuntimeError(f'Celery 子进程启动失败，退出码: {codes}')
    except BaseException:
        _cleanup()
        raise

    print(f'[celery-runner] worker started  (pid={worker.pid})')
    print(f'[celery-runner] beat started    (pid={beat.pid})')
