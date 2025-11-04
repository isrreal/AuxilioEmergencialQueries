from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.models import Usuario

from app.core.deps import get_session, get_current_user

router: APIRouter = APIRouter()

# ============================================================
# 1️⃣ Índices para gasto por UF
# ============================================================
@router.post("/gasto-uf/criar-indices")
async def criar_indices_gasto_uf(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user) 
):
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_uf 
            ON beneficiario(uf);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis 
            ON auxilio(nis_beneficiario);
        """))
        await session.commit()
    return {"status": "Índices para gasto por UF criados."}


@router.post("/gasto-uf/apagar-indices")
async def apagar_indices_gasto_uf(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_uf;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis;"))
        await session.commit()
    return {"status": "Índices para gasto por UF apagados."}


# ============================================================
# 2️⃣ Índices para contagem por município (texto%)
# ============================================================
@router.post("/contagem-municipio/criar-indices")
async def criar_indices_contagem_municipio(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)
):
    async with db as session:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_municipio_trgm
            ON beneficiario USING gin (municipio gin_trgm_ops);
        """))
        await session.commit()
    return {"status": "Índices para contagem por município criados."}


@router.post("/contagem-municipio/apagar-indices")
async def apagar_indices_contagem_municipio(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_municipio_trgm;"))
        await session.commit()
    return {"status": "Índices para contagem por município apagados."}


# ============================================================
# 3️⃣ Índices para busca por nome
# ============================================================
@router.post("/por-nome/criar-indices")
async def criar_indices_por_nome(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_beneficiario_nome_trgm
            ON beneficiario USING gin (nome_beneficiario gin_trgm_ops);
        """))
        await session.commit()
    return {"status": "Índice para busca por nome criado."}


@router.post("/por-nome/apagar-indices")
async def apagar_indices_por_nome(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_beneficiario_nome_trgm;"))
        await session.commit()
    return {"status": "Índice para busca por nome apagado."}


# ============================================================
# 4️⃣ Índices para beneficiários com múltiplas parcelas
# ============================================================
@router.post("/multiplas-parcelas/criar-indices")
async def criar_indices_multiplas_parcelas(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis_parcela
            ON auxilio(nis_beneficiario, parcela);
        """))
        await session.commit()
    return {"status": "Índices para múltiplas parcelas criados."}


@router.post("/multiplas-parcelas/apagar-indices")
async def apagar_indices_multiplas_parcelas(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis_parcela;"))
        await session.commit()
    return {"status": "Índices para múltiplas parcelas apagados."}


# ============================================================
# 5️⃣ Índices para beneficiários que também são responsáveis
# ============================================================
@router.post("/beneficiarios-responsaveis/criar-indices")
async def criar_indices_beneficiarios_responsaveis(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_auxilio_nis_responsaveis
            ON auxilio(nis_beneficiario);
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_responsavel_nis
            ON responsavel(nis_responsavel);
        """))
        await session.commit()
    return {"status": "Índices para beneficiários-responsáveis criados."}


@router.post("/beneficiarios-responsaveis/apagar-indices")
async def apagar_indices_beneficiarios_responsaveis(
    db: AsyncSession = Depends(get_session),
    usuario_logado: Usuario = Depends(get_current_user)  
):
    async with db as session:
        await session.execute(text("DROP INDEX IF EXISTS idx_auxilio_nis_responsaveis;"))
        await session.execute(text("DROP INDEX IF EXISTS idx_responsavel_nis;"))
        await session.commit()
    return {"status": "Índices para beneficiários-responsáveis apagados."}
