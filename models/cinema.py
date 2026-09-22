from datetime import datetime

from models import db


class Cinema(db.Model):
    __tablename__ = "cinemas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    location = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=False, index=True)
    screen_direction = db.Column(db.String(20), nullable=False, default="top")
    normal_seats = db.Column(db.Integer, nullable=False, default=0)
    normal_row_length = db.Column(db.Integer, nullable=False, default=15)
    silver_seats = db.Column(db.Integer, nullable=False, default=0)
    silver_row_length = db.Column(db.Integer, nullable=False, default=15)
    gold_seats = db.Column(db.Integer, nullable=False, default=0)
    gold_row_length = db.Column(db.Integer, nullable=False, default=15)
    diamond_seats = db.Column(db.Integer, nullable=False, default=0)
    diamond_row_length = db.Column(db.Integer, nullable=False, default=15)
    platinum_seats = db.Column(db.Integer, nullable=False, default=0)
    platinum_row_length = db.Column(db.Integer, nullable=False, default=15)
    recliner_seats = db.Column(db.Integer, nullable=False, default=0)
    recliner_row_length = db.Column(db.Integer, nullable=False, default=15)

    def get_row_length(self, tier_name: str) -> int:
        return getattr(self, f"{tier_name.lower()}_row_length", 15)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    shows = db.relationship("Show", back_populates="cinema", cascade="all, delete-orphan")

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    def __repr__(self) -> str:
        return f"<Cinema {self.name}>"
