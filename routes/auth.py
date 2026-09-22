"""Registration, login and logout."""

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from models import Membership, Role, User, db

auth_bp = Blueprint("auth", __name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


def _landing_page(user):
    return url_for("admin.dashboard") if user.is_admin else url_for("customer.home")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_landing_page(current_user))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("That email and password combination did not match an account.", "danger")
            return render_template("login.html", email=email), 401

        login_user(user)
        flash(f"Welcome back, {user.name}.", "success")
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(_landing_page(user))

    return render_template("login.html", email="")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(_landing_page(current_user))

    memberships = Membership.query.filter_by(active=True).order_by(Membership.id).all()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        membership_id = request.form.get("membership_id") or None

        errors = []
        if len(name) < 2:
            errors.append("Enter your full name.")
        if not EMAIL_PATTERN.match(email):
            errors.append("Enter a valid email address.")
        if len(password) < 6:
            errors.append("Use a password of at least 6 characters.")
        if password != confirm:
            errors.append("The two passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("An account already exists for that email.")
        if membership_id:
            membership = db.session.get(Membership, int(membership_id))
            if membership is None or not membership.active:
                errors.append("Invalid membership.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template(
                "register.html", memberships=memberships, name=name, email=email
            ), 400

        user = User(
            name=name,
            email=email,
            role=Role.CUSTOMER,
            membership_id=int(membership_id) if membership_id else None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Your account is ready. Pick a show to get started.", "success")
        return redirect(url_for("customer.home"))

    return render_template("register.html", memberships=memberships, name="", email="")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You are signed out.", "info")
    return redirect(url_for("auth.login"))
