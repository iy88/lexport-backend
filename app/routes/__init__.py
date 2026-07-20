def register_blueprints(app):
    from app.routes.auth import auth_bp
    from app.routes.user import user_bp
    from app.routes.law import law_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    from app.routes.agency import agency_bp
    app.register_blueprint(law_bp, url_prefix='/api/laws')
    from app.routes.news import news_bp
    app.register_blueprint(agency_bp, url_prefix='/api/agencies')
    from app.routes.stat import stat_bp
    app.register_blueprint(news_bp, url_prefix='/api/news')
    from app.routes.admin import admin_bp
    from app.routes.compliance import compliance_bp
    app.register_blueprint(stat_bp, url_prefix='/api/stats')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(compliance_bp, url_prefix='/api/compliance-reports')
