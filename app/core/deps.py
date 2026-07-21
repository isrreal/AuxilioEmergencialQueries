from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Session

# Um gerador assíncrono: retorna um lote de uma conexão assíncrona, ou um objeto None.

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obter sessão do banco de dados.
    """
    session: AsyncSession = Session()
    try:
        yield session
    finally:
        await session.close()
