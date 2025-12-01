from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, distinct

from app.models.models import Beneficiario, Auxilio, Responsavel
from app.schemas.schemas import BeneficiarioListResponse, ContagemResponse
from app.core.deps import get_session

from app.utils.utils import (
    stream_json_array,
    stream_ndjson,
    create_streaming_response
)

router: APIRouter = APIRouter()

# ===================================================================
# ROTAS DE AGREGAÇÃO (SEM STREAMING)
# ===================================================================

@router.get('/total-gasto-por-uf')
async def total_gasto_por_uf(
    uf: str = Query(min_length = 2, max_length = 2, description = "Sigla da UF"),
    db: AsyncSession = Depends(get_session)
):
    """Retorna soma total gasta por UF."""
    query = (
        select(func.sum(Auxilio.valor))
        .join(Beneficiario, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
        .filter(Beneficiario.uf == uf.upper())
    )
    result = await db.execute(query)
    total = result.scalar_one_or_none()
    
    return {"uf": uf.upper(), "total": float(total or 0.0)}


@router.get('/beneficiarios-por-municipio', response_model = ContagemResponse)
async def beneficiarios_por_municipio(
    uf: str = Query(min_length = 2, max_length = 2),
    municipio: str = Query(min_length = 1),
    db: AsyncSession = Depends(get_session)
):
    """Retorna contagem de beneficiários por município."""
    query = (
        select(func.count(distinct(Beneficiario.nis_beneficiario)))
        .filter(Beneficiario.uf == uf.upper())
        .filter(Beneficiario.municipio.ilike(f"%{municipio.upper()}%"))
    )
    result = await db.execute(query)
    quantidade = result.scalar_one_or_none()
    
    return ContagemResponse(quantidade = quantidade or 0)


# ===================================================================
# ROTAS COM STREAMING
# ===================================================================

@router.get("/beneficiarios-responsaveis")
async def beneficiarios_responsaveis(
    uf: str = Query(min_length = 2, max_length = 2),
    formato: str = Query("json", regex = "^(json|ndjson)$"),
    db: AsyncSession = Depends(get_session)
):
    """Streama beneficiários que também são responsáveis."""
    async def stream_query():
        stream = await db.stream(
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
            .execution_options(yield_per = 1000)
        )

        stream_func = stream_ndjson if formato == "ndjson" else stream_json_array
        async for chunk in stream_func(stream):
            yield chunk

    return create_streaming_response(stream_query, formato)


@router.get('/beneficiarios-multiplas-parcelas')
async def beneficiarios_multiplas_parcelas(
    uf: str = Query(min_length = 2, max_length = 2),
    min_parcela: int = Query(1, ge = 1),
    formato: str = Query("json", regex = "^(json|ndjson)$"),
    stream: bool = Query(True, description = "Se False, retorna paginado"),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 1000),
    db: AsyncSession = Depends(get_session)
):
    """
    Busca beneficiários com parcelas > min_parcela.
    - stream=True: retorna todos os dados em streaming
    - stream=False: retorna dados paginados
    """
    base_query = (
        select(Beneficiario)
        .join(Auxilio, Beneficiario.nis_beneficiario == Auxilio.nis_beneficiario)
        .filter(Auxilio.parcela > min_parcela)
        .filter(Beneficiario.uf == uf.upper())
        .distinct()
    )
    
    if not stream:
        # Versão paginada
        query = base_query.offset(skip).limit(limit)
        result = await db.execute(query)
        beneficiarios = result.scalars().all()
        
        if not beneficiarios:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Nenhum beneficiário com parcela > {min_parcela} na UF {uf}"
            )
        
        return beneficiarios
    
    # Versão streaming
    async def stream_query():
        stream_result = await db.stream(
            base_query.execution_options(yield_per = 500)
        )
        stream_func = stream_ndjson if formato == "ndjson" else stream_json_array
        async for chunk in stream_func(stream_result):
            yield chunk

    return create_streaming_response(stream_query, formato)


@router.get('/beneficiarios-por-nome')
async def beneficiarios_por_nome(
    nome: str = Query(min_length = 2),
    formato: str = Query("json", regex = "^(json|ndjson)$"),
    stream: bool = Query(True),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 1000),
    db: AsyncSession = Depends(get_session)
):
    """
    Busca beneficiários por substring do nome.
    - stream=True: streaming completo
    - stream=False: paginado
    """
    base_query = (
        select(Beneficiario)
        .filter(Beneficiario.nome_beneficiario.ilike(f"%{nome.upper()}%"))
        .distinct()
    )
    
    if not stream:
        query = base_query.offset(skip).limit(limit)
        result = await db.execute(query)
        beneficiarios = result.scalars().all()
        
        if not beneficiarios:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = f"Nenhum beneficiário com nome contendo '{nome}'"
            )
        
        return beneficiarios
    
    async def stream_query():
        stream_result = await db.stream(
            base_query.execution_options(yield_per = 500)
        )
        stream_func = stream_ndjson if formato == "ndjson" else stream_json_array
        async for chunk in stream_func(stream_result):
            yield chunk

    return create_streaming_response(stream_query, formato)


@router.get('/listar-beneficiarios')
async def listar_beneficiarios(
    nome: str | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    formato: str = Query("json", regex = "^(json|ndjson)$"),
    stream: bool = Query(True),
    skip: int = Query(0, ge = 0),
    limit: int = Query(1000, ge = 1, le = 5000),
    db: AsyncSession = Depends(get_session)
):
    """
    Lista beneficiários com filtros opcionais.
    - stream=True: streaming completo
    - stream=False: paginado
    """
    query = select(Beneficiario)

    if nome:
        query = query.filter(Beneficiario.nome_beneficiario.ilike(f"{nome.upper()}%"))
    if uf:
        query = query.filter(Beneficiario.uf == uf.upper())
    if municipio:
        query = query.filter(Beneficiario.municipio.ilike(f"{municipio.upper()}%"))

    query = query.order_by(Beneficiario.nis_beneficiario)
    
    if not stream:
        result = await db.execute(query.offset(skip).limit(limit))
        return result.scalars().all()
    
    async def stream_query():
        stream_result = await db.stream(
            query.execution_options(yield_per = 1000)
        )
        stream_func = stream_ndjson if formato == "ndjson" else stream_json_array
        async for chunk in stream_func(stream_result):
            yield chunk

    return create_streaming_response(stream_query, formato)


@router.get('/beneficiario/{nis}', response_model = BeneficiarioListResponse)
async def buscar_beneficiario(
    nis: str,
    db: AsyncSession = Depends(get_session)
):
    """Busca beneficiário por NIS (chave primária)."""
    query = select(Beneficiario).filter(Beneficiario.nis_beneficiario == nis)
    result = await db.execute(query)
    beneficiario = result.scalar_one_or_none()
    
    if not beneficiario:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = f"Beneficiário com NIS {nis} não encontrado"
        )
    
    return beneficiario