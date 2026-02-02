import asyncio
import json
import selectors
from decimal import Decimal
from sqlalchemy import select, insert
from src.database.postgresql import async_session
from src.database.models.movies import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
    MoviesGenresModel,
    MoviesStarsModel,
    MoviesDirectorsModel,
)


async def get_or_create(session, model, field, value):
    stmt = select(model).where(getattr(model, field) == value)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if not obj:
        obj = model(**{field: value})
        session.add(obj)
        await session.flush()
    return obj


async def load_json():
    async with async_session() as session:
        try:
            with open("movies_data.json", "r", encoding="utf-8") as f:
                movies_list = json.load(f)
        except FileNotFoundError:
            print("File movies_data.json is not found.")
            return

        print(f"Load {len(movies_list)} in db.")

        for item in movies_list:
            stmt = select(MovieModel).where(
                MovieModel.name == item["name"],
                MovieModel.year == item["year"],
                MovieModel.time == item["time"],
            )
            existing_movie = await session.execute(stmt)
            if existing_movie.scalars().first():
                continue

            cert = await get_or_create(
                session, CertificationModel, "name", item["certification"]
            )

            movie = MovieModel(
                name=item["name"],
                year=item["year"],
                time=item["time"],
                imdb=item["imdb"],
                votes=item["votes"],
                description=item["description"],
                gross=item["gross"],
                price=Decimal(str(item["price"])),
                certification_id=cert.id,
            )
            session.add(movie)
            await session.flush()

            for g_name in item["genres"]:
                genre = await get_or_create(session, GenreModel, "name", g_name)
                await session.execute(
                    insert(MoviesGenresModel).values(
                        movie_id=movie.id, genre_id=genre.id
                    )
                )

            for s_name in item["stars"]:
                star = await get_or_create(session, StarModel, "name", s_name)
                await session.execute(
                    insert(MoviesStarsModel).values(movie_id=movie.id, star_id=star.id)
                )

            for d_name in item["directors"]:
                director = await get_or_create(session, DirectorModel, "name", d_name)
                await session.execute(
                    insert(MoviesDirectorsModel).values(
                        movie_id=movie.id, director_id=director.id
                    )
                )

        await session.commit()
        print("DB is success synchronize with JSON!")


if __name__ == "__main__":
    selector = selectors.SelectSelector()

    def loop_factory():
        return asyncio.SelectorEventLoop(selector)

    asyncio.run(load_json(), loop_factory=loop_factory)
