"""Price breakdown, booking confirmation, invoice and booking history."""

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for
)
from flask_login import current_user, login_required

from models import Booking, Membership, SeatTier, Show, db
from services.booking_service import (
    BookingError, create_booking, resolve_membership, validate_selection
)
from services.invoice_service import build_invoice_context
from services.pricing_service import PricingError, quote_for_tier

booking_bp = Blueprint("booking", __name__)


@booking_bp.route("/price-breakdown/<int:show_id>", methods=["POST"])
@login_required
def price_breakdown(show_id):
    """Server-side price preview shown before the customer confirms."""
    show = db.session.get(Show, show_id)
    if show is None or not show.is_bookable:
        abort(404)

    seat_tier_id = request.form.get("seat_tier_id")
    quantity = request.form.get("quantity")
    membership_id = request.form.get("membership_id") or None
    selected_seats = request.form.get("selected_seats") or None

    seat_tier = db.session.get(SeatTier, int(seat_tier_id)) if seat_tier_id else None

    try:
        quantity = validate_selection(seat_tier, quantity)
        membership = resolve_membership(membership_id)
        breakdown = quote_for_tier(seat_tier, quantity, membership)
    except (BookingError, PricingError) as exc:
        flash(str(exc), "danger")
        return redirect(url_for("customer.ticket_selection", show_id=show_id))

    return render_template(
        "price_breakdown.html",
        show=show,
        seat_tier=seat_tier,
        quantity=quantity,
        membership=membership,
        breakdown=breakdown,
        selected_seats=selected_seats,
    )


@booking_bp.route("/booking/create", methods=["POST"])
@login_required
def create():
    """Recalculate the price server-side, reserve seats and store the booking."""
    seat_tier_id = request.form.get("seat_tier_id")
    quantity = request.form.get("quantity")
    membership_id = request.form.get("membership_id") or None
    selected_seats = request.form.get("selected_seats") or None

    seat_tier = db.session.get(SeatTier, int(seat_tier_id)) if seat_tier_id else None
    if seat_tier is None:
        flash("Invalid ticket tier.", "danger")
        return redirect(url_for("customer.home"))

    show_id = seat_tier.show_id

    try:
        booking = create_booking(current_user, seat_tier_id, quantity, membership_id, selected_seats)
    except BookingError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("customer.ticket_selection", show_id=show_id))

    return redirect(url_for("booking.success", booking_pk=booking.id))


def _owned_booking(booking_pk) -> Booking:
    booking = db.session.get(Booking, booking_pk)
    if booking is None:
        abort(404)
    if booking.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return booking


@booking_bp.route("/booking/<int:booking_pk>")
@login_required
def success(booking_pk):
    booking = _owned_booking(booking_pk)
    return render_template("booking_success.html", **build_invoice_context(booking))


@booking_bp.route("/invoice/<int:booking_pk>")
@login_required
def invoice(booking_pk):
    booking = _owned_booking(booking_pk)
    return render_template("invoice.html", **build_invoice_context(booking))


@booking_bp.route("/my-bookings")
@login_required
def my_bookings():
    bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template("booking_history.html", bookings=bookings)


@booking_bp.route("/membership")
@login_required
def membership_info():
    memberships = Membership.query.filter_by(active=True).order_by(Membership.id).all()
    return render_template("membership.html", memberships=memberships)
