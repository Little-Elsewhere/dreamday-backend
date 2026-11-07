from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.health.router import router as health_router
from app.trips.router import router as trips_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(trips_router)
