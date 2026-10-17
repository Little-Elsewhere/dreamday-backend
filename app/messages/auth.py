from app.schemas.responses import MessageResponse


class AuthMessages:
  REGISTRATION_ACCEPTED = MessageResponse(
    code=1001,
    message=(
      'If this email address can be registered, a verification link will be sent.'
    ),
  )
  VERIFICATION_RESEND_ACCEPTED = MessageResponse(
    code=1002,
    message='If the account needs verification, an email will be sent.',
  )
  INVALID_OR_EXPIRED_VERIFICATION_LINK = MessageResponse(
    code=1003,
    message='Invalid or expired verification link.',
  )
  EMAIL_VERIFIED = MessageResponse(
    code=1004,
    message='Email verified. You can now log in to your account.',
  )
  INVALID_CREDENTIALS = MessageResponse(
    code=1005,
    message='Invalid email or password.',
  )
  EMAIL_NOT_VERIFIED = MessageResponse(
    code=1006,
    message='Verify your email before logging in.',
  )
  ACCOUNT_DISABLED = MessageResponse(
    code=1007,
    message='This account is disabled.',
  )
  INVALID_OR_EXPIRED_REFRESH_TOKEN = MessageResponse(
    code=1008,
    message='Invalid or expired refresh token.',
  )
  BEARER_ACCESS_TOKEN_REQUIRED = MessageResponse(
    code=1009,
    message='Bearer access token required.',
  )
  INVALID_OR_EXPIRED_ACCESS_TOKEN = MessageResponse(
    code=1010,
    message='Invalid or expired access token.',
  )
  LOGGED_OUT = MessageResponse(
    code=1011,
    message='Logged out.',
  )
