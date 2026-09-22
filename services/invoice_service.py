"""Booking reference and invoice generation."""

import random
from datetime import datetime

from models import Booking, Invoice, db


def generate_booking_reference() -> str:
    """Return a reference such as CINE-20260916-00125, unique per booking."""
    today = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"CINE-{today}-"
    count = Booking.query.filter(Booking.booking_id.like(prefix + "%")).count()

    for attempt in range(count + 1, count + 60):
        candidate = f"{prefix}{attempt:05d}"
        if not Booking.query.filter_by(booking_id=candidate).first():
            return candidate

    return f"{prefix}{random.randint(10000, 99999)}"


def create_invoice(booking: Booking, breakdown: dict) -> Invoice:
    """Create the invoice row for a booking. Caller commits the transaction."""
    invoice = Invoice(
        invoice_number=booking.booking_id.replace("CINE-", "INV-"),
        booking_id=booking.id,
        total_amount=breakdown["final_amount"],
        gst_amount=breakdown["gst_amount"],
        issued_at=datetime.utcnow(),
    )
    db.session.add(invoice)
    return invoice


def build_invoice_context(booking: Booking) -> dict:
    """Assemble invoice data from the stored snapshot only.

    Nothing here reads the current pricing configuration, so an old invoice
    never changes when the admin edits prices, fees, GST or discounts.
    """
    item = booking.item
    show = booking.show
    return {
        "booking": booking,
        "item": item,
        "show": show,
        "movie": show.movie if show else None,
        "cinema": show.cinema if show else None,
        "customer": booking.user,
        "invoice": booking.invoice,
    }
