"""settings.py — account settings (all users) + system settings (admin)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Role
from ..security import admin_required, current_user, login_required
from ..services import settings_service

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.get("/")
@login_required
def index():
    user = current_user()
    system = settings_service.all_settings() if user.role == Role.admin else None
    return render_template("settings.html", user=user, system=system)


@settings_bp.post("/profile")
@login_required
def update_profile():
    user = current_user()
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Name cannot be empty.", "danger")
        return redirect(url_for("settings.index"))
    user.name = name
    user.email_notifications = bool(request.form.get("email_notifications"))
    db.session.commit()
    from flask import session

    session["name"] = user.name
    flash("Profile updated.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.post("/password")
@login_required
def change_password():
    user = current_user()
    current = request.form.get("current_password") or ""
    new = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not user.check_password(current):
        flash("Current password is incorrect.", "danger")
    elif len(new) < 8:
        flash("New password must be at least 8 characters.", "danger")
    elif new != confirm:
        flash("New passwords do not match.", "danger")
    else:
        user.set_password(new)
        db.session.commit()
        flash("Password changed successfully.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.post("/system")
@admin_required
def update_system():
    settings_service.set_many({
        "pricing_surge_enabled": "on" if request.form.get("pricing_surge_enabled") else "off",
        "pricing_surge_threshold": request.form.get("pricing_surge_threshold"),
        "pricing_surge_max": request.form.get("pricing_surge_max"),
        "reservation_ttl_minutes": request.form.get("reservation_ttl_minutes"),
        "upi_vpa": request.form.get("upi_vpa", ""),
        "upi_payee_name": request.form.get("upi_payee_name", ""),
    })
    # Re-price immediately so changes take visible effect.
    from ..services import pricing_service
    from ..realtime import broadcast_slots

    pricing_service.reprice_all()
    broadcast_slots()
    flash("System settings saved.", "success")
    return redirect(url_for("settings.index"))
