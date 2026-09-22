from datetime import date
from decimal import Decimal

from models import db


class Discount(db.Model):
    """Flat festival discount applied to the base ticket amount."""

    __tablename__ = "discounts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    def is_valid_on(self, on_date: date | None = None) -> bool:
        on_date = on_date or date.today()
        return bool(self.active) and self.start_date <= on_date <= self.end_date

    def __repr__(self) -> str:
        return f"<Discount {self.name} {self.amount}>"
