from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import Responsavel
from app.schemas.schemas import ResponsavelListResponse
from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.get("/", response_model = List[ResponsavelListResponse])
async def listar_responsaveis(
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    nome: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session)
):
    """Lista responsáveis com filtros opcionais."""
    async with db as session:
        query = select(Responsavel)
        if nome:
            query = query.filter(Responsavel.nome_responsavel.ilike(f"%{nome}%"))
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()


@router.get("/{nis}", response_model = ResponsavelListResponse)
async def buscar_responsavel(nis: str, db: AsyncSession = Depends(get_session)):
    """Busca um responsável específico por NIS."""
    async with db as session:
        query = select(Responsavel).filter(Responsavel.nis_responsavel == nis)
        result = await session.execute(query)
        responsavel = result.scalar_one_or_none()
        if not responsavel:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND, 
                detail = f"Responsável {nis} não encontrado"
            )
        return responsavel
