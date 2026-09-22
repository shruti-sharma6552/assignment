"""Booking creation: validation, atomic seat reservation, price snapshot."""

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from models import Booking, BookingItem, BookingStatus, Membership, SeatTier, db
from services.invoice_service import create_invoice, generate_booking_reference
from services.pricing_service import PricingError, quote_for_tier


class BookingError(Exception):
    """Raised when a booking cannot be created. Message is user-facing."""


MAX_TICKETS_PER_BOOKING = 10


def validate_selection(seat_tier, quantity):
    """Validate tier state and requested quantity. Raises BookingError."""
    if seat_tier is None:
        raise BookingError("Invalid ticket tier.")

    show = seat_tier.show
    if show is None or not show.is_bookable:
        raise BookingError("This show is no longer available for booking.")

    if seat_tier.status != "ACTIVE":
        raise BookingError(f"{seat_tier.name} tickets are not on sale for this show.")

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise BookingError("Please select at least one ticket.")

    if quantity <= 0:
        raise BookingError("Please select at least one ticket.")

    if quantity > MAX_TICKETS_PER_BOOKING:
        raise BookingError(
            f"A maximum of {MAX_TICKETS_PER_BOOKING} tickets can be booked at once."
        )

    if seat_tier.available_seats <= 0:
        raise BookingError(f"{seat_tier.name} tickets are sold out.")

    if quantity > seat_tier.available_seats:
        raise BookingError(
            f"Only {seat_tier.available_seats} {seat_tier.name} "
            f"ticket{'s' if seat_tier.available_seats != 1 else ''} are available."
        )

    return quantity


def resolve_membership(membership_id):
    """Return an active Membership for the given id, or None for no membership."""
    if not membership_id:
        return None
    membership = db.session.get(Membership, int(membership_id))
    if membership is None:
        raise BookingError("Invalid membership.")
    if not membership.active:
        raise BookingError("Invalid membership: this membership is no longer active.")
    return membership


def _reserve_seats(seat_tier_id, quantity) -> bool:
    """Atomically decrement availability.

    The conditional UPDATE means the database itself refuses to go below zero,
    so two simultaneous bookings for the last seat can never both succeed.
    Returns True when the seats were reserved by this call.
    """
    result = db.session.execute(
        update(SeatTier)
        .where(SeatTier.id == seat_tier_id, SeatTier.available_seats >= quantity)
        .values(available_seats=SeatTier.available_seats - quantity)
    )
    return result.rowcount == 1


def create_booking(user, seat_tier_id, quantity, membership_id=None, selected_seats=None) -> Booking:
    """Validate, price, reserve seats and persist a booking in one transaction."""
    seat_tier = db.session.get(SeatTier, int(seat_tier_id)) if seat_tier_id else None
    quantity = validate_selection(seat_tier, quantity)
    membership = resolve_membership(membership_id)

    try:
        # The price is always recalculated here from database configuration.
        # Anything the browser submitted is ignored.
        breakdown = quote_for_tier(seat_tier, quantity, membership)
    except PricingError as exc:
        raise BookingError(str(exc)) from exc

    try:
        if not _reserve_seats(seat_tier.id, quantity):
            db.session.rollback()
            raise BookingError(
                "Booking could not be completed because availability changed. "
                "Please try again."
            )

        booking = Booking(
            booking_id=generate_booking_reference(),
            user_id=user.id,
            show_id=seat_tier.show_id,
            total_amount=breakdown["final_amount"],
            status=BookingStatus.CONFIRMED,
            created_at=datetime.utcnow(),
        )
        db.session.add(booking)
        db.session.flush()

        item = BookingItem(
            booking_id=booking.id,
            seat_tier_id=seat_tier.id,
            seat_tier=seat_tier.name,
            ticket_price_at_booking=breakdown["ticket_price"],
            quantity=quantity,
            booked_seats=selected_seats,
            base_amount=breakdown["base_amount"],
            festival_discount=breakdown["festival_discount"],
            member_discount=breakdown["member_discount"],
            discounted_amount=breakdown["discounted_amount"],
            convenience_fee=breakdown["convenience_fee"],
            taxable_amount=breakdown["taxable_amount"],
            gst_rate=breakdown["gst_rate"],
            gst_amount=breakdown["gst_amount"],
            final_amount=breakdown["final_amount"],
            membership_name=breakdown["membership_name"],
            festival_name=breakdown["festival_name"],
        )
        db.session.add(item)
        create_invoice(booking, breakdown)
        db.session.commit()
    except BookingError:
        raise
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise BookingError(
            "Something went wrong while creating your booking."
        ) from exc

    db.session.refresh(booking)
    return booking
