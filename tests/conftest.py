"""Shared pytest fixtures. Tests run against an in-memory SQLite database."""

import os
import sys
from datetime import date, time, timedelta
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from models import (  # noqa: E402
    Cinema, Discount, Membership, Movie, PricingConfig, Role, SeatTier, Show,
    User, db
)


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def catalogue(app):
    """A single Avengers show with Silver / Gold / sold-out Recliner tiers."""
    gold_member = Membership(
        name="Gold Member", discount_percentage=Decimal("10.00"),
        discount_cap=Decimal("50.00"), active=True,
    )
    inactive_member = Membership(
        name="Lapsed Member", discount_percentage=Decimal("20.00"),
        discount_cap=Decimal("500.00"), active=False,
    )
    db.session.add_all([gold_member, inactive_member])
    db.session.flush()

    customer = User(name="Shruti", email="shruti@example.com", role=Role.CUSTOMER)
    customer.set_password("customer123")

    cinema = Cinema(name="Cineplex Jaipur", location="MI Road", city="Jaipur", status="ACTIVE")
    movie = Movie(title="Avengers", duration=143, language="English", status="ACTIVE")
    db.session.add_all([customer, cinema, movie])
    db.session.flush()

    show = Show(
        movie_id=movie.id, cinema_id=cinema.id,
        show_date=date.today() + timedelta(days=3),
        start_time=time(19, 30), end_time=time(21, 53), status="ACTIVE",
    )
    db.session.add(show)
    db.session.flush()

    silver = SeatTier(show_id=show.id, name="Silver", price=Decimal("150.00"),
                      total_seats=100, available_seats=45, status="ACTIVE")
    gold = SeatTier(show_id=show.id, name="Gold", price=Decimal("250.00"),
                    total_seats=80, available_seats=20, status="ACTIVE")
    recliner = SeatTier(show_id=show.id, name="Recliner", price=Decimal("450.00"),
                        total_seats=30, available_seats=0, status="ACTIVE")
    db.session.add_all([silver, gold, recliner])

    db.session.add(Discount(
        name="Festival Offer", amount=Decimal("100.00"),
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() + timedelta(days=30), active=True,
    ))
    db.session.add(PricingConfig(
        convenience_fee=Decimal("20.00"), gst_rate=Decimal("18.00")
    ))
    db.session.commit()

    return {
        "customer": customer, "show": show, "silver": silver, "gold": gold,
        "recliner": recliner, "membership": gold_member,
        "inactive_membership": inactive_member,
    }
