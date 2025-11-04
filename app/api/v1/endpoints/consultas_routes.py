from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, distinct, text

from app.models.models import Beneficiario, Auxilio, Responsavel, Usuario
from app.schemas.schemas import (
    BeneficiarioListResponse,
    ContagemResponse,
    BeneficiarioResponsavelResponse,
)
from app.core.deps import get_session

router: APIRouter = APIRouter()

# ===================================================================
# 2. ROTAS DE EXECUÇÃO DE CONSULTAS (BENCHMARK)
# ===================================================================

@router.get('/executar/total-gasto-por-uf')
async def executar_total_gasto_por_uf(
    uf: str = Query("CE", min_length = 2, max_length = 2),
    db: AsyncSession = Depends(get_session)
):
    """Executa a consulta de soma de gastos por UF."""
    async with db as session:
        query = (
            select(func.sum(Auxilio.valor))
            .join(Beneficiario, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Beneficiario.uf == uf.upper())
        )
        result = await session.execute(query)
        total = result.scalar_one_or_none()
        return {"total": total or 0.0}


@router.get(
    '/executar/quantidade-beneficiarios-municipio', 
    response_model = ContagemResponse
)
async def executar_quantidade_beneficiarios_municipio(
    uf: str = Query(min_length = 2, max_length = 2),
    municipio: str = Query(),
    db: AsyncSession = Depends(get_session)
):
    """Executa a consulta de contagem por município."""
    async with db as session:
        query = (
            select(func.count(distinct(Beneficiario.nis_beneficiario)).label("quantidade"))
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Beneficiario.uf == uf.upper())
            .filter(Beneficiario.municipio.ilike(f"{municipio.upper()}%"))
        )
        result = await session.execute(query)
        quantidade = result.scalar_one_or_none()
        return ContagemResponse(quantidade = quantidade or 0)


@router.get(
    '/executar/beneficiarios-responsaveis', 
    response_model = List[BeneficiarioResponsavelResponse]
)
async def executar_beneficiarios_que_sao_responsaveis(
    uf: str = Query(min_length = 2, max_length = 2),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """Executa a consulta por beneficiários que também são responsáveis."""
    async with db as session:
        query = (
            select(
                Beneficiario.nome_beneficiario,
                Beneficiario.cpf_beneficiario,
                Beneficiario.municipio,
                Beneficiario.uf,
                Responsavel.nis_responsavel
            )
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .join(Responsavel, Auxilio.nis_beneficiario == Responsavel.nis_responsavel)
            .filter(Beneficiario.uf == uf.upper())
            .filter(Beneficiario.nis_beneficiario == Responsavel.nis_responsavel)
            .distinct() 
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(query)
        registros = result.all()
        
        if not registros:
            raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = f"Nenhum beneficiário-responsável encontrado na UF {uf}")
        
        return [r._asdict() for r in registros]


@router.get(
    '/executar/beneficiarios-multiplas-parcelas', 
    response_model = List[BeneficiarioListResponse]
)
async def executar_beneficiarios_multiplas_parcelas(
    uf: str = Query(min_length = 2, max_length = 2),
    min_parcela: int = Query(1, ge = 1),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """Executa a consulta por beneficiários com parcelas > min_parcela."""
    async with db as session:
        query = (
            select(Beneficiario)
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Auxilio.parcela > min_parcela)
            .filter(Beneficiario.uf == uf.upper())
            .distinct()
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(query)
        beneficiarios = result.scalars().all()
        
        if not beneficiarios:
            raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = f"Nenhum beneficiário encontrado com parcela > {min_parcela} na UF {uf}")
        
        return beneficiarios


@router.get(
    '/executar/beneficiarios-por-nome', 
    response_model = List[BeneficiarioListResponse]
)
async def executar_beneficiarios_por_nome(
    nome: str = Query(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """Executa a consulta por nome (com 'NOME%')."""
    async with db as session:
        query = (
            select(Beneficiario)
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Beneficiario.nome_beneficiario.ilike(f"{nome.upper()}%"))
            .distinct()
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(query)
        beneficiarios = result.scalars().all()
        
        if not beneficiarios:
            raise HTTPException(status_code = status.HTTP_404_NOT_FOUND, detail = f"Nenhum beneficiário encontrado com nome iniciando em '{nome}'")
        
        return beneficiarios


@router.get(
    '/executar/listar-beneficiarios', 
    response_model = List[BeneficiarioListResponse]
)
async def executar_listar_beneficiarios(
    nome: Optional[str] = None,
    uf: Optional[str] = None,
    municipio: Optional[str] = None,
    limit: int = 1000,
    db: AsyncSession = Depends(get_session)
):
    """Executa a consulta de listagem geral com filtros opcionais."""
    async with db as session: 
        query = select(Beneficiario)

        if nome:
            query = query.filter(Beneficiario.nome_beneficiario.ilike(f"{nome.upper()}%"))
        if uf:
            query = query.filter(Beneficiario.uf == uf.upper())
        if municipio:
            query = query.filter(Beneficiario.municipio.ilike(f"{municipio.upper()}%"))

        query = query.order_by(Beneficiario.nis_beneficiario).limit(limit)
        result = await session.execute(query)
        rows = result.scalars().all()
        return rows


@router.get(
    '/executar/buscar-beneficiario/{nis}', 
    response_model = BeneficiarioListResponse
)
async def executar_buscar_beneficiario(
    nis: str,
    db: AsyncSession = Depends(get_session)
):
    """Executa a busca de um beneficiário por NIS (Chave Primária)."""
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