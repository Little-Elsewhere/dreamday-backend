from fastapi import APIRouter

from app.schemas.responses import MessageResponse

router = APIRouter()


@router.get('/', response_model=MessageResponse)
async def root() -> MessageResponse:
  return MessageResponse(message='Hello World')
