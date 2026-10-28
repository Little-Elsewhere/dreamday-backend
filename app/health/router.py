from fastapi import APIRouter

from app.shared.responses import HealthResponse

router = APIRouter()


@router.get('/health', response_model=HealthResponse, include_in_schema=False)
async def health_check() -> HealthResponse:
  return HealthResponse(status='ok')
