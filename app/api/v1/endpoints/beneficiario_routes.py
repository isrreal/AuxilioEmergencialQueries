from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.models import Beneficiario
from app.schemas.schemas import BeneficiarioListResponse
from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.get('/', response_model = List[BeneficiarioListResponse])
async def listar_beneficiarios(
    uf: Optional[str] = Query(max_length = 2),
    municipio: Optional[str] = Query(None),
    nome: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session)
):
    """Lista beneficiários com filtros opcionais."""
    async with db as session:
        query = select(Beneficiario)
        
        if uf:
            query = query.filter(Beneficiario.uf == uf.upper())
        if municipio:
            query = query.filter(Beneficiario.municipio.ilike(f'%{municipio}%'))
        if nome:
            query = query.filter(Beneficiario.nome_beneficiario.ilike(f'%{nome}%'))
                
        result = await session.execute(query)
        beneficiarios = result.scalars().all()
        return beneficiarios

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
    