"""
security.py — auth helpers, route guards, and login hardening.

- Session-based auth for the web UI.
- Login attempt throttling + temporary account lockout.
"""
from datetime import timedelta
from functools import wraps

from flask import current_app, flash, g, redirect, session, url_for

from .extensions import db
from .models import Role, User, utcnow


def current_user():
    if "user_id" not in session:
        return None
    if getattr(g, "_cached_user", None) is None:
        g._cached_user = db.session.get(User, session["user_id"])
    return g._cached_user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        if user.role != Role.admin:
            flash("Admin access required.", "danger")
            return redirect(url_for("user.dashboard"))
        return f(*args, **kwargs)
    return wrapper


def authenticate(email: str, password: str):
    """Return (user, error_message). Applies lockout policy."""
    email = (email or "").strip().lower()
    user = db.session.query(User).filter_by(email=email).first()
    if not user:
        return None, "Invalid email or password."
    if user.is_locked:
        return None, "Account temporarily locked due to failed attempts. Try again later."

    if user.check_password(password):
        user.failed_logins = 0
        user.locked_until = None
        db.session.commit()
        return user, None

    # Wrong password — increment and maybe lock.
    user.failed_logins = (user.failed_logins or 0) + 1
    max_attempts = current_app.config["LOGIN_MAX_ATTEMPTS"]
    if user.failed_logins >= max_attempts:
        user.locked_until = utcnow() + timedelta(minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"])
        user.failed_logins = 0
        db.session.commit()
        return None, "Too many failed attempts. Account locked for a while."
    db.session.commit()
    return None, "Invalid email or password."


def establish_session(user: User):
    session.clear()
    session["user_id"] = user.id
    session["name"] = user.name
    session["role"] = user.role.value
    session.permanent = True
