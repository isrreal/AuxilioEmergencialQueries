from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import Auxilio
from app.schemas.schemas import (
    AuxilioListResponse
)

from app.core.deps import get_session

router: APIRouter = APIRouter()

@router.get('/auxilios', response_model = List[AuxilioListResponse])
async def listar_auxilios(
    limit: int = Query(100, ge = 1, le = 1000), 
    offset: int = Query(0, ge = 0),
    db: AsyncSession = Depends(get_session)
):
    """Retorna todos os auxílios com paginação"""
    async with db as session:
        query = select(Auxilio).limit(limit).offset(offset)
        result = await session.execute(query)
        auxilios = result.scalars().all()
        
        if not auxilios:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND,
                detail = "Nenhum auxílio encontrado"
            )
        
        return auxilios

