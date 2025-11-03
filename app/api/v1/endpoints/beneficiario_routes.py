from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.models import Beneficiario
from app.schemas.schemas import BeneficiarioListResponse
from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.get("/")
async def listar_beneficiarios(
    nome: Optional[str] = None,
    uf: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = 1000,
    db: AsyncSession = Depends(get_session)
):
    query = select(Beneficiario)

    if nome:
        query = query.filter(Beneficiario.nome_beneficiario.ilike(f"{nome}%"))
    if uf:
        query = query.filter(Beneficiario.uf == uf)
    if municipio:
        query = query.filter(Beneficiario.municipio.ilike(f"%{municipio}%"))

    query = query.order_by(Beneficiario.nis_beneficiario).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()
    return rows


@router.get('/{nis}', response_model = BeneficiarioListResponse)
async def buscar_beneficiario(
    nis: str,
    db: AsyncSession = Depends(get_session)
):
    """Busca um beneficiário específico por NIS."""
    async with db as session:
        query = select(Beneficiario).filter(Beneficiario.nis_beneficiario == nis)
        result = await session.execute(query)
        beneficiario = result.scalar_one_or_none()
        
        if not beneficiario:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Beneficiário com NIS {nis} não encontrado"
            )
        
        return beneficiario
    