import stripe
from sqlalchemy import select, and_, func, or_
from fastapi import APIRouter, Request, Depends, HTTPException, Query, Header
from decimal import Decimal
from sqlalchemy.orm import selectinload
from src.schemas.movies import PaginateResponseSchema, MovieSchemaBase
from src.schemas.payments import OrderResponseSchema
from src.database.models.payments import (
    OrderModel,
    OrderItemModel,
    OrderStatus,
    PaymentModel,
    PaymentStatus,
)
from src.database.models.movies import (
    MovieModel,
    MovieSortOptions,
    StarModel,
    DirectorModel,
)
from src.database.postgresql import get_postgresql_db
from src.crud.accounts import get_current_user
from src.config.settings import settings
from src.database.models.accounts import UserModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import cast, Any, Optional

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post(
    "/orders/checkout/{movie_id}/", response_model=OrderResponseSchema, status_code=201
)
async def checkout_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(get_current_user),
):
    order_stmt = (
        select(OrderItemModel)
        .join(OrderModel)
        .where(
            and_(
                OrderModel.user_id == current_user.id,
                OrderModel.status == OrderStatus.PAID,
                OrderItemModel.movie_id == movie_id,
            )
        )
    )
    already_owned = (await db.execute(order_stmt)).scalar_one_or_none()
    if already_owned:
        raise HTTPException(status_code=400, detail="You have a movie.")

    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    new_order = OrderModel(
        user_id=current_user.id,
        total_amount=Decimal(str(movie.price)),
        status=OrderStatus.PENDING,
    )
    db.add(new_order)
    await db.flush()

    order_item = OrderItemModel(
        order_id=new_order.id,
        movie_id=cast(int, cast(Any, movie.id)),
        price_at_order=Decimal(str(movie.price)),
    )
    db.add(order_item)

    await db.commit()

    stmt = (
        select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.movie))
        .where(OrderModel.id == new_order.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


@router.post("/orders/{order_id}/pay/")
async def create_checkout_session(
    order_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(get_current_user),
):
    order = await db.get(OrderModel, order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == OrderStatus.PAID:
        raise HTTPException(status_code=400, detail="Order already paid")

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"Order #{order.id}"},
                        "unit_amount": int(order.total_amount * 100),
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{settings.DOMAIN}/payments/success/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.DOMAIN}/payments/cancel/",
            metadata={"order_id": str(order.id)},
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_postgresql_db),
):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")

        if order_id:
            stmt = select(OrderModel).where(OrderModel.id == int(order_id))
            order = (await db.execute(stmt)).scalar_one_or_none()

            if order and order.status != OrderStatus.PAID:
                order.status = OrderStatus.PAID
                payment = PaymentModel(
                    user_id=cast(int, cast(Any, order.user_id)),
                    order_id=cast(int, cast(Any, order.id)),
                    amount=cast(Decimal, cast(Any, order.total_amount)),
                    status=PaymentStatus.SUCCESSFUL,
                    external_payment_id=session.get("id"),
                )
                db.add(payment)
                await db.commit()

    return {"status": "success"}


@router.get("/success/")
async def payment_success(session_id: str):
    return {"message": "Payment is successful.", "session_id": session_id}


@router.get("/cancel/")
async def payment_cancel():
    return {"message": "Payment is not successful."}


@router.get("/me/library/", response_model=PaginateResponseSchema, status_code=200)
async def get_movie_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    year: Optional[int] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=10),
    search: Optional[str] = Query(None, min_length=1),
    sort_by: MovieSortOptions = Query(MovieSortOptions.id_desc),
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(get_current_user),
):
    stmt = (
        select(MovieModel)
        .distinct()
        .join(OrderItemModel, MovieModel.id == OrderItemModel.movie_id)
        .join(OrderModel, OrderItemModel.order_id == OrderModel.id)
        .where(
            OrderModel.user_id == current_user.id, OrderModel.status == OrderStatus.PAID
        )
    )

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

    sort_options: dict[MovieSortOptions, Any] = {
        MovieSortOptions.price_asc: MovieModel.price.asc(),
        MovieSortOptions.price_desc: MovieModel.price.desc(),
        MovieSortOptions.year_new: MovieModel.year.desc(),
        MovieSortOptions.rating_top: MovieModel.imdb.desc(),
        MovieSortOptions.id_desc: MovieModel.id.desc(),
        MovieSortOptions.id_asc: MovieModel.id.asc(),
    }
    sort_criterion = sort_options.get(sort_by, MovieModel.id.desc())
    stmt = stmt.order_by(sort_criterion)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_items = (await db.execute(count_stmt)).scalar() or 0

    if not total_items:
        raise HTTPException(
            status_code=404, detail="Library is empty or no movies found"
        )

    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result_movies = await db.execute(stmt)
    movies = result_movies.scalars().all()

    movie_list = [MovieSchemaBase.model_validate(movie) for movie in movies]
    total_pages = (total_items + per_page - 1) // per_page

    return PaginateResponseSchema(
        items=movie_list,
        prev_page=(
            f"/me/library/?page={page - 1}&per_page={per_page}" if page > 1 else None
        ),
        next_page=(
            f"/me/library/?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
