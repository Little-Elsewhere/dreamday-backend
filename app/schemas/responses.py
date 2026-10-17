from typing import Literal

from pydantic import BaseModel


class MessageResponse(BaseModel):
  code: int
  message: str


class HealthResponse(BaseModel):
  status: Literal['ok']
