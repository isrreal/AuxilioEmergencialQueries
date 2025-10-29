from fastapi import APIRouter

from app.api.v1.endpoints import auxilio_emergencial

api_router = APIRouter()

api_router.include_router(auxilio_emergencial.router, prefix = "/auxilio", tags = ["Auxílio"])
