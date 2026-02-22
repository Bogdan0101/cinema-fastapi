from datetime import datetime
from typing import Optional, TYPE_CHECKING
import uuid as uuid_obj
from decimal import Decimal
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    String,
    Float,
    Text,
    DECIMAL,
    UniqueConstraint,
    ForeignKey,
    Table,
    Column,
    Integer,
    func,
    CheckConstraint,
)
from sqlalchemy.orm import mapped_column, Mapped, relationship

from src.database.models.base import Base
from enum import Enum

if TYPE_CHECKING:
    from src.database.models.accounts import UserModel


class MovieSortOptions(str, Enum):
    price_asc = ("price_asc",)
    price_desc = ("price_desc",)
    year_new = ("year_new",)
    rating_top = ("rating_top",)
    id_desc = ("id_desc",)
    id_asc = "id_asc"


MovieUserFavorites = Table(
    "movie_user_favorites",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
)

MoviesGenresModel = Table(
    "movies_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)

MoviesStarsModel = Table(
    "movies_stars",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "star_id",
        ForeignKey("stars.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)

MoviesDirectorsModel = Table(
    "movies_directors",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "director_id",
        ForeignKey("directors.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)


class ReviewModel(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user = relationship("UserModel", back_populates="reviews")
    movie = relationship("MovieModel", back_populates="reviews")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 10", name="rating_1_10"),
        UniqueConstraint("user_id", "movie_id", name="movie_user_unique_review"),
    )


class GenreModel(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesGenresModel,
        back_populates="genres",
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.asc()]

    def __repr__(self):
        return f"<Genre(name='{self.name}')>"


class StarModel(Base):
    __tablename__ = "stars"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesStarsModel,
        back_populates="stars",
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.asc()]

    def __repr__(self):
        return f"<Star(name='{self.name}')>"


class DirectorModel(Base):
    __tablename__ = "directors"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesDirectorsModel,
        back_populates="directors",
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.asc()]

    def __repr__(self):
        return f"<Director(name='{self.name}')>"


class CertificationModel(Base):
    __tablename__ = "certifications"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel", back_populates="certification"
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.asc()]

    def __repr__(self):
        return f"<Certification(name='{self.name}')>"


class MovieModel(Base):
    __tablename__ = "movies"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[uuid_obj.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid_obj.uuid4
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)
    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, default=0.0)

    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="unique_movie_constraint"),
    )

    favorites: Mapped[list["UserModel"]] = relationship(
        "UserModel", secondary=MovieUserFavorites, back_populates="favorite_movies"
    )
    reviews: Mapped[list["ReviewModel"]] = relationship(
        "ReviewModel",
        back_populates="movie",
        cascade="all, delete-orphan",
    )

    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"), nullable=False
    )
    certification: Mapped["CertificationModel"] = relationship(
        "CertificationModel", back_populates="movies"
    )

    genres: Mapped[list["GenreModel"]] = relationship(
        "GenreModel",
        secondary=MoviesGenresModel,
        back_populates="movies",
    )
    stars: Mapped[list["StarModel"]] = relationship(
        "StarModel",
        secondary=MoviesStarsModel,
        back_populates="movies",
    )
    directors: Mapped[list["DirectorModel"]] = relationship(
        "DirectorModel",
        secondary=MoviesDirectorsModel,
        back_populates="movies",
    )

    def __repr__(self):
        return f"<Movie(name='{self.name}')>"
