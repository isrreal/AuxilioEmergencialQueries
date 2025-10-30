from typing import Optional, AsyncGenerator
from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.core.database import Session
from app.core.configs import settings
from app.core.auth import oauth2_schema
from app.models.models import Responsavel, Beneficiario

class TokenData(BaseModel):
    """Schema para dados do token JWT."""
    username: Optional[str] = None

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obter sessão do banco de dados.
    
    Yields:
        AsyncSession: Sessão assíncrona do SQLAlchemy
    """
    session: AsyncSession = Session()
    try:
        yield session
    finally:
        await session.close()


async def get_current_user(
    db: AsyncSession = Depends(get_session),
    token: str = Depends(oauth2_schema)
):
    """
    Dependency para obter o usuário autenticado atual.
    
    Args:
        db: Sessão do banco de dados
        token: Token JWT do header Authorization
        
    Returns:
        UsuarioModel: Usuário autenticado
        
    Raises:
        HTTPException: Se credenciais inválidas
    """
    credential_exception: HTTPException = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Não foi possível autenticar a credencial",
        headers = {"WWW-Authenticate": "Bearer"}
    )
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms = [settings.ALGORITHM],
            options = {"verify_aud": False}
        )
        username: str = payload.get("sub")
        
        if username is None:
            raise credential_exception
            
        token_data: TokenData = TokenData(username = username)
        
    except JWTError:
        raise credential_exception

    return {"id": token_data.username, "authenticated": True}