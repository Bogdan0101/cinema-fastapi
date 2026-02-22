from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.routes.movies import router as movie_router
from src.routes.accounts import router as account_router
from src.routes.payments import router as payment_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete
from datetime import datetime, timezone
from src.database.models.accounts import ActivationTokenModel, PasswordResetTokenModel
from src.database.postgresql import async_session


async def cleanup_expired_tokens():
    async with async_session() as db:
        now = datetime.now(timezone.utc)
        await db.execute(
            delete(ActivationTokenModel).where(ActivationTokenModel.expires_at < now)
        )
        await db.execute(
            delete(PasswordResetTokenModel).where(
                PasswordResetTokenModel.expires_at < now
            )
        )
        await db.commit()
        print(f"Cleanup task executed at {now}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(cleanup_expired_tokens, "interval", hours=1)
    scheduler.start()
    print("Scheduler started...")

    yield

    scheduler.shutdown()
    print("Scheduler shut down...")


app = FastAPI(
    title="Cinema FastAPI",
    lifespan=lifespan,
)

app.include_router(movie_router, prefix="/cinema", tags=["cinema"])
app.include_router(account_router, prefix="/accounts", tags=["accounts"])
app.include_router(payment_router, prefix="/payments", tags=["payments"])


@app.get("/")
async def root():
    return {"message": "Hello World"}
