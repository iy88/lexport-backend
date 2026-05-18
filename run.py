import os
from app import create_app

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', True), host='0.0.0.0', port=6768)
