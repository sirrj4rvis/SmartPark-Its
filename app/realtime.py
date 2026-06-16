"""
realtime.py — WebSocket layer (Flask-SocketIO).

Clients join the "slots" room and receive `slot_update` events whenever
availability changes. With a Redis message_queue configured, emits fan out
across every gunicorn worker, so it scales horizontally.

This replaces the old 20-second polling of /api/slots with true server push.
"""
from flask import request

from .extensions import socketio
from .services import slot_service


def register_socketio_handlers():
    @socketio.on("connect")
    def _on_connect(auth=None):
        socketio.emit("connected", {"sid": request.sid}, to=request.sid)

    @socketio.on("subscribe_slots")
    def _subscribe():
        from flask_socketio import join_room

        join_room("slots")
        socketio.emit("slot_snapshot", slot_service.availability_snapshot(), to=request.sid)


def broadcast_slots():
    """Push the latest availability to every subscriber. Call after mutations."""
    slot_service.invalidate_availability()
    socketio.emit("slot_update", slot_service.availability_snapshot(), to="slots")
