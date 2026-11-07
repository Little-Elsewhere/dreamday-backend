from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.storage import ObjectStorage, create_object_storage
from app.shared.dependencies import DatabaseSession
from app.trips.service import TripService


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
  return create_object_storage()


ObjectStorageDep = Annotated[ObjectStorage, Depends(get_object_storage)]


def get_trip_service(
  session: DatabaseSession,
  storage: ObjectStorageDep,
) -> TripService:
  return TripService(session, storage)


TripServiceDep = Annotated[TripService, Depends(get_trip_service)]
