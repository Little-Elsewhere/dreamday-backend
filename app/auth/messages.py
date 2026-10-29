from app.shared.responses import MessageResponse


class AuthMessages:
  REGISTRATION_ACCEPTED = MessageResponse(
    code=1001,
    message='Check your email for a verification link to finish registration.',
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
    message='Check your email for a verification link before logging in.',
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
  EMAIL_ALREADY_REGISTERED = MessageResponse(
    code=1012,
    message='An account with this email already exists.',
  )
  PASSWORD_RESET_EMAIL_ACCEPTED = MessageResponse(
    code=1013,
    message=(
      'If an account exists for this email, a password reset link will be sent.'
    ),
  )
  INVALID_OR_EXPIRED_PASSWORD_RESET_LINK = MessageResponse(
    code=1014,
    message='Invalid or expired password reset link.',
  )
  PASSWORD_RESET_SUCCESS = MessageResponse(
    code=1015,
    message='Password updated. You can now log in with your new password.',
  )
  INVALID_CURRENT_PASSWORD = MessageResponse(
    code=1016,
    message='Current password is incorrect.',
  )
