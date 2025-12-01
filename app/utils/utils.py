import json
from fastapi.responses import StreamingResponse

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


def create_streaming_response(stream_func, formato: str):
    """Factory para criar StreamingResponse com media type correto."""
    media = "application/x-ndjson" if formato == "ndjson" else "application/json"
    return StreamingResponse(stream_func(), media_type = media)