"""admin.py — admin console: stats, slot management, bookings, analytics."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Booking
from ..security import admin_required
from ..services import analytics_service, slot_service
from ..realtime import broadcast_slots

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@admin_required
def dashboard():
    k = analytics_service.kpis()
    c = slot_service.counts()
    recent = (
        db.session.query(Booking).order_by(Booking.start_time.desc()).limit(5).all()
    )
    return render_template(
        "admin/admin_dashboard.html",
        total_slots=c["total"], avail_slots=c["available"], occupied_slots=c["occupied"],
        total_users=k["total_users"], total_books=k["total_bookings"],
        active_books=k["active_bookings"], revenue=k["revenue"], recent_books=recent,
    )


@admin_bp.route("/analytics")
@admin_required
def analytics():
    return render_template(
        "admin/analytics.html",
        kpis=analytics_service.kpis(),
        revenue=analytics_service.revenue_trend(),
        peaks=analytics_service.peak_hours(),
        mix=analytics_service.vehicle_mix(),
        gauge=analytics_service.occupancy_gauge(),
    )


@admin_bp.route("/slots")
@admin_required
def manage_slots():
    return render_template("admin/manage_slots.html", slots=slot_service.list_slots())


@admin_bp.route("/slots/add", methods=["POST"])
@admin_required
def add_slot():
    try:
        rate = request.form.get("rate_per_hour", type=float)
        slot = slot_service.add_slot(
            request.form.get("slot_number"), request.form.get("location"),
            request.form.get("vehicle_type"), rate,
        )
        broadcast_slots()
        flash(f"Slot {slot.slot_number} added successfully.", "success")
    except slot_service.SlotError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("admin.manage_slots"))


@admin_bp.route("/slots/delete/<int:slot_id>", methods=["POST"])
@admin_required
def delete_slot(slot_id):
    try:
        slot_service.delete_slot(slot_id)
        broadcast_slots()
        flash("Slot deleted.", "success")
    except slot_service.SlotError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("admin.manage_slots"))


@admin_bp.route("/slots/toggle/<int:slot_id>", methods=["POST"])
@admin_required
def toggle_slot(slot_id):
    try:
        slot = slot_service.toggle_slot(slot_id)
        broadcast_slots()
        flash(f"Slot {slot.slot_number} status changed to {slot.status.value}.", "info")
    except slot_service.SlotError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("admin.manage_slots"))


@admin_bp.route("/bookings")
@admin_required
def all_bookings():
    page = request.args.get("page", 1, type=int)
    search = (request.args.get("q") or "").strip()
    query = db.session.query(Booking).order_by(Booking.start_time.desc())
    if search:
        from ..models import User, ParkingSlot

        query = (
            query.join(User, Booking.user_id == User.id)
            .join(ParkingSlot, Booking.slot_id == ParkingSlot.id)
            .filter(
                db.or_(
                    Booking.vehicle_number.ilike(f"%{search}%"),
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    ParkingSlot.slot_number.ilike(f"%{search}%"),
                )
            )
        )
    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "admin/all_bookings.html", bookings=pagination.items, pagination=pagination, search=search
    )
