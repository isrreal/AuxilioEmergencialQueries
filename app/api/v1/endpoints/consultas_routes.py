from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, distinct, text

from app.models.models import Beneficiario, Auxilio, Responsavel
from app.schemas.schemas import (
    BeneficiarioListResponse,
    ContagemResponse,
    BeneficiarioResponsavelResponse,
)
from app.core.deps import get_session

router: APIRouter = APIRouter()

# ===================================================================
# 1. ROTAS DE GERENCIAMENTO DE ÍNDICES (SETUP)
# ===================================================================

# ===================================================================
# 1️⃣ Gasto total por UF
# ===================================================================
@router.post("/setup/gasto-uf/criar-indices", tags=["Setup"])
async def criar_indices_gasto_uf(db: AsyncSession = Depends(get_session)):
    """
    Cria índices para otimizar a soma de Auxilio.valor por Beneficiario.uf.
    """
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_uf_nis 
            ON beneficiario(uf, nis_beneficiario);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis_valor 
            ON auxilio(nis_beneficiario, valor);
        """))
        await session.commit()
    return {"status": "Índices para gasto por UF criados."}

@router.post("/setup/gasto-uf/apagar-indices", tags=["Setup"])
async def apagar_indices_gasto_uf(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_uf_nis;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis_valor;"))
        await session.commit()
    return {"status": "Índices para gasto por UF apagados."}


# ===================================================================
# 2️⃣ Contagem por Município (texto%)
# ===================================================================
@router.post("/setup/contagem-municipio/criar-indices", tags=["Setup"])
async def criar_indices_contagem_municipio(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_municipio_trgm
            ON beneficiario USING gin (municipio gin_trgm_ops);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_uf
            ON beneficiario (uf);
        """))
        await session.commit()
    return {"status": "Índices para contagem por município criados."}


@router.post("/setup/contagem-municipio/apagar-indices", tags=["Setup"])
async def apagar_indices_contagem_municipio(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_municipio_trgm;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_uf;"))
        await session.commit()
    return {"status": "Índices para contagem por município apagados."}


# ===================================================================
# 3️⃣ Busca por Nome
# ===================================================================
@router.post("/setup/por-nome/criar-indices", tags=["Setup"])
async def criar_indices_por_nome(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_nome_pattern
            ON beneficiario(nome_beneficiario text_pattern_ops);
        """))
        await session.commit()
    return {"status": "Índice para busca por nome criado."}

@router.post("/setup/por-nome/apagar-indices", tags=["Setup"])
async def apagar_indices_por_nome(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_nome_pattern;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_nome_uf;"))
        await session.commit()
    return {"status": "Índice para busca por nome apagado."}


# ===================================================================
# 4️⃣ Beneficiários com múltiplas parcelas
# ===================================================================
@router.post("/setup/multiplas-parcelas/criar-indices", tags=["Setup"])
async def criar_indices_multiplas_parcelas(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis_parcela
            ON auxilio(nis_beneficiario, parcela);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_uf_nis
            ON beneficiario(uf, nis_beneficiario);
        """))
        await session.commit()
    return {"status": "Índices para múltiplas parcelas criados."}

@router.post("/setup/multiplas-parcelas/apagar-indices", tags=["Setup"])
async def apagar_indices_multiplas_parcelas(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis_parcela;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_uf_nis;"))
        await session.commit()
    return {"status": "Índices para múltiplas parcelas apagados."}


# ===================================================================
# 5️⃣ Beneficiários que também são responsáveis
# ===================================================================
@router.post("/setup/beneficiarios-responsaveis/criar-indices", tags=["Setup"])
async def criar_indices_beneficiarios_responsaveis(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_uf
            ON beneficiario(uf);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_nis_beneficiario
            ON beneficiario(nis_beneficiario);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis_beneficiario
            ON auxilio(nis_beneficiario);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis_responsavel
            ON auxilio(nis_responsavel);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_responsavel_nis_responsavel
            ON responsavel(nis_responsavel);
        """))
        await session.commit()
    return {"status": "Índices para beneficiários-responsáveis criados."}


@router.post("/setup/beneficiarios-responsaveis/apagar-indices", tags=["Setup"])
async def apagar_indices_beneficiarios_responsaveis(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_uf;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_nis_beneficiario;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis_beneficiario;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis_responsavel;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_responsavel_nis_responsavel;"))
        await session.commit()
    return {"status": "Índices para beneficiários-responsáveis apagados."}


# ===================================================================
# 2. ROTAS DE EXECUÇÃO DE CONSULTAS (BENCHMARK)
# ===================================================================

@router.get('/executar/total-gasto-por-uf', tags=["Executar"])
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


@router.get('/executar/quantidade-beneficiarios-municipio', response_model=ContagemResponse, tags=["Executar"])
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


@router.get('/executar/beneficiarios-responsaveis', response_model=List[BeneficiarioResponsavelResponse], tags=["Executar"])
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


@router.get('/executar/beneficiarios-multiplas-parcelas', response_model=List[BeneficiarioListResponse], tags=["Executar"])
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


@router.get('/executar/beneficiarios-por-nome', response_model=List[BeneficiarioListResponse], tags=["Executar"])
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


@router.get('/executar/listar-beneficiarios', response_model=List[BeneficiarioListResponse], tags=["Executar"])
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


@router.get('/executar/buscar-beneficiario/{nis}', response_model=BeneficiarioListResponse, tags=["Executar"])
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