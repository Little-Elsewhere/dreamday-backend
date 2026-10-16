from typing import Literal

from pydantic import BaseModel


class MessageResponse(BaseModel):
  message: str


class HealthResponse(BaseModel):
  status: Literal['ok']
