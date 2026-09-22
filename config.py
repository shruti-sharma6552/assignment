"""Application configuration for CinePrice.

Database credentials are read from environment variables so that no real
password is ever committed to source control.  Sensible localhost defaults
are provided for a standard XAMPP / stock MySQL installation.
"""

import os
from urllib.parse import quote_plus


def _build_mysql_uri() -> str:
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    host = os.environ.get("MYSQL_HOST", "localhost")
    port = os.environ.get("MYSQL_PORT", "3306")
    database = os.environ.get("MYSQL_DATABASE", "cineprice")

    credentials = quote_plus(user)
    if password:
        credentials += ":" + quote_plus(password)

    return f"mysql+pymysql://{credentials}@{host}:{port}/{database}?charset=utf8mb4"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cineprice-local-dev-secret-key")

    # DATABASE_URL wins when set (useful for tests, which use SQLite).
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _build_mysql_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Poster uploads are capped at 4 MB in routes/admin.py; this adds a hard
    # ceiling slightly above that so Werkzeug rejects anything larger before
    # it is fully read into memory.
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024

    # Auto-create tables and load demo data on first run.
    AUTO_INIT_DB = os.environ.get("AUTO_INIT_DB", "1") == "1"


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    AUTO_INIT_DB = False
    TESTING = True