"""auth.py — register, login (hardened), logout."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db, limiter
from ..models import Role, User
from ..security import authenticate, establish_session
from ..validators import is_valid_email

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))
        if not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("auth.register"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return redirect(url_for("auth.register"))

        user = User(name=name, email=email, role=Role.user)
        user.set_password(password)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Email already registered.", "danger")
            return redirect(url_for("auth.register"))

        flash("Account created! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email") or ""
        password = request.form.get("password") or ""
        user, error = authenticate(email, password)
        if error:
            flash(error, "danger")
            return redirect(url_for("auth.login"))

        establish_session(user)
        flash(f"Welcome back, {user.name}!", "success")
        if user.role == Role.admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("user.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    from flask import session

    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("public.index"))
