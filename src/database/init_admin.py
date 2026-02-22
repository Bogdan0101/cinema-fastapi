import asyncio
from src.database.postgresql import async_session
from src.database.models.accounts import (
    UserModel,
    UserGroupEnum,
    UserGroupModel,
)
from sqlalchemy import select
from src.database.load_json import get_or_create


async def create_default_admin():
    async with async_session() as session:
        print("Initializing user groups...")
        for role in UserGroupEnum:
            await get_or_create(session, UserGroupModel, "name", role.value)

        group_query = await session.execute(
            select(UserGroupModel).filter_by(name=UserGroupEnum.ADMIN)
        )
        admin_group = group_query.scalar_one_or_none()
        if not admin_group:
            print("Admin group not found in database.")
            return

        result = await session.execute(
            select(UserModel).filter_by(email="admin@example.com")
        )
        admin = result.scalar_one_or_none()

        if not admin:
            new_admin = UserModel.create(
                email="admin@example.com",
                raw_password="Adminpass1!",
                group_id=admin_group.id,
            )
            new_admin.is_active = True
            session.add(new_admin)
            await session.commit()
            print("Default admin created!")
        else:
            print("Admin already exists.")


if __name__ == "__main__":
    asyncio.run(create_default_admin())
