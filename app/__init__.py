from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError

from .config import Config
from .extensions import csrf, db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    csrf.init_app(app)

    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.projects import projects_bp
    from .routes.tasks import tasks_bp
    from .routes.users import users_bp
    from .routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    from .seed import register_commands

    register_commands(app)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "CSRF token missing or invalid"}), 400
        return render_template("errors/403.html"), 403

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.context_processor
    def inject_globals():
        from datetime import date as _date
        return {"today_date": _date.today()}

    @app.context_processor
    def inject_notifications():
        from .auth import current_user
        from .models import Notification

        user = current_user()
        unread_notifications = 0
        if user:
            unread_notifications = Notification.query.filter_by(
                user_id=user.id,
                is_read=False,
            ).count()
        return {"unread_notifications": unread_notifications}

    return app
