"""
logging_config.py — structured (JSON) logging with request correlation IDs.

Every log line carries a request_id so a single request can be traced across
the app, the worker, and your log aggregator.
"""
import json
import logging
import sys
import uuid

from flask import g, has_request_context, request


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-") if has_request_context() else "-"
        record.path = request.path if has_request_context() else "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "path": getattr(record, "path", "-"),
        }
        for key in ("to", "subject", "slot_id", "user_id", "booking_id", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(app):
    level = getattr(logging, app.config["LOG_LEVEL"].upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if app.config["LOG_JSON"]:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(request_id)s %(name)s: %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    app.logger.setLevel(level)

    @app.before_request
    def _assign_request_id():
        g.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])

    @app.after_request
    def _echo_request_id(resp):
        resp.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        return resp
