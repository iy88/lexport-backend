import os

from celery import Celery, Task

from app import create_app


config_name = os.environ.get('FLASK_ENV', 'development')
flask_app = create_app(config_name)


class FlaskTask(Task):
    """Run every Celery task inside the configured Flask app context."""

    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)


celery_app = Celery(
    'lexport',
    task_cls=FlaskTask,
    include=['app.tasks.compliance_tasks'],
)
celery_app.config_from_object('config.CeleryConfig')

celery_app.conf.beat_schedule = {
    'poll-compliance-reports': {
        'task': 'app.tasks.compliance_tasks.poll_reports',
        'schedule': float(os.environ.get('REPORT_POLL_INTERVAL_SECONDS', 10)),
    },
}
celery_app.conf.timezone = 'Asia/Shanghai'
