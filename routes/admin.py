"""Admin console: dashboard, catalogue management, pricing config, reports."""

import os
import re
import uuid
from collections import OrderedDict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, url_for
)
from sqlalchemy import func
from werkzeug.utils import secure_filename

from models import (
    Booking, BookingItem, Cinema, Discount, Membership, Movie, PricingConfig,
    SeatTier, Show, db
)
from routes import admin_required
from services.pricing_service import money

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

DEFAULT_TIERS = ("Silver", "Gold", "Recliner")
AVAILABLE_TIERS = ("Normal", "Silver", "Gold", "Diamond", "Platinum", "Recliner")

POSTER_UPLOAD_SUBDIR = os.path.join("images", "posters")
ALLOWED_POSTER_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_POSTER_BYTES = 4 * 1024 * 1024  # 4 MB


# --------------------------------------------------------------------------
# small parsing helpers
# --------------------------------------------------------------------------
def parse_decimal(raw, field, minimum=Decimal("0"), maximum=None) -> Decimal:
    try:
        value = money(Decimal(str(raw).strip()))
    except (InvalidOperation, ValueError, AttributeError, TypeError):
        raise ValueError(f"{field} must be a number.")
    if value < minimum:
        raise ValueError(f"{field} cannot be less than {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field} cannot be more than {maximum}.")
    return value


def parse_int(raw, field, minimum=0) -> int:
    try:
        value = int(str(raw).strip())
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"{field} must be a whole number.")
    if value < minimum:
        raise ValueError(f"{field} cannot be less than {minimum}.")
    return value


def parse_date(raw, field) -> date:
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"{field} must be a valid date.")


def parse_time(raw, field) -> time:
    raw = str(raw).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"{field} must be a valid time.")


# --------------------------------------------------------------------------
# movie poster uploads
# --------------------------------------------------------------------------
def _poster_upload_dir() -> str:
    upload_dir = os.path.join(current_app.static_folder, POSTER_UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def save_poster_upload(file_storage) -> str:
    """Validate and save an uploaded poster image. Returns its stored filename.

    Raises ValueError with a user-facing message on anything invalid.
    """
    filename = secure_filename(file_storage.filename or "")
    if not filename or "." not in filename:
        raise ValueError("Choose a valid image file for the poster.")

    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_POSTER_EXTENSIONS:
        raise ValueError("Poster images must be JPG, PNG or WEBP.")

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_POSTER_BYTES:
        raise ValueError("Poster image must be smaller than 4 MB.")
    if size == 0:
        raise ValueError("The selected poster file is empty.")

    stored_name = f"{uuid.uuid4().hex}.{extension}"
    file_storage.save(os.path.join(_poster_upload_dir(), stored_name))
    return stored_name


def delete_poster_file(stored_name) -> None:
    """Remove a previously uploaded poster from disk, if it exists."""
    if not stored_name:
        return
    path = os.path.join(_poster_upload_dir(), stored_name)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            current_app.logger.warning("Could not remove poster file %s", path)


# --------------------------------------------------------------------------
# dashboard
# --------------------------------------------------------------------------
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    today = date.today()

    total_revenue = db.session.query(func.coalesce(func.sum(Booking.total_amount), 0)).scalar()
    today_revenue = (
        db.session.query(func.coalesce(func.sum(Booking.total_amount), 0))
        .filter(func.date(Booking.created_at) == today)
        .scalar()
    )
    tickets_sold = db.session.query(func.coalesce(func.sum(BookingItem.quantity), 0)).scalar()

    stats = {
        "cinemas": Cinema.query.count(),
        "movies": Movie.query.count(),
        "shows": Show.query.count(),
        "bookings": Booking.query.count(),
        "tickets": int(tickets_sold or 0),
        "revenue": money(total_revenue or 0),
        "today_revenue": money(today_revenue or 0),
    }

    # Revenue for the last 7 days
    revenue_labels, revenue_values = [], []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        amount = (
            db.session.query(func.coalesce(func.sum(Booking.total_amount), 0))
            .filter(func.date(Booking.created_at) == day)
            .scalar()
        )
        revenue_labels.append(day.strftime("%d %b"))
        revenue_values.append(float(money(amount or 0)))

    tier_rows = (
        db.session.query(BookingItem.seat_tier, func.sum(BookingItem.quantity))
        .group_by(BookingItem.seat_tier)
        .all()
    )
    movie_rows = (
        db.session.query(Movie.title, func.count(Booking.id))
        .join(Show, Show.movie_id == Movie.id)
        .join(Booking, Booking.show_id == Show.id)
        .group_by(Movie.title)
        .order_by(func.count(Booking.id).desc())
        .limit(6)
        .all()
    )

    occupancy_labels, occupancy_values = [], []
    for show in Show.query.order_by(Show.show_date.desc()).limit(6).all():
        total = sum(t.total_seats for t in show.seat_tiers)
        sold = sum(t.seats_sold for t in show.seat_tiers)
        occupancy_labels.append(f"{show.movie.title[:14]} {show.start_time.strftime('%H:%M')}")
        occupancy_values.append(round(sold * 100 / total, 1) if total else 0)

    charts = {
        "revenue_labels": revenue_labels,
        "revenue_values": revenue_values,
        "tier_labels": [r[0] for r in tier_rows],
        "tier_values": [int(r[1] or 0) for r in tier_rows],
        "movie_labels": [r[0] for r in movie_rows],
        "movie_values": [int(r[1] or 0) for r in movie_rows],
        "occupancy_labels": occupancy_labels,
        "occupancy_values": occupancy_values,
    }

    recent = Booking.query.order_by(Booking.created_at.desc()).limit(8).all()
    return render_template("admin/dashboard.html", stats=stats, charts=charts, recent=recent)


# --------------------------------------------------------------------------
# cinemas
# --------------------------------------------------------------------------
@admin_bp.route("/cinemas")
@admin_required
def cinemas():
    return render_template(
        "admin/cinemas.html",
        cinemas=Cinema.query.order_by(Cinema.name).all(),
    )


@admin_bp.route("/cinemas/add", methods=["GET", "POST"])
@admin_required
def add_cinema():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        city = (request.form.get("city") or "").strip()
        if not name or not city:
            flash("Cinema name and city are required.", "danger")
            return redirect(url_for("admin.add_cinema"))

        cinema = Cinema(
            name=name,
            city=city,
            location=(request.form.get("location") or city).strip(),
            address=(request.form.get("address") or "").strip(),
            screen_direction=request.form.get("screen_direction") or "top",
            normal_seats=parse_int(request.form.get("normal_seats") or 0, "Normal seats"),
            normal_row_length=parse_int(request.form.get("normal_row_length") or 15, "Normal row length"),
            silver_seats=parse_int(request.form.get("silver_seats") or 0, "Silver seats"),
            silver_row_length=parse_int(request.form.get("silver_row_length") or 15, "Silver row length"),
            gold_seats=parse_int(request.form.get("gold_seats") or 0, "Gold seats"),
            gold_row_length=parse_int(request.form.get("gold_row_length") or 15, "Gold row length"),
            diamond_seats=parse_int(request.form.get("diamond_seats") or 0, "Diamond seats"),
            diamond_row_length=parse_int(request.form.get("diamond_row_length") or 15, "Diamond row length"),
            platinum_seats=parse_int(request.form.get("platinum_seats") or 0, "Platinum seats"),
            platinum_row_length=parse_int(request.form.get("platinum_row_length") or 15, "Platinum row length"),
            recliner_seats=parse_int(request.form.get("recliner_seats") or 0, "Recliner seats"),
            recliner_row_length=parse_int(request.form.get("recliner_row_length") or 15, "Recliner row length"),
            status=request.form.get("status") or "ACTIVE",
        )
        db.session.add(cinema)
        db.session.commit()
        flash(f"{cinema.name} added.", "success")
        return redirect(url_for("admin.cinemas"))

    return render_template("admin/cinema_form.html", cinema=None)


@admin_bp.route("/cinemas/<int:cinema_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_cinema(cinema_id):
    cinema = db.session.get(Cinema, cinema_id) or abort(404)
    if request.method == "POST":
        cinema.name = (request.form.get("name") or cinema.name).strip()
        cinema.city = (request.form.get("city") or cinema.city).strip()
        cinema.location = (request.form.get("location") or cinema.location).strip()
        cinema.address = (request.form.get("address") or "").strip()
        cinema.screen_direction = request.form.get("screen_direction") or cinema.screen_direction
        cinema.normal_seats = parse_int(request.form.get("normal_seats") or 0, "Normal seats")
        cinema.normal_row_length = parse_int(request.form.get("normal_row_length") or 15, "Normal row length")
        cinema.silver_seats = parse_int(request.form.get("silver_seats") or 0, "Silver seats")
        cinema.silver_row_length = parse_int(request.form.get("silver_row_length") or 15, "Silver row length")
        cinema.gold_seats = parse_int(request.form.get("gold_seats") or 0, "Gold seats")
        cinema.gold_row_length = parse_int(request.form.get("gold_row_length") or 15, "Gold row length")
        cinema.diamond_seats = parse_int(request.form.get("diamond_seats") or 0, "Diamond seats")
        cinema.diamond_row_length = parse_int(request.form.get("diamond_row_length") or 15, "Diamond row length")
        cinema.platinum_seats = parse_int(request.form.get("platinum_seats") or 0, "Platinum seats")
        cinema.platinum_row_length = parse_int(request.form.get("platinum_row_length") or 15, "Platinum row length")
        cinema.recliner_seats = parse_int(request.form.get("recliner_seats") or 0, "Recliner seats")
        cinema.recliner_row_length = parse_int(request.form.get("recliner_row_length") or 15, "Recliner row length")
        cinema.status = request.form.get("status") or cinema.status
        db.session.commit()
        flash(f"{cinema.name} updated.", "success")
        return redirect(url_for("admin.cinemas"))

    return render_template("admin/cinema_form.html", cinema=cinema)


@admin_bp.route("/cinemas/<int:cinema_id>/delete", methods=["POST"])
@admin_required
def delete_cinema(cinema_id):
    cinema = db.session.get(Cinema, cinema_id) or abort(404)
    has_bookings = (
        Booking.query.join(Show, Booking.show_id == Show.id)
        .filter(Show.cinema_id == cinema.id)
        .first()
    )
    if has_bookings:
        cinema.status = "INACTIVE"
        flash(f"{cinema.name} has bookings, so it was deactivated instead of deleted.", "info")
    else:
        db.session.delete(cinema)
        flash(f"{cinema.name} deleted.", "success")
    db.session.commit()
    return redirect(url_for("admin.cinemas"))


@admin_bp.route("/api/cinema/<int:cinema_id>/tiers")
@admin_required
def api_cinema_tiers(cinema_id):
    cinema = db.session.get(Cinema, cinema_id)
    if not cinema:
        return {"tiers": []}, 404
        
    tiers = []
    for t in AVAILABLE_TIERS:
        seats = getattr(cinema, f"{t.lower()}_seats", 0)
        if seats > 0:
            tiers.append({"name": t, "seats": seats})
            
    return {"tiers": tiers}


# --------------------------------------------------------------------------
# movies
# --------------------------------------------------------------------------
@admin_bp.route("/movies")
@admin_required
def movies():
    return render_template("admin/movies.html", movies=Movie.query.order_by(Movie.title).all())


def _movie_from_form(movie: Movie) -> Movie:
    movie.title = (request.form.get("title") or "").strip()
    movie.description = (request.form.get("description") or "").strip()
    movie.duration = parse_int(request.form.get("duration") or 120, "Duration", minimum=1)
    movie.language = (request.form.get("language") or "English").strip()
    movie.genre = (request.form.get("genre") or "").strip()
    movie.certificate = (request.form.get("certificate") or "").strip()
    movie.status = request.form.get("status") or "ACTIVE"

    # A newly uploaded file always wins. Otherwise "remove poster" clears it.
    # Leaving both alone keeps whatever poster the movie already had.
    poster_file = request.files.get("poster_file")
    if poster_file is not None and poster_file.filename:
        new_poster = save_poster_upload(poster_file)
        old_poster = movie.poster
        movie.poster = new_poster
        delete_poster_file(old_poster)
    elif request.form.get("remove_poster") == "on":
        delete_poster_file(movie.poster)
        movie.poster = None

    return movie


@admin_bp.route("/movies/add", methods=["GET", "POST"])
@admin_required
def add_movie():
    if request.method == "POST":
        try:
            movie = _movie_from_form(Movie())
            if not movie.title:
                raise ValueError("Movie title is required.")
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.add_movie"))

        db.session.add(movie)
        db.session.commit()
        flash(f"{movie.title} added.", "success")
        return redirect(url_for("admin.movies"))

    return render_template("admin/movie_form.html", movie=None)


@admin_bp.route("/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_movie(movie_id):
    movie = db.session.get(Movie, movie_id) or abort(404)
    if request.method == "POST":
        try:
            _movie_from_form(movie)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.edit_movie", movie_id=movie_id))
        db.session.commit()
        flash(f"{movie.title} updated.", "success")
        return redirect(url_for("admin.movies"))

    return render_template("admin/movie_form.html", movie=movie)


@admin_bp.route("/movies/<int:movie_id>/delete", methods=["POST"])
@admin_required
def delete_movie(movie_id):
    movie = db.session.get(Movie, movie_id) or abort(404)
    has_bookings = (
        Booking.query.join(Show, Booking.show_id == Show.id)
        .filter(Show.movie_id == movie.id)
        .first()
    )
    if has_bookings:
        movie.status = "INACTIVE"
        flash(f"{movie.title} has bookings, so it was deactivated instead of deleted.", "info")
    else:
        delete_poster_file(movie.poster)
        db.session.delete(movie)
        flash(f"{movie.title} deleted.", "success")
    db.session.commit()
    return redirect(url_for("admin.movies"))


# --------------------------------------------------------------------------
# shows
# --------------------------------------------------------------------------
@admin_bp.route("/shows")
@admin_required
def shows():
    show_list = Show.query.order_by(Show.show_date.desc(), Show.start_time).all()
    return render_template("admin/shows.html", shows=show_list)


@admin_bp.route("/shows/add", methods=["GET", "POST"])
@admin_required
def add_show():
    movies_list = Movie.query.order_by(Movie.title).all()
    cinemas_list = Cinema.query.order_by(Cinema.name).all()

    if request.method == "POST":
        try:
            movie_id = parse_int(request.form.get("movie_id"), "Movie", minimum=1)
            cinema_id = parse_int(request.form.get("cinema_id"), "Cinema", minimum=1)
            show_date = parse_date(request.form.get("show_date"), "Show date")
            start = parse_time(request.form.get("start_time"), "Start time")
            end_raw = (request.form.get("end_time") or "").strip()
            end = parse_time(end_raw, "End time") if end_raw else None

            show = Show(
                movie_id=movie_id,
                cinema_id=cinema_id,
                show_date=show_date,
                start_time=start,
                end_time=end,
                status=request.form.get("status") or "ACTIVE",
            )
            db.session.add(show)
            db.session.flush()

            cinema = db.session.get(Cinema, cinema_id)
            if not cinema:
                raise ValueError("Selected cinema does not exist.")

            # Generate SeatTiers based on cinema's capacities and submitted prices.
            added_tiers = []
            for tier_name in AVAILABLE_TIERS:
                seats = getattr(cinema, f"{tier_name.lower()}_seats", 0)
                if seats > 0:
                    price_str = request.form.get(f"price_{tier_name.lower()}")
                    if price_str is None:
                        raise ValueError(f"Price for {tier_name} is required.")
                    price = parse_decimal(price_str, f"{tier_name} price")
                    db.session.add(
                        SeatTier(
                            show_id=show.id, name=tier_name, price=price,
                            total_seats=seats, available_seats=seats,
                            status="ACTIVE",
                        )
                    )
                    added_tiers.append(tier_name)
            
            if not added_tiers:
                raise ValueError("Selected cinema has no configured seats for any tier. Please configure the cinema's seats first.")

            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("admin.add_show"))

        flash(f"Show created with tiers: {', '.join(added_tiers)}.", "success")
        return redirect(url_for("admin.shows"))

    return render_template(
        "admin/show_form.html", show=None, movies=movies_list,
        cinemas=cinemas_list, tiers=DEFAULT_TIERS,
    )


@admin_bp.route("/shows/<int:show_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_show(show_id):
    show = db.session.get(Show, show_id) or abort(404)
    if request.method == "POST":
        try:
            show.movie_id = parse_int(request.form.get("movie_id"), "Movie", minimum=1)
            show.cinema_id = parse_int(request.form.get("cinema_id"), "Cinema", minimum=1)
            show.show_date = parse_date(request.form.get("show_date"), "Show date")
            show.start_time = parse_time(request.form.get("start_time"), "Start time")
            end_raw = (request.form.get("end_time") or "").strip()
            show.end_time = parse_time(end_raw, "End time") if end_raw else None
            show.status = request.form.get("status") or show.status
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("admin.edit_show", show_id=show_id))

        flash("Show updated.", "success")
        return redirect(url_for("admin.shows"))

    return render_template(
        "admin/show_form.html",
        show=show,
        movies=Movie.query.order_by(Movie.title).all(),
        cinemas=Cinema.query.order_by(Cinema.name).all(),
        tiers=DEFAULT_TIERS,
    )


@admin_bp.route("/shows/<int:show_id>/delete", methods=["POST"])
@admin_required
def delete_show(show_id):
    show = db.session.get(Show, show_id) or abort(404)
    if Booking.query.filter_by(show_id=show.id).first():
        show.status = "INACTIVE"
        flash("This show has bookings, so it was deactivated instead of deleted.", "info")
    else:
        db.session.delete(show)
        flash("Show deleted.", "success")
    db.session.commit()
    return redirect(url_for("admin.shows"))


# --------------------------------------------------------------------------
# ticket pricing, availability, fees and tax
# --------------------------------------------------------------------------
@admin_bp.route("/pricing", methods=["GET", "POST"])
@admin_required
def pricing():
    config = PricingConfig.get_current()

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "config":
                config.convenience_fee = parse_decimal(
                    request.form.get("convenience_fee"), "Convenience fee"
                )
                config.gst_rate = parse_decimal(
                    request.form.get("gst_rate"), "GST rate", maximum=Decimal("100")
                )
                db.session.commit()
                flash("Convenience fee and GST updated.", "success")
            elif action == "tier":
                tier = db.session.get(
                    SeatTier, parse_int(request.form.get("tier_id"), "Tier", minimum=1)
                ) or abort(404)
                tier.price = parse_decimal(request.form.get("price"), "Price")
                total = parse_int(request.form.get("total_seats"), "Total seats")
                available = parse_int(request.form.get("available_seats"), "Available seats")
                if available > total:
                    raise ValueError("Available seats cannot exceed total seats.")
                tier.total_seats = total
                tier.available_seats = available
                tier.status = request.form.get("status") or "ACTIVE"
                db.session.commit()
                flash(f"{tier.name} pricing updated.", "success")
            elif action == "import_tiers":
                show_id = parse_int(request.form.get("show_id"), "Show ID", minimum=1)
                show = db.session.get(Show, show_id) or abort(404)
                csv_data = request.form.get("csv_data") or ""
                
                imported_count = 0
                dedup_count = 0
                rejected_count = 0
                imported_names = []
                
                parsed_tiers = {}
                
                for original_line in csv_data.splitlines():
                    line = original_line.strip()
                    if not line:
                        continue
                        
                    parts = line.split(",", 1)
                    if len(parts) != 2:
                        rejected_count += 1
                        continue
                        
                    name_raw, price_raw = parts
                    name = name_raw.strip()
                    if not name:
                        rejected_count += 1
                        continue
                        
                    match = re.search(r'-?\d+(\.\d+)?', price_raw)
                    if not match:
                        rejected_count += 1
                        continue
                        
                    try:
                        price = parse_decimal(match.group(), "Price")
                    except ValueError:
                        rejected_count += 1
                        continue
                    
                    if price < Decimal("0"):
                        rejected_count += 1
                        continue
                        
                    normalized_name = name.lower()
                    if normalized_name in parsed_tiers:
                        dedup_count += 1
                    else:
                        parsed_tiers[normalized_name] = (name.title(), price)
                        
                existing_tiers = {t.name.lower(): t for t in show.seat_tiers}
                for norm_name, (title_name, price) in parsed_tiers.items():
                    if norm_name in existing_tiers:
                        tier = existing_tiers[norm_name]
                        tier.price = price
                    else:
                        tier = SeatTier(
                            show_id=show.id,
                            name=title_name,
                            price=price,
                            total_seats=50,
                            available_seats=50,
                            status="ACTIVE"
                        )
                        db.session.add(tier)
                    imported_count += 1
                    imported_names.append(title_name)
                    
                db.session.commit()
                
                msg_parts = [f"Imported/Updated {imported_count} tiers ({', '.join(imported_names)})."]
                if dedup_count > 0:
                    msg_parts.append(f"De-duplicated {dedup_count} entries.")
                if rejected_count > 0:
                    msg_parts.append(f"Rejected {rejected_count} entries.")
                    
                flash(" ".join(msg_parts), "success" if rejected_count == 0 else "warning")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin.pricing", show_id=request.form.get("show_id") or None))

    show_list = Show.query.order_by(Show.show_date.desc(), Show.start_time).all()
    selected_id = request.args.get("show_id", type=int)
    selected = db.session.get(Show, selected_id) if selected_id else (show_list[0] if show_list else None)
    return render_template(
        "admin/pricing.html", config=config, shows=show_list, selected=selected
    )


# --------------------------------------------------------------------------
# festival discounts
# --------------------------------------------------------------------------
@admin_bp.route("/discounts", methods=["GET", "POST"])
@admin_required
def discounts():
    if request.method == "POST":
        try:
            discount_id = request.form.get("discount_id")
            discount = (
                db.session.get(Discount, int(discount_id)) if discount_id else Discount()
            )
            if discount is None:
                abort(404)
            discount.name = (request.form.get("name") or "").strip()
            if not discount.name:
                raise ValueError("Festival name is required.")
            discount.amount = parse_decimal(request.form.get("amount"), "Discount amount")
            discount.start_date = parse_date(request.form.get("start_date"), "Start date")
            discount.end_date = parse_date(request.form.get("end_date"), "End date")
            if discount.end_date < discount.start_date:
                raise ValueError("End date cannot be before the start date.")
            discount.active = request.form.get("active") == "on"
            db.session.add(discount)
            db.session.commit()
            flash(f"{discount.name} saved.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin.discounts"))

    return render_template(
        "admin/discounts.html",
        discounts=Discount.query.order_by(Discount.start_date.desc()).all(),
        today=date.today(),
    )


@admin_bp.route("/discounts/<int:discount_id>/delete", methods=["POST"])
@admin_required
def delete_discount(discount_id):
    discount = db.session.get(Discount, discount_id) or abort(404)
    db.session.delete(discount)
    db.session.commit()
    flash("Festival offer removed.", "success")
    return redirect(url_for("admin.discounts"))


# --------------------------------------------------------------------------
# memberships
# --------------------------------------------------------------------------
@admin_bp.route("/memberships", methods=["GET", "POST"])
@admin_required
def memberships():
    if request.method == "POST":
        try:
            membership_id = request.form.get("membership_id")
            membership = (
                db.session.get(Membership, int(membership_id))
                if membership_id else Membership()
            )
            if membership is None:
                abort(404)
            membership.name = (request.form.get("name") or "").strip()
            if not membership.name:
                raise ValueError("Membership name is required.")
            membership.discount_percentage = parse_decimal(
                request.form.get("discount_percentage"),
                "Discount percentage",
                maximum=Decimal("100"),
            )
            membership.discount_cap = parse_decimal(
                request.form.get("discount_cap"), "Maximum discount"
            )
            membership.active = request.form.get("active") == "on"
            db.session.add(membership)
            db.session.commit()
            flash(f"{membership.name} saved.", "success")
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("admin.memberships"))

    return render_template(
        "admin/memberships.html",
        memberships=Membership.query.order_by(Membership.id).all(),
    )


# --------------------------------------------------------------------------
# bookings and reports
# --------------------------------------------------------------------------
@admin_bp.route("/bookings")
@admin_required
def bookings():
    query = Booking.query.order_by(Booking.created_at.desc())
    reference = (request.args.get("q") or "").strip()
    if reference:
        query = query.filter(Booking.booking_id.ilike(f"%{reference}%"))
    return render_template("admin/bookings.html", bookings=query.all(), search=reference)


@admin_bp.route("/reports")
@admin_required
def reports():
    # Revenue by date
    revenue_rows = (
        db.session.query(
            func.date(Booking.created_at).label("day"),
            func.count(func.distinct(Booking.id)),
            func.coalesce(func.sum(BookingItem.quantity), 0),
            func.coalesce(func.sum(BookingItem.final_amount), 0),
            func.coalesce(func.sum(BookingItem.gst_amount), 0),
        )
        .join(BookingItem, BookingItem.booking_id == Booking.id)
        .group_by(func.date(Booking.created_at))
        .order_by(func.date(Booking.created_at).desc())
        .all()
    )
    revenue_report = [
        {
            "day": row[0],
            "bookings": int(row[1]),
            "tickets": int(row[2] or 0),
            "revenue": money(row[3] or 0),
            "gst": money(row[4] or 0),
        }
        for row in revenue_rows
    ]

    # Tier report
    tier_rows = (
        db.session.query(
            BookingItem.seat_tier,
            func.coalesce(func.sum(BookingItem.quantity), 0),
            func.coalesce(func.sum(BookingItem.final_amount), 0),
        )
        .group_by(BookingItem.seat_tier)
        .all()
    )
    remaining = OrderedDict()
    for tier in SeatTier.query.all():
        remaining[tier.name] = remaining.get(tier.name, 0) + tier.available_seats

    tier_report = [
        {
            "tier": row[0],
            "tickets": int(row[1] or 0),
            "revenue": money(row[2] or 0),
            "remaining": remaining.get(row[0], 0),
        }
        for row in tier_rows
    ]
    for name, seats in remaining.items():
        if not any(r["tier"] == name for r in tier_report):
            tier_report.append(
                {"tier": name, "tickets": 0, "revenue": money(0), "remaining": seats}
            )

    # Movie report
    movie_rows = (
        db.session.query(
            Movie.title,
            func.count(func.distinct(Booking.id)),
            func.coalesce(func.sum(BookingItem.quantity), 0),
            func.coalesce(func.sum(BookingItem.final_amount), 0),
        )
        .join(Show, Show.movie_id == Movie.id)
        .join(Booking, Booking.show_id == Show.id)
        .join(BookingItem, BookingItem.booking_id == Booking.id)
        .group_by(Movie.title)
        .order_by(func.coalesce(func.sum(BookingItem.final_amount), 0).desc())
        .all()
    )
    movie_report = [
        {
            "movie": row[0],
            "bookings": int(row[1]),
            "tickets": int(row[2] or 0),
            "revenue": money(row[3] or 0),
        }
        for row in movie_rows
    ]

    return render_template(
        "admin/reports.html",
        revenue_report=revenue_report,
        tier_report=tier_report,
        movie_report=movie_report,
    )