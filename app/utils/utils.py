import json

from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def serialize_row(row) -> dict:
    """Serializa uma row do SQLAlchemy para dict."""
    if hasattr(row, '__dict__'):
        return {k: v for k, v in row.__dict__.items() if not k.startswith('_')}
    return row._asdict() if hasattr(row, '_asdict') else dict(row._mapping)


async def stream_json_array(query_stream):
    """Streaming de arrays JSON com yield_per() para controlar buffer."""
    yield b'['
    first = True
    
    async for row in query_stream:
        if not first:
            yield b','
        first = False
        
        data = serialize_row(row)
        yield json.dumps(data, default = str).encode('utf-8')
    
    yield b']'


async def stream_ndjson(query_stream):
    """Streaming em formato NDJSON (mais eficiente para processamento progressivo)."""
    async for row in query_stream:
        data = serialize_row(row)
        yield json.dumps(data, default = str).encode('utf-8')
        yield b'\n'

async def configurar_estrategia_busca(db: AsyncSession, usar_indice: bool):
    if not usar_indice:
        #enable_indexscan: Permite ao planner usar B-Tree ou outros índices normais para acessar as linhas da tabela.
        #enable_indexonlyscan: Permite usar Index Only Scan, que é quando o PostgreSQL consegue ler somente o índice sem precisar ir na tabela base.
        #enable_bitmapscan: É um método de leitura de dados que combina índices e leitura sequencial eficiente.

        await db.execute(text("SET LOCAL enable_indexscan = OFF"))
        await db.execute(text("SET LOCAL enable_indexonlyscan = OFF"))
        await db.execute(text("SET LOCAL enable_bitmapscan = OFF"))


def create_streaming_response(stream_func, formato: str):
    """Factory para criar StreamingResponse com media type correto."""
    media = "application/x-ndjson" if formato == "ndjson" else "application/json"
    return StreamingResponse(stream_func(), media_type = media)

