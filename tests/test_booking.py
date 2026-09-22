"""Booking service tests: validation, availability, snapshots, oversell."""

from decimal import Decimal

import pytest

from models import Booking, SeatTier, db
from services.booking_service import BookingError, create_booking


def test_successful_booking_totals_778_80(catalogue):
    """End to end: the stored booking total is exactly 778.80."""
    booking = create_booking(
        user=catalogue["customer"],
        seat_tier_id=catalogue["gold"].id,
        quantity=3,
        membership_id=catalogue["membership"].id,
    )
    assert booking.total_amount == Decimal("778.80")

    item = booking.item
    assert item.base_amount == Decimal("750.00")
    assert item.festival_discount == Decimal("100.00")
    assert item.member_discount == Decimal("50.00")
    assert item.discounted_amount == Decimal("600.00")
    assert item.convenience_fee == Decimal("60.00")
    assert item.taxable_amount == Decimal("660.00")
    assert item.gst_amount == Decimal("118.80")
    assert item.final_amount == Decimal("778.80")
    assert booking.booking_id.startswith("CINE-")
    assert booking.invoice is not None


def test_5_sold_out_tier_cannot_be_booked(catalogue):
    with pytest.raises(BookingError, match="sold out"):
        create_booking(catalogue["customer"], catalogue["recliner"].id, 1)


def test_6_quantity_above_availability_is_rejected(catalogue):
    """Only 2 Gold seats left, so a request for 3 must fail with a clear message."""
    gold = catalogue["gold"]
    gold.available_seats = 2
    db.session.commit()

    with pytest.raises(BookingError, match="Only 2 Gold tickets are available"):
        create_booking(catalogue["customer"], gold.id, 3)

    assert db.session.get(SeatTier, gold.id).available_seats == 2


def test_7_zero_quantity_is_rejected(catalogue):
    with pytest.raises(BookingError, match="at least one ticket"):
        create_booking(catalogue["customer"], catalogue["gold"].id, 0)


def test_negative_quantity_is_rejected(catalogue):
    with pytest.raises(BookingError):
        create_booking(catalogue["customer"], catalogue["gold"].id, -1)


def test_invalid_tier_is_rejected(catalogue):
    with pytest.raises(BookingError, match="Invalid ticket tier"):
        create_booking(catalogue["customer"], 99999, 1)


def test_inactive_membership_is_rejected(catalogue):
    with pytest.raises(BookingError, match="Invalid membership"):
        create_booking(
            catalogue["customer"], catalogue["gold"].id, 1,
            membership_id=catalogue["inactive_membership"].id,
        )


def test_availability_drops_by_quantity(catalogue):
    gold = catalogue["gold"]
    before = gold.available_seats

    create_booking(catalogue["customer"], gold.id, 2)

    assert db.session.get(SeatTier, gold.id).available_seats == before - 2


def test_failed_booking_leaves_availability_untouched(catalogue):
    gold = catalogue["gold"]
    before = gold.available_seats

    with pytest.raises(BookingError):
        create_booking(catalogue["customer"], gold.id, before + 5)

    assert db.session.get(SeatTier, gold.id).available_seats == before


def test_overselling_the_last_seat_is_impossible(catalogue):
    """Two bookings for one remaining seat: the second must fail."""
    gold = catalogue["gold"]
    gold.available_seats = 1
    db.session.commit()

    create_booking(catalogue["customer"], gold.id, 1)

    with pytest.raises(BookingError):
        create_booking(catalogue["customer"], gold.id, 1)

    assert db.session.get(SeatTier, gold.id).available_seats == 0
    assert Booking.query.count() == 1


def test_price_change_after_booking_does_not_alter_the_invoice(catalogue):
    """Gold goes 250 -> 300 and the stored snapshot stays at 250.00."""
    gold = catalogue["gold"]
    booking = create_booking(
        catalogue["customer"], gold.id, 3, membership_id=catalogue["membership"].id
    )

    gold.price = Decimal("300.00")
    db.session.commit()

    stored = db.session.get(Booking, booking.id)
    assert stored.item.ticket_price_at_booking == Decimal("250.00")
    assert stored.item.final_amount == Decimal("778.80")
    assert stored.total_amount == Decimal("778.80")


def test_booking_references_are_unique(catalogue):
    first = create_booking(catalogue["customer"], catalogue["silver"].id, 1)
    second = create_booking(catalogue["customer"], catalogue["silver"].id, 1)
    assert first.booking_id != second.booking_id


def test_booking_without_membership_skips_the_member_discount(catalogue):
    booking = create_booking(catalogue["customer"], catalogue["gold"].id, 3)
    assert booking.item.member_discount == Decimal("0.00")
    # 750 - 100 festival + 60 fee = 710 taxable, +18% GST = 837.80
    assert booking.total_amount == Decimal("837.80")


def test_inactive_show_cannot_be_booked(catalogue):
    catalogue["show"].status = "INACTIVE"
    db.session.commit()
    with pytest.raises(BookingError, match="no longer available"):
        create_booking(catalogue["customer"], catalogue["gold"].id, 1)
