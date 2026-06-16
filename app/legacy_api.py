"""
legacy_api.py — backwards-compatible /api/slots endpoint.

Kept so the dashboard degrades gracefully to polling if WebSockets are blocked
(corporate proxies, etc.). New clients should use WebSockets or /api/v1.
"""
from flask import Blueprint, jsonify

from .extensions import csrf
from .services import slot_service

legacy_bp = Blueprint("legacy", __name__)
csrf.exempt(legacy_bp)


@legacy_bp.get("/api/slots")
def api_slots():
    return jsonify(slot_service.availability_snapshot())
