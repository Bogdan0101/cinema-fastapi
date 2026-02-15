from typing import Type, TypeVar, Generic
from sqlalchemy import select, func, and_, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from src.database.models.movies import MovieUserFavorites
from src.schemas.movies import FavoriteResponse
from src.database.models.movies import (
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
    MovieModel,
)

T = TypeVar("T")
TS = TypeVar("TS")


class EntityCRUD(Generic[T, TS]):
    def __init__(self, model: Type[T]):
        self.model = model

    @staticmethod
    async def get_or_create(db: AsyncSession, crud_obj: "EntityCRUD", name: str):
        stmt = select(crud_obj.model).where(crud_obj.model.name == name)
        result = await db.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            obj = crud_obj.model(name=name)
            db.add(obj)
            await db.flush()
        return obj

    async def get_all_with_movie_count(
        self,
        db: AsyncSession,
        page: int,
        per_page: int,
        rel_table,
        rel_field,
        path: str,
        count_field=None,
    ):
        if count_field is None:
            count_field = rel_table.c.movie_id

        offset = (page - 1) * per_page
        count_stmt = select(func.count(self.model.id))
        total_items = (await db.execute(count_stmt)).scalar() or 0
        if not total_items:
            raise HTTPException(status_code=404, detail="Not found")
        stmt = (
            select(
                self.model.id,
                self.model.name,
                func.count(count_field).label("movies_count"),
            )
            .outerjoin(rel_table, self.model.id == rel_field)
            .group_by(self.model.id)
        )
        if hasattr(self.model, "default_order_by"):
            stmt = stmt.order_by(*self.model.default_order_by())
        result = await db.execute(stmt.offset(offset).limit(per_page))
        items = result.mappings().all()
        total_pages = (total_items + per_page - 1) // per_page
        return {
            "items": items,
            "total_items": total_items,
            "total_pages": total_pages,
            "prev_page": (
                f"/cinema/{path}/?page={page - 1}&per_page={per_page}"
                if page > 1
                else None
            ),
            "next_page": (
                f"/cinema/{path}/?page={page + 1}&per_page={per_page}"
                if page < total_pages
                else None
            ),
        }

    async def get_by_id(self, db: AsyncSession, obj_id: int, options=None):
        stmt = select(self.model).where(self.model.id == obj_id)
        if options:
            if isinstance(options, list):
                stmt = stmt.options(*options)
            else:
                stmt = stmt.options(options)
        result = await db.execute(stmt)
        obj = result.scalars().unique().first()
        if not obj:
            raise HTTPException(
                status_code=404, detail=f"Object with id {obj_id} is not found"
            )
        return obj

    async def create(self, db: AsyncSession, data: TS):
        check_stmt = select(self.model).where(self.model.name == data.name)
        existing = (await db.execute(check_stmt)).scalars().first()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Object with name {data.name} already exists."
            )
        new_obj = self.model(name=data.name)
        db.add(new_obj)
        try:
            await db.commit()
            await db.refresh(new_obj)
            return new_obj
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    async def update(self, db: AsyncSession, obj_id: int, data: TS):
        obj = await self.get_by_id(db, obj_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        try:
            await db.commit()
            await db.refresh(obj)
            return obj
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    async def delete(self, db: AsyncSession, obj_id: int):
        obj = await self.get_by_id(db, obj_id)
        try:
            await db.delete(obj)
            await db.commit()
            return None
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))


genre_crud = EntityCRUD(GenreModel)
star_crud = EntityCRUD(StarModel)
director_crud = EntityCRUD(DirectorModel)
certification_crud = EntityCRUD(CertificationModel)
movie_crud = EntityCRUD(MovieModel)


async def toggle_movie_favorite(db: AsyncSession, user_id: int, movie_id: int):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    stmt = select(MovieUserFavorites).where(
        and_(
            MovieUserFavorites.c.user_id == user_id,
            MovieUserFavorites.c.movie_id == movie_id,
        )
    )
    result = await db.execute(stmt)
    if_fav = result.first()

    if if_fav:
        await db.execute(
            delete(MovieUserFavorites).where(
                and_(
                    MovieUserFavorites.c.user_id == user_id,
                    MovieUserFavorites.c.movie_id == movie_id,
                )
            )
        )
        await db.commit()
        return FavoriteResponse(
            movie_id=movie_id,
            is_favorite=False,
            message="Removed from favorites.",
        )
    else:
        await db.execute(
            insert(MovieUserFavorites).values(user_id=user_id, movie_id=movie_id)
        )
        await db.commit()
        return FavoriteResponse(
            movie_id=movie_id,
            is_favorite=True,
            message="Added to favorites.",
        )
