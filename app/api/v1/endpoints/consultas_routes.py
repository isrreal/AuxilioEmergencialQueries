from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, distinct

from app.models.models import Beneficiario, Auxilio, Responsavel
from app.schemas.schemas import (
    BeneficiarioListResponse,
    BeneficiarioComValorResponse,
    TotalGastoResponse, 
    ContagemResponse,
    BeneficiarioResponsavelResponse,
)

from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.get('/beneficiarios-por-valor', response_model = List[BeneficiarioComValorResponse])
async def beneficiarios_por_valor(
    valor: float = Query(description = "Valor do auxílio (ex: 600)"),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """
    Beneficiários que receberam um valor específico de auxílio.
    Equivalente à consulta SQL com valor = 600.
    """
    async with db as session:
        query = (
            select(
                Beneficiario.nome_beneficiario,
                Beneficiario.cpf_beneficiario,
                Beneficiario.municipio,
                Beneficiario.uf,
                Auxilio.valor
            )
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Auxilio.valor == valor)
            .group_by(
                Beneficiario.nome_beneficiario,
                Beneficiario.cpf_beneficiario,
                Beneficiario.municipio,
                Beneficiario.uf,
                Auxilio.valor
            )
            .order_by(Beneficiario.nome_beneficiario)
            .offset(skip)
            .limit(limit)
        )
        
        result = await session.execute(query)
        beneficiarios = result.all()
        
        if not beneficiarios:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Nenhum beneficiário encontrado com valor {valor}"
            )
        
        return [
            {
                "nome": b.nome_beneficiario,
                "cpf": b.cpf_beneficiario,
                "municipio": b.municipio,
                "estado": b.uf,
                "valor": b.valor
            }
            for b in beneficiarios
        ]


@router.get('/total-gasto-por-uf', response_model = TotalGastoResponse)
async def total_gasto_por_uf(
    uf: str = Query(min_length = 2, max_length = 2, description = "UF (ex: CE)"),
    db: AsyncSession = Depends(get_session)
):
    """
    Gasto total do governo com o auxílio emergencial em uma UF específica.
    Exemplo: Gasto total no estado do Ceará.
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


@router.get('/quantidade-beneficiarios-municipio', response_model = ContagemResponse)
async def quantidade_beneficiarios_municipio(
    uf: str = Query(min_length = 2, max_length = 2, description = "UF (ex: CE)"),
    municipio: str = Query(description = "Nome do município (ex: Quixadá)"),
    db: AsyncSession = Depends(get_session)
):
    """
    Quantidade de beneficiários em um município específico.
    Exemplo: Quantidade de beneficiários no município de Quixadá.
    """
    async with db as session:
        query = (
            select(func.count(distinct(Beneficiario.nis_beneficiario)).label("quantidade"))
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Beneficiario.uf == uf.upper())
            .filter(Beneficiario.municipio.ilike(f'%{municipio}%'))
        )
        
        result = await session.execute(query)
        quantidade = result.scalar_one_or_none()
        
        return ContagemResponse(quantidade = quantidade or 0)


@router.get('/beneficiarios-responsaveis', response_model = List[BeneficiarioResponsavelResponse])
async def beneficiarios_que_sao_responsaveis(
    uf: str = Query(min_length = 2, max_length = 2, description = "UF (ex: CE)"),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """
    Beneficiários que são responsáveis concomitantes em uma UF.
    Retorna beneficiários que também aparecem como responsáveis.
    """
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
            .join(Responsavel, Auxilio.nis_responsavel == Responsavel.nis_responsavel)
            .filter(Beneficiario.uf == uf.upper())
            .offset(skip)
            .limit(limit)
        )
        
        result = await session.execute(query)
        registros = result.all()
        
        if not registros:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Nenhum beneficiário-responsável encontrado na UF {uf}"
            )
        
        return [
            {
                "nome_beneficiario": r.nome_beneficiario,
                "cpf_beneficiario": r.cpf_beneficiario,
                "municipio": r.municipio,
                "uf": r.uf,
                "nis_responsavel": r.nis_responsavel
            }
            for r in registros
        ]


@router.get('/beneficiarios-multiplas-parcelas', response_model = List[BeneficiarioListResponse])
async def beneficiarios_multiplas_parcelas(
    uf: str = Query(min_length = 2, max_length = 2, description = "UF (ex: CE)"),
    min_parcela: int = Query(1, ge = 1, description="Número mínimo de parcelas"),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """
    Beneficiários que receberam mais que uma parcela em uma UF específica.
    Exemplo: Beneficiários que receberam mais de 1 parcela no Ceará.
    """
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
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Nenhum beneficiário encontrado na UF {uf} com mais de {min_parcela} parcela(s)"
            )
        
        return beneficiarios


@router.get('/beneficiarios-por-nome', response_model = List[BeneficiarioListResponse])
async def beneficiarios_por_nome(
    nome: str = Query(description = "Nome ou parte do nome (ex: ISRAEL)"),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: AsyncSession = Depends(get_session)
):
    """
    Beneficiários que têm determinado nome.
    Exemplo: Beneficiários com nome "ISRAEL".
    """
    async with db as session:
        query = (
            select(Beneficiario)
            .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Beneficiario.nome_beneficiario.ilike(f'{nome}%'))
            .distinct()
            .offset(skip)
            .limit(limit)
        )
        
        result = await session.execute(query)
        beneficiarios = result.scalars().all()
        
        if not beneficiarios:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Nenhum beneficiário encontrado com o nome '{nome}'"
            )
        
        return beneficiarios


@router.get('/total-gasto-por-mes', response_model = TotalGastoResponse)
async def total_gasto_por_mes(
    ano_mes: str = Query(min_length = 6, max_length = 6, regex = r"^\d{6}$", 
                         description = "Ano e Mês no formato YYYYMM (ex: 202007)"),
    db: AsyncSession = Depends(get_session)
):
    """
    Montante gasto pelo governo em um mês específico em toda a nação.
    Exemplo: Montante gasto em julho de 2020 (202007).
    """
    async with db as session:
        query = (
            select(func.sum(Auxilio.valor).label("total"))
            .join(Beneficiario, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
            .filter(Auxilio.ano_mes == ano_mes)
        )
        
        result = await session.execute(query)
        total_gasto = result.scalar_one_or_none()
        
        return TotalGastoResponse(total = total_gasto or 0.0)