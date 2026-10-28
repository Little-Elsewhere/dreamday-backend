from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status

from app.auth.dependencies import AuthServiceDep, CurrentUser
from app.auth.messages import AuthMessages
from app.auth.schemas import (
  EmailRequest,
  EmailVerificationRequest,
  LoginRequest,
  LogoutRequest,
  RefreshRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
)
from app.auth.service import (
  AuthServiceError,
  AuthServiceErrorCode,
  VerificationEmail,
  deliver_verification_email_in_background,
)
from app.shared.responses import MessageResponse

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])

_AUTH_ERROR_DETAILS = {
  AuthServiceErrorCode.INVALID_VERIFICATION_LINK: (
    status.HTTP_400_BAD_REQUEST,
    AuthMessages.INVALID_OR_EXPIRED_VERIFICATION_LINK,
  ),
  AuthServiceErrorCode.INVALID_CREDENTIALS: (
    status.HTTP_401_UNAUTHORIZED,
    AuthMessages.INVALID_CREDENTIALS,
  ),
  AuthServiceErrorCode.EMAIL_NOT_VERIFIED: (
    status.HTTP_403_FORBIDDEN,
    AuthMessages.EMAIL_NOT_VERIFIED,
  ),
  AuthServiceErrorCode.ACCOUNT_DISABLED: (
    status.HTTP_403_FORBIDDEN,
    AuthMessages.ACCOUNT_DISABLED,
  ),
  AuthServiceErrorCode.INVALID_REFRESH_TOKEN: (
    status.HTTP_401_UNAUTHORIZED,
    AuthMessages.INVALID_OR_EXPIRED_REFRESH_TOKEN,
  ),
}


def _http_exception_for_auth_error(error: AuthServiceError) -> HTTPException:
  status_code, message = _AUTH_ERROR_DETAILS[error.code]
  headers = (
    {'WWW-Authenticate': 'Bearer'}
    if error.code is AuthServiceErrorCode.INVALID_CREDENTIALS
    else None
  )
  return HTTPException(
    status_code=status_code,
    detail=message.model_dump(),
    headers=headers,
  )


def _schedule_verification_email(
  background_tasks: BackgroundTasks,
  verification_email: VerificationEmail | None,
) -> None:
  if verification_email is not None:
    background_tasks.add_task(
      deliver_verification_email_in_background,
      verification_email.email,
      verification_email.raw_token,
      verification_email.token_hash,
    )


@router.post(
  '/register',
  response_model=MessageResponse,
  status_code=status.HTTP_202_ACCEPTED,
)
async def register(
  payload: RegisterRequest,
  background_tasks: BackgroundTasks,
  auth_service: AuthServiceDep,
) -> MessageResponse:
  verification_email = await auth_service.register(
    str(payload.email), payload.password
  )
  _schedule_verification_email(background_tasks, verification_email)
  return AuthMessages.REGISTRATION_ACCEPTED


@router.post(
  '/resend-verification',
  response_model=MessageResponse,
  status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification(
  payload: EmailRequest,
  background_tasks: BackgroundTasks,
  auth_service: AuthServiceDep,
) -> MessageResponse:
  verification_email = await auth_service.resend_verification(
    str(payload.email)
  )
  _schedule_verification_email(background_tasks, verification_email)
  return AuthMessages.VERIFICATION_RESEND_ACCEPTED


@router.post('/verify-email', response_model=MessageResponse)
async def verify_email(
  payload: EmailVerificationRequest,
  response: Response,
  auth_service: AuthServiceDep,
) -> MessageResponse:
  response.headers['Cache-Control'] = 'no-store'
  response.headers['Referrer-Policy'] = 'no-referrer'
  try:
    await auth_service.verify_email(payload.token)
  except AuthServiceError as error:
    raise _http_exception_for_auth_error(error) from error
  return AuthMessages.EMAIL_VERIFIED


@router.post('/login', response_model=TokenResponse)
async def login(
  payload: LoginRequest, auth_service: AuthServiceDep
) -> TokenResponse:
  try:
    return await auth_service.login(str(payload.email), payload.password)
  except AuthServiceError as error:
    raise _http_exception_for_auth_error(error) from error


@router.post('/refresh', response_model=TokenResponse)
async def refresh(
  payload: RefreshRequest, auth_service: AuthServiceDep
) -> TokenResponse:
  try:
    return await auth_service.refresh(payload.refresh_token)
  except AuthServiceError as error:
    raise _http_exception_for_auth_error(error) from error


@router.post('/logout', response_model=MessageResponse)
async def logout(
  payload: LogoutRequest, auth_service: AuthServiceDep
) -> MessageResponse:
  await auth_service.logout(payload.refresh_token)
  return AuthMessages.LOGGED_OUT


@router.get('/me', response_model=UserResponse)
async def read_current_user(current_user: CurrentUser) -> UserResponse:
  return UserResponse(
    id=current_user.id,
    email=current_user.email,
    is_email_verified=current_user.is_email_verified,
    created_at=current_user.created_at,
  )
