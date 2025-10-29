from typing import Generator, Optional, AsyncGenerator
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
        detail="Não foi possível autenticar a credencial",
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


async def get_responsavel_or_404(
    nis_responsavel: str,
    db: AsyncSession = Depends(get_session)
) -> Responsavel:
    """
    Dependency para buscar um responsável ou retornar 404.
    
    Args:
        nis_responsavel: NIS do responsável
        db: Sessão do banco de dados
        
    Returns:
        Responsavel: Objeto do responsável encontrado
        
    Raises:
        HTTPException: Se responsável não encontrado
    """
    query = select(Responsavel).filter(Responsavel.nis_responsavel == nis_responsavel)
    result = await db.execute(query)
    responsavel = result.scalars().unique().one_or_none()
    
    if not responsavel:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Responsável com NIS {nis_responsavel} não encontrado"
        )
    
    return responsavel


async def get_beneficiario_or_404(
    nis_beneficiario: str,
    db: AsyncSession = Depends(get_session)
) -> Beneficiario:
    """
    Dependency para buscar um beneficiário ou retornar 404.
    
    Args:
        nis_beneficiario: NIS do beneficiário
        db: Sessão do banco de dados
        
    Returns:
        Beneficiario: Objeto do beneficiário encontrado
        
    Raises:
        HTTPException: Se beneficiário não encontrado
    """
    query = select(Beneficiario).filter(Beneficiario.nis_beneficiario == nis_beneficiario)
    result = await db.execute(query)
    beneficiario = result.scalars().unique().one_or_none()
    
    if not beneficiario:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Beneficiário com NIS {nis_beneficiario} não encontrado"
        )
    
    return beneficiario


class PaginationParams(BaseModel):
    """Schema para parâmetros de paginação."""
    skip: int = 0
    limit: int = 100
    
    class Config:
        frozen = True


def get_pagination_params(
    skip: int = 0,
    limit: int = 100
) -> PaginationParams:
    """
    Dependency para parâmetros de paginação.
    
    Args:
        skip: Número de registros para pular
        limit: Número máximo de registros para retornar
        
    Returns:
        PaginationParams: Parâmetros de paginação validados
        
    Raises:
        HTTPException: Se parâmetros inválidos
    """
    if skip < 0:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "O parâmetro 'skip' deve ser maior ou igual a 0"
        )
    
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "O parâmetro 'limit' deve estar entre 1 e 1000"
        )
    
    return PaginationParams(skip = skip, limit = limit)


class FilterParams(BaseModel):
    """Schema para parâmetros de filtro."""
    uf: Optional[str] = None
    municipio: Optional[str] = None
    ano_mes: Optional[str] = None
    
    class Config:
        frozen = True


def get_filter_params(
    uf: Optional[str] = None,
    municipio: Optional[str] = None,
    ano_mes: Optional[str] = None
) -> FilterParams:
    """
    Dependency para parâmetros de filtro.
    
    Args:
        uf: Sigla da UF para filtrar
        municipio: Nome do município para filtrar
        ano_mes: Período no formato YYYYMM
        
    Returns:
        FilterParams: Parâmetros de filtro validados
        
    Raises:
        HTTPException: Se parâmetros inválidos
    """
    if uf and len(uf) != 2:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "A UF deve ter exatamente 2 caracteres"
        )
    
    if ano_mes and (len(ano_mes) != 6 or not ano_mes.isdigit()):
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "O parâmetro 'ano_mes' deve estar no formato YYYYMM (ex: 202401)"
        )
    
    return FilterParams(uf = uf, municipio = municipio, ano_mes = ano_mes)