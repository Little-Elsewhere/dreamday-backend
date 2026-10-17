from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
  try:
    yield
  finally:
    await engine.dispose()


def create_app() -> FastAPI:
  application = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    lifespan=lifespan,
  )
  application.include_router(api_router)
  return application


app = create_app()
