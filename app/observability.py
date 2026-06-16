"""
observability.py — Sentry error tracking, Prometheus metrics, health probes.

Endpoints:
  GET /healthz  — liveness + DB connectivity (for load balancers / k8s)
  GET /metrics  — Prometheus exposition format
"""
import time

from flask import Blueprint, Response, current_app, g, jsonify, request
from sqlalchemy import text

from .extensions import db

ops_bp = Blueprint("ops", __name__)

# Prometheus metrics (registered lazily to stay optional).
_metrics = {}


def _init_metrics():
    if _metrics:
        return
    try:
        from prometheus_client import Counter, Histogram

        _metrics["requests"] = Counter(
            "smartpark_http_requests_total", "HTTP requests", ["method", "endpoint", "status"]
        )
        _metrics["latency"] = Histogram(
            "smartpark_http_request_duration_seconds", "Request latency", ["endpoint"]
        )
    except Exception:  # pragma: no cover
        pass


def init_observability(app):
    # --- Sentry ---
    dsn = app.config.get("SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration

            sentry_sdk.init(dsn=dsn, integrations=[FlaskIntegration()], traces_sample_rate=0.1)
            app.logger.info("Sentry initialised")
        except Exception as exc:  # pragma: no cover
            app.logger.warning(f"Sentry init failed: {exc}")

    # --- Prometheus request instrumentation ---
    if app.config.get("METRICS_ENABLED"):
        _init_metrics()

        @app.before_request
        def _start_timer():
            g._start = time.perf_counter()

        @app.after_request
        def _record(resp):
            if "requests" in _metrics:
                endpoint = request.endpoint or "unknown"
                _metrics["requests"].labels(request.method, endpoint, resp.status_code).inc()
                if hasattr(g, "_start"):
                    _metrics["latency"].labels(endpoint).observe(time.perf_counter() - g._start)
            return resp

    app.register_blueprint(ops_bp)


@ops_bp.route("/healthz")
def healthz():
    checks = {"app": "ok"}
    status = 200
    try:
        db.session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"
        status = 503
    return jsonify({"status": "ok" if status == 200 else "degraded", "checks": checks}), status


@ops_bp.route("/metrics")
def metrics():
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    except Exception:
        return jsonify({"error": "prometheus_client not installed"}), 501
