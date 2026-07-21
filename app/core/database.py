import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo = True)

Session: AsyncSession = sessionmaker(
        autocommit = False,
        autoflush = False,
        expire_on_commit = False,
        class_ = AsyncSession,
        bind = engine
    )
