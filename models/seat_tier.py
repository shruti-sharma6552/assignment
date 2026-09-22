from decimal import Decimal

from models import db


class SeatTier(db.Model):
    """A bookable ticket tier (Silver / Gold / Recliner) for one show."""

    __tablename__ = "seat_tiers"
    __table_args__ = (
        db.UniqueConstraint("show_id", "name", name="uq_seat_tier_show_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(
        db.Integer, db.ForeignKey("shows.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name = db.Column(db.String(60), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_seats = db.Column(db.Integer, nullable=False, default=0)
    available_seats = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)

    show = db.relationship("Show", back_populates="seat_tiers")

    @property
    def is_sold_out(self) -> bool:
        return self.available_seats <= 0

    @property
    def is_selectable(self) -> bool:
        return self.status == "ACTIVE" and not self.is_sold_out

    @property
    def seats_sold(self) -> int:
        return max(0, self.total_seats - self.available_seats)

    @property
    def occupancy_percent(self) -> float:
        if not self.total_seats:
            return 0.0
        return round(self.seats_sold * 100 / self.total_seats, 1)

    def __repr__(self) -> str:
        return f"<SeatTier {self.name} show={self.show_id}>"
