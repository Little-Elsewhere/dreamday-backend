from app.shared.responses import MessageResponse


class TripMessages:
  TRIP_NOT_FOUND = MessageResponse(
    code=2001,
    message='Trip not found.',
  )
  DRAFT_ALREADY_EXISTS = MessageResponse(
    code=2002,
    message='An active draft already exists.',
  )
  DRAFT_NOT_FOUND = MessageResponse(
    code=2003,
    message='No active draft found.',
  )
  INVALID_TRIP_DATES = MessageResponse(
    code=2004,
    message='End date must be on or after start date.',
  )
  PUBLISH_VALIDATION_FAILED = MessageResponse(
    code=2005,
    message='Trip is missing required fields to publish.',
  )
  ACTIVITY_NOT_FOUND = MessageResponse(
    code=2006,
    message='Activity not found.',
  )
  ACTIVITY_OUTSIDE_TRIP = MessageResponse(
    code=2007,
    message='Activity date must fall within the trip dates.',
  )
  INVALID_ACTIVITY_TIME = MessageResponse(
    code=2008,
    message='Activity end time must be after start time.',
  )
  TRIP_DELETED = MessageResponse(
    code=2009,
    message='Trip is deleted and cannot be modified.',
  )
  TRIP_NOT_DELETED = MessageResponse(
    code=2010,
    message='Trip is not deleted.',
  )
  INVALID_COVER = MessageResponse(
    code=2011,
    message='Cover must be a JPEG, PNG, or WebP image up to 2MB.',
  )
  ACTIVITY_DELETED = MessageResponse(
    code=2012,
    message='Activity is deleted and cannot be modified.',
  )
  ACTIVITY_NOT_DELETED = MessageResponse(
    code=2013,
    message='Activity is not deleted.',
  )
