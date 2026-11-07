from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol
from uuid import UUID, uuid4

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings

COVER_CONTENT_TYPES = frozenset({'image/jpeg', 'image/png', 'image/webp'})
COVER_EXTENSIONS = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
}
MAX_COVER_BYTES = 2 * 1024 * 1024


class ObjectStorage(Protocol):
  async def ensure_bucket(self) -> None: ...

  async def put_bytes(
    self,
    *,
    key: str,
    body: bytes,
    content_type: str,
  ) -> str: ...

  async def delete_object(self, key: str) -> None: ...

  def public_url_for(self, key: str) -> str: ...


def cover_object_key(
  *,
  user_id: UUID,
  trip_id: UUID,
  content_type: str,
) -> str:
  extension = COVER_EXTENSIONS[content_type]
  return f'trips/{user_id}/{trip_id}/{uuid4()}.{extension}'


class S3ObjectStorage:
  def __init__(
    self,
    *,
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str,
    public_base_url: str,
  ) -> None:
    self._endpoint_url = endpoint_url.rstrip('/')
    self._access_key = access_key
    self._secret_key = secret_key
    self._bucket = bucket
    self._region = region
    self._public_base_url = public_base_url.rstrip('/')
    self._session = aioboto3.Session()

  @asynccontextmanager
  async def _client(self) -> AsyncIterator[object]:
    async with self._session.client(
      's3',
      endpoint_url=self._endpoint_url,
      aws_access_key_id=self._access_key,
      aws_secret_access_key=self._secret_key,
      region_name=self._region,
    ) as client:
      yield client

  async def ensure_bucket(self) -> None:
    async with self._client() as client:
      try:
        await client.head_bucket(Bucket=self._bucket)
      except ClientError:
        await client.create_bucket(Bucket=self._bucket)

  async def put_bytes(
    self,
    *,
    key: str,
    body: bytes,
    content_type: str,
  ) -> str:
    await self.ensure_bucket()
    async with self._client() as client:
      await client.put_object(
        Bucket=self._bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
      )
    return self.public_url_for(key)

  async def delete_object(self, key: str) -> None:
    async with self._client() as client:
      try:
        await client.delete_object(Bucket=self._bucket, Key=key)
      except ClientError:
        return

  def public_url_for(self, key: str) -> str:
    return f'{self._public_base_url}/{key.lstrip("/")}'


def create_object_storage() -> S3ObjectStorage:
  return S3ObjectStorage(
    endpoint_url=str(settings.s3_endpoint_url),
    access_key=settings.s3_access_key,
    secret_key=settings.s3_secret_key.get_secret_value(),
    bucket=settings.s3_bucket,
    region=settings.s3_region,
    public_base_url=str(settings.s3_public_base_url),
  )


class InMemoryObjectStorage:
  """Test double that keeps objects in process memory."""

  def __init__(self, *, public_base_url: str = 'http://test.local') -> None:
    self._public_base_url = public_base_url.rstrip('/')
    self.objects: dict[str, tuple[bytes, str]] = {}

  async def ensure_bucket(self) -> None:
    return None

  async def put_bytes(
    self,
    *,
    key: str,
    body: bytes,
    content_type: str,
  ) -> str:
    self.objects[key] = (body, content_type)
    return self.public_url_for(key)

  async def delete_object(self, key: str) -> None:
    self.objects.pop(key, None)

  def public_url_for(self, key: str) -> str:
    return f'{self._public_base_url}/{key.lstrip("/")}'
