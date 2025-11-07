from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.post("/beneficiarios-responsaveis/criar-indices")
async def criar_indices_beneficiarios_responsaveis(db: AsyncSession = Depends(get_session)):
    """
    Cria apenas os índices necessários que não são criados automaticamente.
    PKs e FKs já têm índices automáticos no PostgreSQL.
    """
    async with db as session:
        # Índice para filtro por UF (já definido no model com index=True)
        # await session.execute(text("CREATE INDEX IF NOT EXISTS idx_beneficiario_uf ON beneficiario(uf);"))
        
        # Índice composto para JOIN comum
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis_parcela 
            ON auxilio(nis_beneficiario, parcela);
        """))
        
        await session.commit()
    
    return {"status": "Índices criados"}


@router.post("/beneficiarios-responsaveis/apagar-indices")
async def apagar_indices_beneficiarios_responsaveis(db: AsyncSession = Depends(get_session)):
    """Remove índices customizados (mantém PKs e FKs)"""
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_uf;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis_parcela;"))
        await session.commit()
    
    return {"status": "Índices removidos"}


# ===================================================================
# EXEMPLO: Setup para outros cenários
# ===================================================================

@router.post("/gasto-uf/criar-indices")
async def criar_indices_gasto_uf(db: AsyncSession = Depends(get_session)):
    """Índices para query de gasto por UF"""
    async with db as session:
        # UF já tem índice no model
        # Valor para agregação SUM
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_valor 
            ON auxilio(valor) WHERE valor IS NOT NULL;
        """))
        await session.commit()
    
    return {"status": "Índices para gasto-uf criados"}


@router.post("/gasto-uf/apagar-indices")
async def apagar_indices_gasto_uf(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_valor;"))
        await session.commit()
    
    return {"status": "Índices removidos"}


@router.post("/por-nome/criar-indices")
async def criar_indices_por_nome(db: AsyncSession = Depends(get_session)):
    """Índices para busca por nome (ILIKE)"""
    async with db as session:
        # B-Tree para ILIKE 'termo%'
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_nome 
            ON beneficiario(nome_beneficiario text_pattern_ops);
        """))
        await session.commit()
    
    return {"status": "Índices para busca por nome criados"}


@router.post("/por-nome/apagar-indices")
async def apagar_indices_por_nome(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_nome;"))
        await session.commit()
    
    return {"status": "Índices removidos"}


@router.post("/contagem-municipio/criar-indices")
async def criar_indices_contagem_municipio(db: AsyncSession = Depends(get_session)):
    """Índices para busca fuzzy em município"""
    async with db as session:
        # Extensão pg_trgm para ILIKE '%termo%'
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_municipio_trgm 
            ON beneficiario USING gin(municipio gin_trgm_ops);
        """))
        await session.commit()
    
    return {"status": "Índices GIN/TRGM criados"}


@router.post("/contagem-municipio/apagar-indices")
async def apagar_indices_contagem_municipio(db: AsyncSession = Depends(get_session)):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_municipio_trgm;"))
        await session.commit()
    
    return {"status": "Índices removidos"}