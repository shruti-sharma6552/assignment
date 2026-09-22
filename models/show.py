from models import db


class Show(db.Model):
    __tablename__ = "shows"

    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(
        db.Integer, db.ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    cinema_id = db.Column(
        db.Integer, db.ForeignKey("cinemas.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    show_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)

    movie = db.relationship("Movie", back_populates="shows")
    cinema = db.relationship("Cinema", back_populates="shows")
    seat_tiers = db.relationship(
        "SeatTier", back_populates="show",
        cascade="all, delete-orphan", order_by="SeatTier.price"
    )
    bookings = db.relationship("Booking", back_populates="show")

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    @property
    def is_bookable(self) -> bool:
        return (
            self.is_active
            and self.movie is not None and self.movie.is_active
            and self.cinema is not None and self.cinema.is_active
        )

    def __repr__(self) -> str:
        return f"<Show {self.id} movie={self.movie_id} cinema={self.cinema_id}>"
