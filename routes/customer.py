"""Customer browsing: home, movies, cinemas, shows, ticket selection."""

from datetime import date

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from models import Cinema, Membership, Movie, Show, db
from services.pricing_service import active_festival_discount

customer_bp = Blueprint("customer", __name__)


@customer_bp.route("/")
def home():
    movies = Movie.query.filter_by(status="ACTIVE").order_by(Movie.title).all()
    cinemas = Cinema.query.filter_by(status="ACTIVE").order_by(Cinema.name).all()
    festival = active_festival_discount()
    upcoming = (
        Show.query.filter(Show.status == "ACTIVE", Show.show_date >= date.today())
        .order_by(Show.show_date, Show.start_time)
        .limit(6)
        .all()
    )
    return render_template(
        "home.html",
        movies=movies,
        cinemas=cinemas,
        festival=festival,
        upcoming=[s for s in upcoming if s.is_bookable],
    )


@customer_bp.route("/movies")
def movies():
    city = (request.args.get("city") or "").strip()
    query = Movie.query.filter_by(status="ACTIVE")
    search = (request.args.get("q") or "").strip()
    if search:
        query = query.filter(Movie.title.ilike(f"%{search}%"))
    movie_list = query.order_by(Movie.title).all()
    cities = sorted(
        {c.city for c in Cinema.query.filter_by(status="ACTIVE").all() if c.city}
    )
    return render_template(
        "movies.html", movies=movie_list, search=search, cities=cities, city=city
    )


@customer_bp.route("/movie/<int:movie_id>")
def movie_details(movie_id):
    movie = db.session.get(Movie, movie_id)
    if movie is None or not movie.is_active:
        abort(404)

    shows = (
        Show.query.filter(
            Show.movie_id == movie.id,
            Show.status == "ACTIVE",
            Show.show_date >= date.today(),
        )
        .order_by(Show.show_date, Show.start_time)
        .all()
    )
    shows = [s for s in shows if s.is_bookable]

    by_cinema = {}
    for show in shows:
        by_cinema.setdefault(show.cinema, []).append(show)

    return render_template("movie_details.html", movie=movie, by_cinema=by_cinema)


@customer_bp.route("/cinemas")
def cinemas():
    cinema_list = Cinema.query.filter_by(status="ACTIVE").order_by(Cinema.city, Cinema.name).all()
    return render_template("cinemas.html", cinemas=cinema_list)


@customer_bp.route("/shows/<int:cinema_id>")
def shows(cinema_id):
    cinema = db.session.get(Cinema, cinema_id)
    if cinema is None or not cinema.is_active:
        abort(404)

    show_list = (
        Show.query.filter(
            Show.cinema_id == cinema.id,
            Show.status == "ACTIVE",
            Show.show_date >= date.today(),
        )
        .order_by(Show.show_date, Show.start_time)
        .all()
    )
    return render_template(
        "shows.html", cinema=cinema, shows=[s for s in show_list if s.is_bookable]
    )


@customer_bp.route("/ticket-selection/<int:show_id>")
@login_required
def ticket_selection(show_id):
    show = db.session.get(Show, show_id)
    if show is None or not show.is_bookable:
        abort(404)

    from models import PricingConfig, Booking

    booked_seats = []
    bookings = Booking.query.filter_by(show_id=show.id, status="CONFIRMED").all()
    for booking in bookings:
        for item in booking.items:
            if item.booked_seats:
                booked_seats.extend([s.strip() for s in item.booked_seats.split(',') if s.strip()])

    memberships = Membership.query.filter_by(active=True).order_by(Membership.id).all()
    return render_template(
        "ticket_selection.html",
        show=show,
        tiers=show.seat_tiers,
        memberships=memberships,
        festival=active_festival_discount(),
        config=PricingConfig.get_current(),
        default_membership_id=current_user.membership_id,
        booked_seats=booked_seats,
    )
