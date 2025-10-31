from fastapi import APIRouter

from app.api.v1.endpoints import (
    auxilio_emergencial_routes,
    beneficiario_routes,
    responsavel_routes
)

api_router: APIRouter = APIRouter()

api_router.include_router(auxilio_emergencial_routes.router, prefix = "/auxilio", tags = ["Auxílio"])
api_router.include_router(responsavel_routes.router, prefix = "/responsaveis", tags = ["Responsáveis"])
api_router.include_router(beneficiario_routes.router, prefix = "/beneficiarios", tags = ["Beneficiários"])
