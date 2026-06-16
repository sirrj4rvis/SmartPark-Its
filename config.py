"""
config.py — 12-factor configuration for SmartPark ITS.

All environment-specific values come from environment variables so the same
image runs unchanged across dev / staging / prod. Never hardcode secrets.
"""
import os
from datetime import timedelta


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


class BaseConfig:
    # --- Core ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me-0123456789")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)

    # --- Database ---
    # DATABASE_URL example: postgresql+psycopg://user:pass@host:5432/smartpark
    # Falls back to a local SQLite file so the app always boots with zero config.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.path.dirname(__file__), "database.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # --- Redis (cache, rate-limit, socket.io message queue, celery broker) ---
    REDIS_URL = os.environ.get("REDIS_URL", "memory://")
    CACHE_TYPE = "RedisCache" if os.environ.get("REDIS_URL") else "SimpleCache"
    CACHE_REDIS_URL = os.environ.get("REDIS_URL")
    CACHE_DEFAULT_TIMEOUT = 30

    # --- Sessions / cookies ---
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)

    # --- Security / auth hardening ---
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", 5))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", 15))
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per minute")
    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "memory://")
    WTF_CSRF_TIME_LIMIT = None  # tie CSRF token to the session lifetime

    # --- Business rules ---
    CURRENCY = "₹"
    MIN_BILLED_HOURS = 1
    RESERVATION_TTL_MINUTES = int(os.environ.get("RESERVATION_TTL_MINUTES", 10))
    # Dynamic pricing: surge multiplier grows with occupancy.
    PRICING_SURGE_ENABLED = _bool("PRICING_SURGE_ENABLED", True)
    PRICING_SURGE_MAX = float(os.environ.get("PRICING_SURGE_MAX", 2.0))
    PRICING_SURGE_THRESHOLD = float(os.environ.get("PRICING_SURGE_THRESHOLD", 0.6))

    # --- Observability ---
    SENTRY_DSN = os.environ.get("SENTRY_DSN")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_JSON = _bool("LOG_JSON", True)
    METRICS_ENABLED = _bool("METRICS_ENABLED", True)

    # --- Realtime ---
    SOCKETIO_MESSAGE_QUEUE = os.environ.get("REDIS_URL")  # None => in-process

    # --- Celery ---
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "memory://"))
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", os.environ.get("REDIS_URL"))

    DEBUG = False
    TESTING = False
    ENV_NAME = "base"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    ENV_NAME = "development"
    LOG_JSON = _bool("LOG_JSON", False)


class TestingConfig(BaseConfig):
    TESTING = True
    ENV_NAME = "testing"
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    CACHE_TYPE = "SimpleCache"
    PRICING_SURGE_ENABLED = True
    LOG_LEVEL = "WARNING"


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)

    def __init__(self):
        # Fail fast: never run prod with the insecure default secret.
        if self.SECRET_KEY.startswith("dev-only-insecure-key-change-me"):
            raise RuntimeError("SECRET_KEY must be set in production")


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config():
    name = os.environ.get("FLASK_ENV", "development").lower()
    cfg = _CONFIGS.get(name, DevelopmentConfig)
    return cfg() if isinstance(cfg, type) and name == "production" else cfg
