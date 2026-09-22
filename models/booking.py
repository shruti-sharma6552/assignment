from datetime import datetime
from decimal import Decimal

from models import db


class BookingStatus:
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.String(40), nullable=False, unique=True, index=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    show_id = db.Column(
        db.Integer, db.ForeignKey("shows.id"), nullable=False, index=True
    )
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    status = db.Column(
        db.String(20), nullable=False, default=BookingStatus.CONFIRMED, index=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User", back_populates="bookings")
    show = db.relationship("Show", back_populates="bookings")
    items = db.relationship(
        "BookingItem", back_populates="booking", cascade="all, delete-orphan"
    )
    invoice = db.relationship(
        "Invoice", back_populates="booking", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def item(self) -> "BookingItem | None":
        """CinePrice books one tier per booking, so the first item is the item."""
        return self.items[0] if self.items else None

    def __repr__(self) -> str:
        return f"<Booking {self.booking_id} {self.total_amount}>"


class BookingItem(db.Model):
    """Frozen snapshot of every pricing value used at booking time."""

    __tablename__ = "booking_items"

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(
        db.Integer, db.ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    seat_tier_id = db.Column(
        db.Integer, db.ForeignKey("seat_tiers.id"), nullable=True
    )
    seat_tier = db.Column(db.String(60), nullable=False)
    ticket_price_at_booking = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    booked_seats = db.Column(db.Text, nullable=True)
    base_amount = db.Column(db.Numeric(12, 2), nullable=False)
    festival_discount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    member_discount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discounted_amount = db.Column(db.Numeric(12, 2), nullable=False)
    convenience_fee = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    taxable_amount = db.Column(db.Numeric(12, 2), nullable=False)
    gst_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    gst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    final_amount = db.Column(db.Numeric(12, 2), nullable=False)
    membership_name = db.Column(db.String(90), nullable=True)
    festival_name = db.Column(db.String(120), nullable=True)

    booking = db.relationship("Booking", back_populates="items")

    def __repr__(self) -> str:
        return f"<BookingItem {self.seat_tier} x{self.quantity}>"
