from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.configs import settings

engine = create_async_engine(settings.DATABASE_URL, echo = settings.DB_ECHO)

Session: AsyncSession = sessionmaker(
        autocommit = False,
        autoflush = False,
        expire_on_commit = False,
        class_ = AsyncSession,
        bind = engine
    )
