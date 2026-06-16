"""user.py — driver-facing flows: dashboard, booking, exit, receipt, history."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Booking, BookingStatus, ParkingSlot
from ..security import current_user, login_required
from ..services import booking_service, forecast_service, notification_service, slot_service
from ..realtime import broadcast_slots

user_bp = Blueprint("user", __name__)


@user_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    slots = slot_service.list_slots()
    active = (
        db.session.query(Booking)
        .filter_by(user_id=user.id, status=BookingStatus.active)
        .first()
    )
    recommendations = forecast_service.recommend_slots(limit=3)
    return render_template(
        "dashboard.html", slots=slots, active_booking=active, recommendations=recommendations
    )


@user_bp.route("/book/<int:slot_id>", methods=["GET", "POST"])
@login_required
def book_slot(slot_id):
    user = current_user()
    slot = db.session.get(ParkingSlot, slot_id)
    if not slot:
        flash("Slot not found.", "danger")
        return redirect(url_for("user.dashboard"))

    if request.method == "POST":
        try:
            booking_service.book_slot(user.id, slot_id, request.form.get("vehicle_number"))
            broadcast_slots()
            flash(f"Slot {slot.slot_number} booked successfully! 🎉", "success")
            return redirect(url_for("user.dashboard"))
        except booking_service.BookingError as exc:
            flash(str(exc), "warning")
            return redirect(url_for("user.dashboard"))

    return render_template("booking.html", slot=slot)


@user_bp.route("/exit/<int:booking_id>", methods=["POST"])
@login_required
def exit_slot(booking_id):
    user = current_user()
    try:
        booking = booking_service.exit_booking(user.id, booking_id)
        broadcast_slots()
        notification_service.notify(user.email, "Parking receipt", f"Total {booking.total_cost}")
        flash("You have exited successfully. Here is your receipt.", "success")
        return redirect(url_for("user.receipt", booking_id=booking.id))
    except booking_service.BookingError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("user.dashboard"))


@user_bp.route("/receipt/<int:booking_id>")
@login_required
def receipt(booking_id):
    user = current_user()
    booking = (
        db.session.query(Booking).filter_by(id=booking_id, user_id=user.id).first()
    )
    if not booking:
        flash("Receipt not found.", "danger")
        return redirect(url_for("user.dashboard"))
    qr = notification_service.receipt_qr_data_uri(booking)
    return render_template("receipt.html", booking=booking, qr=qr)


@user_bp.route("/my_bookings")
@login_required
def my_bookings():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    pagination = (
        db.session.query(Booking)
        .filter_by(user_id=user.id)
        .order_by(Booking.start_time.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("my_bookings.html", bookings=pagination.items, pagination=pagination)
