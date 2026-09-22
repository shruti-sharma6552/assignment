from datetime import datetime
from decimal import Decimal

from models import db


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(40), nullable=False, unique=True, index=True)
    booking_id = db.Column(
        db.Integer, db.ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    gst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    booking = db.relationship("Booking", back_populates="invoice")

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number}>"
