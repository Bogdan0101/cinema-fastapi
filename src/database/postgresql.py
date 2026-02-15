from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.config.settings import settings

engine = create_async_engine(settings.database_url, echo=False)

async_session = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_postgresql_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
