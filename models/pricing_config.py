from datetime import datetime
from decimal import Decimal

from models import db


class PricingConfig(db.Model):
    """Single row holding the counter-wide fee and tax configuration."""

    __tablename__ = "pricing_config"

    id = db.Column(db.Integer, primary_key=True)
    convenience_fee = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    gst_rate = db.Column(db.Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @classmethod
    def get_current(cls) -> "PricingConfig":
        config = cls.query.order_by(cls.id.asc()).first()
        if config is None:
            config = cls(convenience_fee=Decimal("0.00"), gst_rate=Decimal("0.00"))
            db.session.add(config)
            db.session.commit()
        return config

    def __repr__(self) -> str:
        return f"<PricingConfig fee={self.convenience_fee} gst={self.gst_rate}>"
