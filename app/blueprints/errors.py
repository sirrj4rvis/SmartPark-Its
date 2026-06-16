"""errors.py — unified HTML/JSON error handling."""
from flask import Blueprint, jsonify, render_template, request

errors_bp = Blueprint("errors", __name__)


def _wants_json():
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _render(code, title, message):
    if _wants_json():
        return jsonify({"error": message, "code": code}), code
    return render_template("error.html", code=code, title=title, message=message), code


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return _render(403, "Forbidden", "You don't have access to this resource.")

    @app.errorhandler(404)
    def not_found(e):
        return _render(404, "Page Not Found", "The page you're looking for doesn't exist.")

    @app.errorhandler(429)
    def rate_limited(e):
        return _render(429, "Slow Down", "Too many requests. Please try again shortly.")

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("unhandled error")
        return _render(500, "Something Went Wrong", "An unexpected error occurred.")

    app.register_blueprint(errors_bp)
