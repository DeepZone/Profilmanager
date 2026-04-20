import os
import subprocess

from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate
from app.services.version_service import VersionService, VersionServiceError


def _resolve_release_id() -> str | None:
    release_id = os.getenv("APP_RELEASE_ID")
    if release_id:
        return release_id.strip()

    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_global_version():
        try:
            app_version = VersionService.get_version_string()
        except VersionServiceError:
            app_version = "0.2.7683"
        return {"app_version": app_version}

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.gitlab_mr import gitlab_bp
    from app.routes.profiles import profiles_bp
    from app.routes.settings import settings_bp
    from app.routes.users import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(gitlab_bp)

    with app.app_context():
        try:
            VersionService.initialize_version_if_missing()
            VersionService.bump_build_for_release(_resolve_release_id())
        except SQLAlchemyError:
            app.logger.debug("Versionsinitialisierung übersprungen, Tabellen sind noch nicht verfügbar.")

    return app
