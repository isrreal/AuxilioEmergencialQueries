from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.core.auth import (
    oauth2_schema, 
    decodificar_token, 
    extrair_user_id, 
    validar_tipo_token, 
    token_expirado
)

from app.core.database import Session
from app.models.models import Usuario


class TokenData(BaseModel):
    """Schema para dados do token JWT."""
    user_id: int | None = None

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

async def get_current_user(
    db: AsyncSession = Depends(get_session),
    token: str = Depends(oauth2_schema)
) -> Usuario:
    """
    Retorna o usuário autenticado a partir do token JWT.
    """
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Não foi possível autenticar a credencial.",
        # Diz ao cliente que o server só aceitará seu acesso com um token correto (tipo Bearer).
        headers = {"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decodificar_token(token)

        if not validar_tipo_token(payload, "access_token") or token_expirado(payload):
            raise credentials_exception

        user_id = extrair_user_id(payload)
        if user_id is None:
            raise credentials_exception

        token_data = TokenData(user_id = int(user_id))

    except JWTError:
        raise credentials_exception

    async with db as session:
        query = select(Usuario).filter(Usuario.id == token_data.user_id)
        result = await session.execute(query)
        usuario: Usuario = result.scalars().first()

        if usuario is None:
            raise credentials_exception

        return usuario
