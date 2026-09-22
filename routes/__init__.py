"""Flask blueprints. Every route renders a Jinja2 template -- no REST APIs."""

from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(view):
    """Allow only authenticated ADMIN users past this point."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
