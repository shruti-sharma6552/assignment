"""CinePrice application entry point.

Run locally with:  python app.py
Then open:         http://127.0.0.1:5000
"""

from datetime import date, time, timedelta
from decimal import Decimal

from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from models import (
    Cinema, Discount, Membership, Movie, PricingConfig, Role, SeatTier, Show,
    User, db
)
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.booking import booking_bp
from routes.customer import customer_bp

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Sign in to continue."
    login_manager.login_message_category = "info"

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp)

    register_error_handlers(app)

    if app.config.get("AUTO_INIT_DB"):
        with app.app_context():
            initialize_database()

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------
# error handling -- customers never see a stack trace
# --------------------------------------------------------------------------
def register_error_handlers(app: Flask) -> None:
    def render_error(code, heading, message):
        return render_template(
            "error.html", code=code, heading=heading, message=message
        ), code

    @app.errorhandler(401)
    def unauthorized(_error):
        return render_error(401, "Sign in required", "Sign in to view this page.")

    @app.errorhandler(403)
    def forbidden(_error):
        return render_error(
            403, "Not your page", "This area is restricted to cinema staff."
        )

    @app.errorhandler(413)
    def too_large(_error):
        return render_error(
            413, "File too large", "That poster image is too large. Please use a file under 4 MB."
        )

    @app.errorhandler(404)
    def not_found(_error):
        return render_error(
            404, "Page not found", "That page, show or movie is not available."
        )

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        return render_error(
            400, "Form expired", "Your form session expired. Please try again."
        )

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database error: %s", error)
        return render_error(
            500, "Something went wrong", "Please try that again in a moment."
        )

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Server error: %s", error)
        return render_error(
            500, "Something went wrong", "Please try that again in a moment."
        )


# --------------------------------------------------------------------------
# database initialization and demo data
# --------------------------------------------------------------------------
def initialize_database() -> None:
    """Create tables and, on an empty database, load the demo catalogue."""
    db.create_all()
    if User.query.first() is None:
        seed_sample_data()


def seed_sample_data() -> None:
    """Load a working demo catalogue. Safe to skip on a populated database."""
    memberships = [
        Membership(name="Silver Member", discount_percentage=Decimal("5.00"),
                   discount_cap=Decimal("30.00"), active=True),
        Membership(name="Gold Member", discount_percentage=Decimal("10.00"),
                   discount_cap=Decimal("50.00"), active=True),
        Membership(name="Premium Member", discount_percentage=Decimal("15.00"),
                   discount_cap=Decimal("100.00"), active=True),
    ]
    db.session.add_all(memberships)
    db.session.flush()

    admin = User(name="Cinema Admin", email="admin@cineprice.com", role=Role.ADMIN)
    admin.set_password("admin123")

    customer = User(
        name="Shruti", email="customer@cineprice.com",
        role=Role.CUSTOMER, membership_id=memberships[1].id,
    )
    customer.set_password("customer123")
    db.session.add_all([admin, customer])

    cinemas = [
        Cinema(name="Cineplex Jaipur", location="MI Road", city="Jaipur",
               address="12 MI Road, Jaipur", status="ACTIVE"),
        Cinema(name="CineMax Central", location="Central Mall", city="Jaipur",
               address="Central Mall, Tonk Road, Jaipur", status="ACTIVE"),
    ]
    movies = [
        Movie(title="Avengers", description="Earth's mightiest heroes reunite for one last stand.",
              duration=143, language="English", genre="Action", certificate="UA", status="ACTIVE"),
        Movie(title="Inception", description="A thief who steals secrets from dreams takes on one final job.",
              duration=148, language="English", genre="Sci-Fi", certificate="UA", status="ACTIVE"),
        Movie(title="Interstellar", description="A crew travels through a wormhole to find humanity a new home.",
              duration=169, language="English", genre="Sci-Fi", certificate="U", status="ACTIVE"),
    ]
    db.session.add_all(cinemas + movies)
    db.session.flush()

    # Prices come from here once and are editable in the admin panel afterwards.
    tier_prices = {
        "Silver": (Decimal("150.00"), 100),
        "Gold": (Decimal("250.00"), 80),
        "Recliner": (Decimal("450.00"), 30),
    }
    schedule = [
        (movies[0], cinemas[0], 4, time(19, 30), time(21, 53)),
        (movies[0], cinemas[1], 4, time(16, 0), time(18, 23)),
        (movies[1], cinemas[0], 5, time(18, 0), time(20, 28)),
        (movies[2], cinemas[1], 5, time(20, 15), time(23, 4)),
    ]

    for index, (movie, cinema, day_offset, start, end) in enumerate(schedule):
        show = Show(
            movie_id=movie.id, cinema_id=cinema.id,
            show_date=date.today() + timedelta(days=day_offset),
            start_time=start, end_time=end, status="ACTIVE",
        )
        db.session.add(show)
        db.session.flush()

        for name, (price, seats) in tier_prices.items():
            available = seats
            # One tier on the first show is sold out to demonstrate the state.
            if index == 0 and name == "Recliner":
                available = 0
            elif index == 0 and name == "Gold":
                available = 20
            db.session.add(
                SeatTier(show_id=show.id, name=name, price=price,
                         total_seats=seats, available_seats=available, status="ACTIVE")
            )

    db.session.add(
        Discount(
            name="Festival Offer", amount=Decimal("100.00"),
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=180),
            active=True,
        )
    )
    db.session.add(
        PricingConfig(convenience_fee=Decimal("20.00"), gst_rate=Decimal("18.00"))
    )
    db.session.commit()


app = create_app()


@app.cli.command("init-db")
def init_db_command():
    """flask --app app init-db -- create tables and load demo data."""
    initialize_database()
    print("Database ready.")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)