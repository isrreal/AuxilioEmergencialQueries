from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import Beneficiario, Auxilio
from app.schemas.schemas import BeneficiarioListResponse
from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.get("/", response_model = List[BeneficiarioListResponse])
async def listar_beneficiarios(
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    uf: Optional[str] = Query(None, max_length = 2),
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
            query = query.filter(Beneficiario.municipio.ilike(f"%{municipio}%"))
        if nome:
            query = query.filter(Beneficiario.nome_beneficiario.ilike(f"%{nome}%"))

        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        beneficiarios = result.scalars().all()
        return beneficiarios


@router.get("/{nis}", response_model=BeneficiarioListResponse)
async def buscar_beneficiario(nis: str, db: AsyncSession = Depends(get_session)):
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


@router.get("/consulta/por-parcela-e-uf", response_model = List[BeneficiarioListResponse])
async def beneficiarios_por_parcela_e_uf(
    uf: str = Query(..., min_length = 2, max_length = 2),
    min_parcela: int = Query(ge = 0),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """Lista beneficiários com número de parcela maior que o valor informado em uma UF."""
    async with db as session:
        query = (
            select(Beneficiario)
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Beneficiario.uf == uf.upper())
            .filter(Auxilio.parcela > min_parcela)
            .distinct()
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(query)
        beneficiarios = result.scalars().all()

        if not beneficiarios:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = "Nenhum beneficiário encontrado."
            )
        return beneficiarios
