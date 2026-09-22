"""SQLAlchemy models package.

`db` is created here and imported by every model module so that all tables
register on a single metadata object.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.membership import Membership  # noqa: E402,F401
from models.user import User, Role  # noqa: E402,F401
from models.cinema import Cinema  # noqa: E402,F401
from models.movie import Movie  # noqa: E402,F401
from models.show import Show  # noqa: E402,F401
from models.seat_tier import SeatTier  # noqa: E402,F401
from models.discount import Discount  # noqa: E402,F401
from models.pricing_config import PricingConfig  # noqa: E402,F401
from models.booking import Booking, BookingItem, BookingStatus  # noqa: E402,F401
from models.invoice import Invoice  # noqa: E402,F401

__all__ = [
    "db", "User", "Role", "Cinema", "Movie", "Show", "SeatTier",
    "Membership", "Discount", "PricingConfig", "Booking", "BookingItem",
    "BookingStatus", "Invoice",
]
