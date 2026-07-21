from fastapi import APIRouter

from app.api.v1.endpoints import consultas_routes

api_router: APIRouter = APIRouter()

api_router.include_router(
    consultas_routes.router,
    prefix = "/consultas",
    tags = ["Consultas"]
)
