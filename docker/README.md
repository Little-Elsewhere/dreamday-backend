# Docker

Development and production each have their own Dockerfile and Compose file. Both install locked dependencies from `uv.lock`; production omits development dependencies and runs as a non-root user.

Run the commands below from `apps/backend`.

## Environment

Copy `.env.example` to `.env` and fill every key (the app has no in-code defaults):

```bash
cp .env.example .env
```

| Group | Keys | Notes |
| --- | --- | --- |
| Application | `APP_NAME`, `APP_DEBUG` | FastAPI title and debug flag |
| Database | `DB_HOST`, `DB_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose: `DB_HOST=db`; host run: `localhost` |  # pragma: allowlist secret
| Auth tokens | `JWT_SECRET_KEY`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | `JWT_SECRET_KEY` ≥ 32 chars; generate with `python -c 'import secrets; print(secrets.token_urlsafe(48))'` |  # pragma: allowlist secret
| Email verification | `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`, `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS`, `EMAIL_VERIFICATION_URL` | Frontend verify page URL; backend appends the token query param |
| Password reset | `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`, `PASSWORD_RESET_RESEND_COOLDOWN_SECONDS`, `PASSWORD_RESET_URL` | Frontend reset page URL; backend appends the token query param |
| SMTP | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_START_TLS`, `SMTP_TIMEOUT_SECONDS`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` | Compose: `SMTP_HOST=mailpit`; username/password may be empty |  # pragma: allowlist secret

## Development

```bash
docker compose --env-file .env -f docker/dev/compose.yaml up --build
```

- API: <http://localhost:8000>
- Mailpit: <http://localhost:8025>

```bash
docker compose --env-file .env -f docker/dev/compose.yaml down
```

## Production

```bash
docker compose --env-file .env -f docker/prod/compose.yaml up --build -d
```

API is published on port `8000`.

```bash
docker compose --env-file .env -f docker/prod/compose.yaml logs -f
docker compose --env-file .env -f docker/prod/compose.yaml down
```
