from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import (
    auxilio_routes,
    beneficiario_routes,
    responsavel_routes,
    consultas_routes
)
from app.core.deps import get_session
from app.core.auth import criar_token_acesso, autenticar

api_router: APIRouter = APIRouter()

api_router.include_router(
    auxilio_routes.router,
    prefix = "/auxilio",
    tags = ["Auxílios"]
)

api_router.include_router(
    responsavel_routes.router,
    prefix = "/responsaveis",
    tags = ["Responsáveis"]
)

api_router.include_router(
    beneficiario_routes.router,
    prefix = "/beneficiarios",
    tags = ["Beneficiários"]
)

api_router.include_router(
    consultas_routes.router,
    prefix = "/consultas",
    tags = ["Consultas"]
)

@api_router.post("/login", summary = "Autenticar usuário e gerar token JWT")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_session)
):
    """
    Rota de login para autenticar um usuário e retornar um token JWT.

    Args:
        form_data: Formulário OAuth2 com username e password
        db: Sessão assíncrona do banco de dados

    Returns:
        JSON contendo o access_token e tipo de token ("bearer")
    """
    usuario = await autenticar(email = form_data.username, senha = form_data.password, db = db)

    if not usuario:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "Dados de acesso incorretos."
        )

    return JSONResponse(
        content = {
            "access_token": criar_token_acesso(sub = usuario.id),
            "token_type": "bearer"
        },
        status_code = status.HTTP_200_OK
    )