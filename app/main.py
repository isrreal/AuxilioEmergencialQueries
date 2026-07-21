from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.api import api_router
from app.core.configs import settings
from app.core.database import engine

app = FastAPI()

app.include_router(api_router, prefix = settings.API_V1_STR)


@app.get("/health", include_in_schema = False)
async def healthcheck() -> dict[str, str]:
    """Confirma que a API e sua conexão com o banco estão disponíveis."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail = "Database unavailable",
        ) from exc

    return {"status": "ok"}
