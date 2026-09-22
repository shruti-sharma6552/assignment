from decimal import Decimal

from models import db


class Membership(db.Model):
    """Percentage discount with an absolute cap, e.g. Gold: 10% up to Rs.50."""

    __tablename__ = "memberships"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(90), nullable=False, unique=True)
    discount_percentage = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    discount_cap = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    users = db.relationship("User", back_populates="membership")

    def __repr__(self) -> str:
        return f"<Membership {self.name} {self.discount_percentage}%>"
