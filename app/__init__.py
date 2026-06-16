"""
app/__init__.py — the application factory.

create_app() wires config, extensions, logging, observability, blueprints,
realtime, JWT and CLI commands into an isolated Flask instance. Tests build
their own app; gunicorn/celery import this factory.
"""
import os

from flask import Flask
from flask_jwt_extended import JWTManager

from config import get_config
from .extensions import cache, csrf, db, limiter, migrate, socketio

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

jwt = JWTManager()


def create_app(config_object=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app.config.from_object(config_object or get_config())

    # --- extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    cache.init_app(app)
    jwt.init_app(app)
    if app.config.get("TESTING") and not app.config.get("RATELIMIT_ENABLED", True):
        limiter.enabled = False
    limiter.init_app(app)
    socketio.init_app(app, message_queue=app.config.get("SOCKETIO_MESSAGE_QUEUE"))

    # --- logging & observability ---
    from .logging_config import configure_logging
    from .observability import init_observability

    configure_logging(app)
    init_observability(app)

    # --- template globals ---
    from .security import current_user

    @app.context_processor
    def inject_globals():
        return {"current_user": current_user, "CURRENCY": app.config["CURRENCY"]}

    @app.teardown_request
    def _clear_user_cache(exc=None):
        from flask import g

        g.pop("_cached_user", None)

    # --- blueprints ---
    from .blueprints.public import public_bp
    from .blueprints.auth import auth_bp
    from .blueprints.user import user_bp
    from .blueprints.admin import admin_bp
    from .blueprints.api import api_v1_bp, docs_bp
    from .blueprints.errors import register_error_handlers
    from .legacy_api import legacy_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_v1_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(legacy_bp)
    register_error_handlers(app)

    # --- realtime ---
    from .realtime import register_socketio_handlers

    register_socketio_handlers()

    # --- CLI ---
    from .cli import register_cli

    register_cli(app)

    return app
