from fastapi import FastAPI
from api.v1.api import api_router

app = FastAPI()

app.include_router(
    api_router.router,
    prefix = "/api/v1/auxilios",
    tags = ["Auxílios"]
)