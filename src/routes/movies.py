from typing import Optional

from sqlalchemy import select, func, or_
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload, load_only

from src.crud.movies import (
    genre_crud,
    star_crud,
    director_crud,
    certification_crud,
    movie_crud,
    EntityCRUD,
)
from src.database.models.movies import (
    MovieModel,
    MoviesDirectorsModel,
    GenreModel,
    MoviesGenresModel,
    StarModel,
    DirectorModel,
    MovieSortOptions,
    MoviesStarsModel,
    CertificationModel,
)
from src.schemas.movies import (
    MovieSchemaBase,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema,
    PaginateResponseSchema,
    EntityDetailSchema,
    NameIdSchema,
    EntityMovieCountSchema,
    EntityCreateOrUpdateSchema,
)
from src.database.postgresql import get_postgresql_db

router = APIRouter()


@router.get("/movies/", response_model=PaginateResponseSchema, status_code=200)
async def get_movie_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    year: Optional[int] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=10),
    search: Optional[str] = Query(None, min_length=1),
    sort_by: MovieSortOptions = Query(MovieSortOptions.id_desc),
    db: AsyncSession = Depends(get_postgresql_db),
):
    stmt = select(MovieModel).distinct()
    if year:
        stmt = stmt.where(MovieModel.year == year)
    if min_rating:
        stmt = stmt.where(MovieModel.imdb >= min_rating)
    if search:
        search_filter = f"%{search}%"
        stmt = stmt.outerjoin(MovieModel.stars).outerjoin(MovieModel.directors)
        stmt = stmt.where(
            or_(
                MovieModel.name.ilike(search_filter),
                MovieModel.description.ilike(search_filter),
                StarModel.name.ilike(search_filter),
                DirectorModel.name.ilike(search_filter),
            )
        )
    sort_options = {
        MovieSortOptions.price_asc: MovieModel.price.asc(),
        MovieSortOptions.price_desc: MovieModel.price.desc(),
        MovieSortOptions.year_new: MovieModel.year.desc(),
        MovieSortOptions.rating_top: MovieModel.imdb.desc(),
        MovieSortOptions.id_desc: MovieModel.id.desc(),
        MovieSortOptions.id_asc: MovieModel.id.asc(),
    }
    stmt = stmt.order_by(sort_options.get(sort_by, MovieModel.id.desc()))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_items = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    if not total_items:
        raise HTTPException(status_code=404, detail="No movies found")
    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found")
    movie_list = [MovieSchemaBase.model_validate(movie) for movie in movies]
    total_pages = (total_items + per_page - 1) // per_page
    response = PaginateResponseSchema(
        items=movie_list,
        prev_page=(
            f"/cinema/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
        ),
        next_page=(
            f"/cinema/movies/?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.get("/movies/{movie_id}/", response_model=MovieDetailSchema, status_code=200)
async def get_movie_by_id(movie_id: int, db: AsyncSession = Depends(get_postgresql_db)):
    return await movie_crud.get_by_id(
        db=db,
        obj_id=movie_id,
        options=[
            joinedload(MovieModel.genres),
            joinedload(MovieModel.certification),
            joinedload(MovieModel.stars),
            joinedload(MovieModel.directors),
        ],
    )


@router.post("/movies/", response_model=MovieDetailSchema, status_code=201)
async def create_movie(
    movie_data: MovieCreateSchema, db: AsyncSession = Depends(get_postgresql_db)
):
    existing_movie = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie_data.name,
            MovieModel.year == movie_data.year,
            MovieModel.time == movie_data.time,
        )
    )
    if existing_movie.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"Movie with name: '{movie_data.name}'"
            f" year: '{movie_data.year}'"
            f" time: '{movie_data.time}' already exists.",
        )
    try:
        certification = await EntityCRUD.get_or_create(
            db, certification_crud, movie_data.certification
        )
        genres = [
            await EntityCRUD.get_or_create(db, genre_crud, g) for g in movie_data.genres
        ]
        stars = [
            await EntityCRUD.get_or_create(db, star_crud, s) for s in movie_data.stars
        ]
        directors = [
            await EntityCRUD.get_or_create(db, director_crud, d)
            for d in movie_data.directors
        ]
        movie = MovieModel(
            **movie_data.model_dump(
                exclude={"genres", "stars", "directors", "certification"}
            ),
            certification=certification,
            genres=genres,
            stars=stars,
            directors=directors,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, ["genres", "stars", "directors", "certification"])
        return movie
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


@router.patch("/movies/{movie_id}/", response_model=MovieDetailSchema, status_code=200)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    movie = await movie_crud.update(db=db, obj_id=movie_id, data=movie_data)
    await db.refresh(movie, ["genres", "stars", "directors", "certification"])
    return movie


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await movie_crud.delete(db=db, obj_id=movie_id)


@router.get(
    "/genres/",
    response_model=PaginateResponseSchema[EntityMovieCountSchema],
    status_code=200,
)
async def get_genre_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await genre_crud.get_all_with_movie_count(
        db=db,
        page=page,
        per_page=per_page,
        rel_table=MoviesGenresModel,
        rel_field=MoviesGenresModel.c.genre_id,
        path="genres",
    )


@router.get("/genres/{genre_id}/", response_model=EntityDetailSchema, status_code=200)
async def get_genre_by_id(genre_id: int, db: AsyncSession = Depends(get_postgresql_db)):
    return await genre_crud.get_by_id(
        db=db,
        obj_id=genre_id,
        options=[
            selectinload(GenreModel.movies).options(
                load_only(MovieModel.id, MovieModel.name)
            )
        ],
    )


@router.post("/genres/", response_model=NameIdSchema, status_code=201)
async def create_genre(
    genre_data: EntityCreateOrUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await genre_crud.create(db=db, data=genre_data)


@router.patch("/genres/{genre_id}/", response_model=NameIdSchema, status_code=200)
async def update_genre(
    genre_id: int,
    genre_data: EntityCreateOrUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await genre_crud.update(
        db=db,
        obj_id=genre_id,
        data=genre_data,
    )


@router.delete("/genres/{genre_id}/", status_code=204)
async def delete_genre(genre_id: int, db: AsyncSession = Depends(get_postgresql_db)):
    return await genre_crud.delete(
        db=db,
        obj_id=genre_id,
    )


@router.get(
    "/stars/",
    response_model=PaginateResponseSchema[EntityMovieCountSchema],
    status_code=200,
)
async def get_star_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await star_crud.get_all_with_movie_count(
        db=db,
        page=page,
        per_page=per_page,
        rel_table=MoviesStarsModel,
        rel_field=MoviesStarsModel.c.star_id,
        path="stars",
    )


@router.get("/stars/{star_id}/", response_model=EntityDetailSchema, status_code=200)
async def get_star_by_id(star_id: int, db: AsyncSession = Depends(get_postgresql_db)):
    return await star_crud.get_by_id(
        db=db,
        obj_id=star_id,
        options=[
            selectinload(StarModel.movies).options(
                load_only(MovieModel.id, MovieModel.name)
            )
        ],
    )


@router.post("/stars/", response_model=NameIdSchema, status_code=201)
async def create_star(
    star_data: EntityCreateOrUpdateSchema, db: AsyncSession = Depends(get_postgresql_db)
):
    return await star_crud.create(db=db, data=star_data)


@router.patch("/stars/{star_id}/", response_model=NameIdSchema, status_code=200)
async def update_star(
    star_id: int,
    star_data: EntityCreateOrUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await star_crud.update(
        db=db,
        obj_id=star_id,
        data=star_data,
    )


@router.delete("/stars/{star_id}/", status_code=204)
async def delete_star(star_id: int, db: AsyncSession = Depends(get_postgresql_db)):
    return await star_crud.delete(
        db=db,
        obj_id=star_id,
    )


@router.get(
    "/certifications/",
    response_model=PaginateResponseSchema[EntityMovieCountSchema],
    status_code=200,
)
async def get_certification_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await certification_crud.get_all_with_movie_count(
        db=db,
        page=page,
        per_page=per_page,
        rel_table=MovieModel.__table__,
        rel_field=MovieModel.certification_id,
        path="certifications",
        count_field=MovieModel.id,
    )


@router.get(
    "/certifications/{certification_id}/",
    response_model=EntityDetailSchema,
    status_code=200,
)
async def get_certification_by_id(
    certification_id: int, db: AsyncSession = Depends(get_postgresql_db)
):
    return await certification_crud.get_by_id(
        db=db,
        obj_id=certification_id,
        options=[
            selectinload(CertificationModel.movies).options(
                load_only(MovieModel.id, MovieModel.name)
            )
        ],
    )


@router.post("/certifications/", response_model=NameIdSchema, status_code=201)
async def create_certification(
    certification_data: EntityCreateOrUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await certification_crud.create(db=db, data=certification_data)


@router.patch(
    "/certifications/{certification_id}/", response_model=NameIdSchema, status_code=200
)
async def update_certification(
    certification_id: int,
    certification_data: EntityCreateOrUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await certification_crud.update(
        db=db,
        obj_id=certification_id,
        data=certification_data,
    )


@router.delete("/certifications/{certification_id}/", status_code=204)
async def delete_certification(
    certification_id: int, db: AsyncSession = Depends(get_postgresql_db)
):
    return await certification_crud.delete(
        db=db,
        obj_id=certification_id,
    )


@router.get(
    "/directors/",
    response_model=PaginateResponseSchema[EntityMovieCountSchema],
    status_code=200,
)
async def get_director_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await director_crud.get_all_with_movie_count(
        db=db,
        page=page,
        per_page=per_page,
        rel_table=MoviesDirectorsModel,
        rel_field=MoviesDirectorsModel.c.director_id,
        path="directors",
    )


@router.get(
    "/directors/{director_id}/", response_model=EntityDetailSchema, status_code=200
)
async def get_director_by_id(
    director_id: int, db: AsyncSession = Depends(get_postgresql_db)
):
    return await director_crud.get_by_id(
        db=db,
        obj_id=director_id,
        options=[
            selectinload(DirectorModel.movies).options(
                load_only(MovieModel.id, MovieModel.name)
            )
        ],
    )


@router.post("/directors/", response_model=NameIdSchema, status_code=201)
async def create_director(
    director_data: EntityCreateOrUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await director_crud.create(db=db, data=director_data)


@router.patch("/directors/{director_id}/", response_model=NameIdSchema, status_code=200)
async def update_director(
    director_id: int,
    director_data: EntityCreateOrUpdateSchema,
    db: AsyncSession = Depends(get_postgresql_db),
):
    return await director_crud.update(
        db=db,
        obj_id=director_id,
        data=director_data,
    )


@router.delete("/directors/{director_id}/", status_code=204)
async def delete_director(
    director_id: int, db: AsyncSession = Depends(get_postgresql_db)
):
    return await director_crud.delete(
        db=db,
        obj_id=director_id,
    )
