from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from src.security.token import get_jwt_manager

from src.database.models.movies import (
    MovieModel,
    CertificationModel,
    GenreModel,
    StarModel,
    DirectorModel,
)
from src.database.postgresql import async_session
from sqlalchemy import text
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from src.config.settings import settings
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class BaseCinemaTestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not settings.TESTING:
            print("Error variable TESTING=False.")
            sys.exit(1)
        if "_test" not in settings.database_url:
            print("The database is not intended for testing.")
            sys.exit(1)

        self.session = async_session()
        await self.session.execute(
            text(
                "TRUNCATE TABLE user_groups, certifications, users, movies, genres, stars, directors, "
                "movies_genres, movies_stars, movies_directors, reviews RESTART IDENTITY CASCADE"
            )
        )
        await self.session.commit()

        user_group = UserGroupModel(name=UserGroupEnum.USER)
        admin_group = UserGroupModel(name=UserGroupEnum.ADMIN)

        cert_one = CertificationModel(name="PG-13")
        cert_two = CertificationModel(name="R")
        genre_one = GenreModel(name="Sci-Fi")
        star_one = StarModel(name="Leonardo DiCaprio")
        director_one = DirectorModel(name="Christopher Nolan")
        genre_two = GenreModel(name="Crime")
        star_two = StarModel(name="John Smith")
        director_two = DirectorModel(name="Bob Smith")

        self.session.add_all(
            [
                user_group,
                genre_one,
                star_one,
                director_one,
                director_two,
                star_two,
                genre_two,
                admin_group,
                cert_one,
                cert_two,
            ]
        )
        await self.session.commit()

        self.user = UserModel(
            email="user@gmail.com", group_id=user_group.id, is_active=True
        )
        self.user.password = "Password123!"
        self.admin = UserModel(
            email="admin@gmail.com", group_id=admin_group.id, is_active=True
        )
        self.admin.password = "SafePassword123!"

        self.movie_one = MovieModel(
            name="Inception",
            year=2010,
            time=148,
            imdb=8.8,
            votes=5000,
            description="Inception test",
            price=Decimal("500.00"),
            certification_id=cert_one.id,
            genres=[genre_one],
            stars=[star_one],
            directors=[director_one],
        )
        self.movie_two = MovieModel(
            name="Creed III",
            year=2018,
            time=110,
            imdb=9.8,
            votes=5000,
            description="Creed III test",
            price=Decimal("400.00"),
            certification_id=cert_two.id,
            genres=[genre_two],
            stars=[star_two],
            directors=[director_two],
        )
        self.session.add_all([self.user, self.admin, self.movie_one, self.movie_two])
        await self.session.commit()

        await self.session.refresh(self.user)
        await self.session.refresh(self.admin)
        await self.session.refresh(self.movie_one)
        await self.session.refresh(self.movie_two)

        jwt_manager = get_jwt_manager()
        self.user_headers = {
            "Authorization": f"Bearer {jwt_manager.create_access_token(data={"user_id": self.user.id})}"
        }
        self.admin_headers = {
            "Authorization": f"Bearer {jwt_manager.create_access_token(data={"user_id": self.admin.id})}"
        }

        self.client = AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.session.close()
