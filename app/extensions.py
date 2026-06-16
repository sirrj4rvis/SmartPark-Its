"""
extensions.py — instantiate Flask extensions once, init them in the factory.

Keeping these decoupled from the app object avoids circular imports and lets
tests build isolated app instances.
"""
import os

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_socketio import SocketIO

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
cache = Cache()
limiter = Limiter(key_func=get_remote_address)
# Dev/tests default to 'threading' (no build deps). Production sets
# SOCKETIO_ASYNC_MODE=gevent to match the gevent WebSocket gunicorn worker,
# enabling native WebSockets; a Redis message_queue fans emits out across workers.
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode=os.environ.get("SOCKETIO_ASYNC_MODE", "threading"),
)
