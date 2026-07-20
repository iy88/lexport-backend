import os

from app import create_app

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    if os.environ.get('CELERY_AUTO_START', '').lower() in ('1', 'true', 'yes'):
        # Flask debug reloader spawns a child process with WERKZEUG_RUN_MAIN=true.
        # We only start Celery in the reloader child (actual server) or when
        # debug mode is off — never in the reloader parent, to avoid double-launch.
        in_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        debug = app.config.get('DEBUG', False)
        if in_reloader or not debug:
            from app.utils.celery_runner import start as start_celery
            start_celery()

    app.run(debug=app.config.get('DEBUG', True), host='0.0.0.0', port=6768)
