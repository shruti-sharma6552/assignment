from datetime import datetime

from models import db


class Movie(db.Model):
    __tablename__ = "movies"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Integer, nullable=False, default=120)  # minutes
    language = db.Column(db.String(60), nullable=False, default="English")
    genre = db.Column(db.String(90), nullable=True)
    certificate = db.Column(db.String(10), nullable=True)
    poster = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    shows = db.relationship("Show", back_populates="movie", cascade="all, delete-orphan")

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    @property
    def poster_url(self) -> str | None:
        """Relative static path for the uploaded poster, or None if unset."""
        if not self.poster:
            return None
        return f"images/posters/{self.poster}"

    def __repr__(self) -> str:
        return f"<Movie {self.title}>"