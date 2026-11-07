from typing import Annotated
from uuid import UUID

from fastapi import (
  APIRouter,
  File,
  HTTPException,
  Query,
  UploadFile,
  status,
)

from app.auth.dependencies import CurrentUser
from app.shared.responses import MessageResponse
from app.trips.dependencies import TripServiceDep
from app.trips.messages import TripMessages
from app.trips.schemas import (
  TripActivityCreate,
  TripActivityResponse,
  TripActivityUpdate,
  TripCreateRequest,
  TripDetailResponse,
  TripListResponse,
  TripListStatus,
  TripUpdateRequest,
)
from app.trips.service import TripServiceError, TripServiceErrorCode

router = APIRouter(prefix='/api/v1/trips', tags=['trips'])

_ERROR_DETAILS = {
  TripServiceErrorCode.TRIP_NOT_FOUND: (
    status.HTTP_404_NOT_FOUND,
    TripMessages.TRIP_NOT_FOUND,
  ),
  TripServiceErrorCode.DRAFT_ALREADY_EXISTS: (
    status.HTTP_409_CONFLICT,
    TripMessages.DRAFT_ALREADY_EXISTS,
  ),
  TripServiceErrorCode.DRAFT_NOT_FOUND: (
    status.HTTP_404_NOT_FOUND,
    TripMessages.DRAFT_NOT_FOUND,
  ),
  TripServiceErrorCode.INVALID_TRIP_DATES: (
    status.HTTP_400_BAD_REQUEST,
    TripMessages.INVALID_TRIP_DATES,
  ),
  TripServiceErrorCode.PUBLISH_VALIDATION_FAILED: (
    status.HTTP_400_BAD_REQUEST,
    TripMessages.PUBLISH_VALIDATION_FAILED,
  ),
  TripServiceErrorCode.ACTIVITY_NOT_FOUND: (
    status.HTTP_404_NOT_FOUND,
    TripMessages.ACTIVITY_NOT_FOUND,
  ),
  TripServiceErrorCode.ACTIVITY_OUTSIDE_TRIP: (
    status.HTTP_400_BAD_REQUEST,
    TripMessages.ACTIVITY_OUTSIDE_TRIP,
  ),
  TripServiceErrorCode.INVALID_ACTIVITY_TIME: (
    status.HTTP_400_BAD_REQUEST,
    TripMessages.INVALID_ACTIVITY_TIME,
  ),
  TripServiceErrorCode.TRIP_DELETED: (
    status.HTTP_409_CONFLICT,
    TripMessages.TRIP_DELETED,
  ),
  TripServiceErrorCode.TRIP_NOT_DELETED: (
    status.HTTP_409_CONFLICT,
    TripMessages.TRIP_NOT_DELETED,
  ),
  TripServiceErrorCode.INVALID_COVER: (
    status.HTTP_400_BAD_REQUEST,
    TripMessages.INVALID_COVER,
  ),
  TripServiceErrorCode.ACTIVITY_DELETED: (
    status.HTTP_409_CONFLICT,
    TripMessages.ACTIVITY_DELETED,
  ),
  TripServiceErrorCode.ACTIVITY_NOT_DELETED: (
    status.HTTP_409_CONFLICT,
    TripMessages.ACTIVITY_NOT_DELETED,
  ),
}


def _http_exception_for(error: TripServiceError) -> HTTPException:
  status_code, message = _ERROR_DETAILS[error.code]
  return HTTPException(
    status_code=status_code,
    detail=message.model_dump(),
  )


@router.get('', response_model=TripListResponse)
async def list_trips(
  current_user: CurrentUser,
  service: TripServiceDep,
  status_filter: Annotated[TripListStatus, Query(alias='status')] = 'all',
  q: Annotated[str | None, Query(max_length=80)] = None,
  limit: Annotated[int, Query(ge=1, le=50)] = 6,
  offset: Annotated[int, Query(ge=0)] = 0,
) -> TripListResponse:
  return await service.list_trips(
    current_user.id,
    status=status_filter,
    q=q,
    limit=limit,
    offset=offset,
  )


@router.get('/deleted', response_model=TripListResponse)
async def list_deleted_trips(
  current_user: CurrentUser,
  service: TripServiceDep,
  limit: Annotated[int, Query(ge=1, le=50)] = 6,
  offset: Annotated[int, Query(ge=0)] = 0,
) -> TripListResponse:
  return await service.list_trips(
    current_user.id,
    deleted=True,
    limit=limit,
    offset=offset,
  )


@router.get('/draft', response_model=TripDetailResponse)
async def get_draft(
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripDetailResponse:
  try:
    return await service.get_draft(current_user.id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.post(
  '',
  response_model=TripDetailResponse,
  status_code=status.HTTP_201_CREATED,
)
async def create_draft(
  payload: TripCreateRequest,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripDetailResponse:
  try:
    return await service.create_draft(current_user.id, payload)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.get('/{trip_id}', response_model=TripDetailResponse)
async def get_trip(
  trip_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripDetailResponse:
  try:
    return await service.get_trip(current_user.id, trip_id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.patch('/{trip_id}', response_model=TripDetailResponse)
async def update_trip(
  trip_id: UUID,
  payload: TripUpdateRequest,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripDetailResponse:
  try:
    return await service.update_trip(current_user.id, trip_id, payload)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.post('/{trip_id}/publish', response_model=TripDetailResponse)
async def publish_trip(
  trip_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripDetailResponse:
  try:
    return await service.publish(current_user.id, trip_id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.delete(
  '/{trip_id}',
  response_model=MessageResponse,
  status_code=status.HTTP_200_OK,
)
async def soft_delete_trip(
  trip_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> MessageResponse:
  try:
    await service.soft_delete(current_user.id, trip_id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error
  return MessageResponse(code=2014, message='Trip deleted.')


@router.post('/{trip_id}/restore', response_model=TripDetailResponse)
async def restore_trip(
  trip_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripDetailResponse:
  try:
    return await service.restore(current_user.id, trip_id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.post('/{trip_id}/cover', response_model=TripDetailResponse)
async def upload_cover(
  trip_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
  file: Annotated[UploadFile, File()],
) -> TripDetailResponse:
  body = await file.read()
  content_type = file.content_type or ''
  try:
    return await service.upload_cover(
      current_user.id,
      trip_id,
      body=body,
      content_type=content_type,
    )
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.delete('/{trip_id}/cover', response_model=TripDetailResponse)
async def remove_cover(
  trip_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripDetailResponse:
  try:
    return await service.remove_cover(current_user.id, trip_id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.post(
  '/{trip_id}/activities',
  response_model=TripActivityResponse,
  status_code=status.HTTP_201_CREATED,
)
async def create_activity(
  trip_id: UUID,
  payload: TripActivityCreate,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripActivityResponse:
  try:
    return await service.create_activity(current_user.id, trip_id, payload)
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.patch(
  '/{trip_id}/activities/{activity_id}',
  response_model=TripActivityResponse,
)
async def update_activity(
  trip_id: UUID,
  activity_id: UUID,
  payload: TripActivityUpdate,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripActivityResponse:
  try:
    return await service.update_activity(
      current_user.id, trip_id, activity_id, payload
    )
  except TripServiceError as error:
    raise _http_exception_for(error) from error


@router.delete(
  '/{trip_id}/activities/{activity_id}',
  response_model=MessageResponse,
)
async def soft_delete_activity(
  trip_id: UUID,
  activity_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> MessageResponse:
  try:
    await service.soft_delete_activity(current_user.id, trip_id, activity_id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error
  return MessageResponse(code=2015, message='Activity deleted.')


@router.post(
  '/{trip_id}/activities/{activity_id}/restore',
  response_model=TripActivityResponse,
)
async def restore_activity(
  trip_id: UUID,
  activity_id: UUID,
  current_user: CurrentUser,
  service: TripServiceDep,
) -> TripActivityResponse:
  try:
    return await service.restore_activity(current_user.id, trip_id, activity_id)
  except TripServiceError as error:
    raise _http_exception_for(error) from error
