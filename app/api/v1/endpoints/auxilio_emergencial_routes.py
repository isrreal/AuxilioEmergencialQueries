from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func 

from app.models.models import Responsavel, Beneficiario, Auxilio
from app.schemas.schemas import (
    AuxilioListResponse, 
    BeneficiarioListResponse, 
    ResponsavelListResponse,
    TotalGastoResponse
)

from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.get('/beneficiarios', response_model = List[BeneficiarioListResponse])
async def listar_beneficiarios(
    skip: int = Query(0, ge = 0, description = "Número de registros a pular"),
    limit: int = Query(100, ge = 1, le = 500, description = "Máximo de registros"),
    uf: Optional[str] = Query(None, max_length = 2, description = "Filtrar por UF"),
    municipio: Optional[str] = Query(None, description = "Filtrar por município"),
    nome: Optional[str] = Query(None, description = "Buscar por nome (parcial)"),
    db: AsyncSession = Depends(get_session)
):
    """
    Lista beneficiários com filtros opcionais.
    (Esta rota já cobre a "Busca por nome" do seu script ipywidgets)
    """
    async with db as session:
        query = select(Beneficiario)
        
        if uf:
            query = query.filter(Beneficiario.uf == uf.upper())
        if municipio:
            query = query.filter(Beneficiario.municipio.ilike(f'%{municipio}%'))
        if nome:
            query = query.filter(Beneficiario.nome_beneficiario.ilike(f'%{nome}%'))
        
        query = query.offset(skip).limit(limit)
        
        result = await session.execute(query)
        beneficiarios = result.scalars().all()
        return beneficiarios

@router.get('/responsaveis', response_model = List[ResponsavelListResponse])
async def listar_responsaveis(
    skip: int = Query(0, ge = 0, description = "Número de registros a pular"),
    limit: int = Query(100, ge = 1, le = 500, description = "Máximo de registros"),
    nome: Optional[str] = Query(None, description = "Buscar por nome (parcial)"),
    db: AsyncSession = Depends(get_session)
):
    """Lista responsáveis com filtros opcionais."""
    async with db as session:
        query = select(Responsavel)
        
        if nome:
            query = query.filter(Responsavel.nome_responsavel.ilike(f'%{nome}%'))
        
        query = query.offset(skip).limit(limit)
        
        result = await session.execute(query)
        responsaveis = result.scalars().all()
        return responsaveis


@router.get('/auxilios', response_model = List[AuxilioListResponse])
async def listar_auxilios(
    limit: int = Query(100, ge = 1, le = 1000), 
    offset: int = Query(0, ge = 0),
    db: AsyncSession = Depends(get_session)
):
    """Retorna todos os auxílios com paginação"""
    async with db as session:
        query = select(Auxilio).limit(limit).offset(offset)
        result = await session.execute(query)
        auxilios = result.scalars().all()
        
        if not auxilios:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = "Nenhum auxílio encontrado"
            )
        
        return auxilios


@router.get('/beneficiarios/{nis}', response_model = BeneficiarioListResponse)
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


@router.get('/responsaveis/{nis}', response_model = ResponsavelListResponse)
async def buscar_responsavel(
    nis: str,
    db: AsyncSession = Depends(get_session)
):
    """Busca um responsável específico por NIS."""
    async with db as session:
        query = select(Responsavel).filter(Responsavel.nis_responsavel == nis)
        result = await session.execute(query)
        responsavel = result.scalar_one_or_none()
        
        if not responsavel:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Responsável com NIS {nis} não encontrado"
            )
        
        return responsavel


@router.get('/beneficiarios/consulta/por-parcela-e-uf', response_model = List[BeneficiarioListResponse])
async def beneficiarios_por_parcela_e_uf(
    uf: str = Query(min_length = 2, max_length = 2, description = "Unidade Federal (ex: CE)"),
    min_parcela: int = Query(ge = 0, description = "Número mínimo da parcela (ex: 1 para > 1)"),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """
    Lista beneficiários que possuem auxílios com número de parcela MAIOR que o
    valor informado, em uma UF específica.
    (Baseado em 'quantidade_de_parcelas_em_uf')
    """
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
                detail = "Nenhum beneficiário encontrado com esses critérios."
            )
        
        return beneficiarios


@router.get('/estatisticas/total-gasto-por-uf', response_model = TotalGastoResponse)
async def total_gasto_por_uf(
    uf: str = Query(min_length = 2, max_length = 2, description = "Unidade Federal (ex: CE)"),
    db: AsyncSession = Depends(get_session)
):
    """
    Retorna o valor total gasto (SUM) em auxílios para uma UF específica.
    (Baseado em 'seleciona_uf')
    """
    async with db as session:
        query = (
            select(func.sum(Auxilio.valor).label("total"))
            .join(Beneficiario, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Beneficiario.uf == uf.upper())
        )
        
        result = await session.execute(query)
        total_gasto = result.scalar_one_or_none()
        
        return TotalGastoResponse(total = total_gasto or 0.0)


@router.get('/estatisticas/total-gasto-por-mes', response_model = TotalGastoResponse)
async def total_gasto_por_mes(
    ano_mes: str = Query(min_length = 6, max_length = 6, regex = r"^\d{6}$", 
                         description = "Ano e Mês no formato YYYYMM (ex: 202004)"),
    db: AsyncSession = Depends(get_session)
):
    """
    Retorna o valor total gasto (SUM) em auxílios em um mês/ano específico.
    (Baseado em 'montante_gasto_em_data_especifica')
    """
    async with db as session:
        query = (
            select(func.sum(Auxilio.valor).label("total"))
            .filter(Auxilio.ano_mes == ano_mes)
        )
        
        result = await session.execute(query)
        total_gasto = result.scalar_one_or_none()
        
        return TotalGastoResponse(total = total_gasto or 0.0)