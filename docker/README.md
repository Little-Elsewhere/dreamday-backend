# Docker

Development and production have separate Dockerfiles. Both install locked dependencies from `uv.lock`; production omits development dependencies and runs as a non-root user.

## Application settings

Settings are validated at application startup. Every setting must be present in `.env`; the application has no in-code defaults. The example lists the required keys with blank values, so fill them before starting the backend. When running it directly, Pydantic loads `apps/backend/.env`; Docker Compose passes that project-local file into the container. Create it from the backend example while in `apps/backend`:

```bash
cp .env.example .env
```

Set `JWT_SECRET_KEY` to a random value of at least 32 characters. Generate one with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.

### Application

| Variable | Type | Required | Description |
| --- | --- | --- | --- |
| `APP_NAME` | non-empty string | Yes | FastAPI application title |
| `APP_DEBUG` | boolean | Yes | Enables FastAPI debug mode; accepted values include `true` and `false` |

### Database

| Variable | Type | Required | Description |
| --- | --- | --- | --- |
| `DB_HOST`, `DB_PORT` | hostname and port | Yes | PostgreSQL server; set `DB_HOST=db` for Compose or `localhost` when running directly on the host |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | credentials and database name | Yes | PostgreSQL login and database; configure these in `.env` |

### Authentication and tokens

| Variable | Type | Required | Description |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | secret, at least 32 characters | Yes | Sign access tokens; generate a different random value for each environment |
| `JWT_ISSUER`, `JWT_AUDIENCE` | strings | Yes | Access token validation claims |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | positive integer | Yes | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | positive integer | Yes | Refresh token lifetime |

### Email verification

| Variable | Type | Required | Description |
| --- | --- | --- | --- |
| `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES` | positive integer | Yes | Email link lifetime |
| `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS` | non-negative integer | Yes | Minimum delay before sending another verification email |
| `EMAIL_VERIFICATION_URL` | HTTP(S) URL | Yes | Frontend email verification page; the backend appends the token as a query parameter |

### SMTP

| Variable | Type | Required | Description |
| --- | --- | --- | --- |
| `SMTP_HOST`, `SMTP_PORT` | hostname and port | Yes | SMTP server; dev Compose routes this to Mailpit |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | optional credentials | Yes | Set both to empty or configure both with credentials |
| `SMTP_USE_TLS`, `SMTP_START_TLS` | booleans | Yes | Select implicit TLS or STARTTLS for SMTP |
| `SMTP_TIMEOUT_SECONDS` | positive number | Yes | SMTP connection and send timeout |
| `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` | sender address and name | Yes | Email sender headers |

The monorepo's root Compose file can independently pass `env/backend/.env` to the backend service. This backend project does not depend on that parent path. Run the commands below from `apps/backend`.

## Development

For Compose development, set `DB_HOST=db` and `SMTP_HOST=mailpit` in `.env`. When running the API directly on your machine, use `localhost` for services running on that machine. Compose runs PostgreSQL 18 and stores its data in the `postgres18_data` volume. Existing PostgreSQL 17 data in `postgres_data` is left untouched and is not upgraded automatically. Then start PostgreSQL, Mailpit, apply migrations, and start the API with reload enabled:

```bash
docker compose --env-file .env -f docker/dev/compose.yaml up --build
```

The API is available at <http://localhost:8000>. Mailpit's inbox is available at <http://localhost:8025>. Stop the services with:

```bash
docker compose --env-file .env -f docker/dev/compose.yaml down
```

## Authentication flow

The auth API is under `/api/v1/auth`:

Auth messages include a stable numeric `code` for frontend i18n and an English `message` fallback. The backend does not localize these messages. Successful responses return both at the top level; FastAPI error responses return them inside `detail`:

```json
{"code":1004,"message":"Email verified. You can now log in to your account."}
```

```json
{"detail":{"code":1005,"message":"Invalid email or password"}}
```

1. `POST /register` with an email and a password (12–128 characters). The response is the same whether the address is new or already registered.
2. Open the single-use link delivered to the address. The frontend page sends its token to `POST /api/v1/auth/verify-email` to confirm the address. The token expires after the configured verification lifetime.
3. `POST /login` with the verified email and password. The response contains a short-lived JWT access token and an opaque refresh token.
4. Send the refresh token to `POST /refresh` to rotate it. Store the replacement and discard the old token; reuse of an old token revokes its token family.
5. Send `Authorization: Bearer <access_token>` to protected routes such as `GET /api/v1/auth/me`. `POST /logout` revokes the submitted refresh token.

If the message does not arrive, `POST /resend-verification` accepts `{"email":"person@example.com"}`. The API applies a resend cooldown and uses a generic response for unknown and already verified addresses.

Request bodies:

```json
{"email":"person@example.com","password":"a-long-password-at-least-12"}  # pragma: allowlist secret
```

```json
{"refresh_token":"the-current-refresh-token"}
```

The frontend verification page sends the `token` query parameter from the email link to the backend:

```json
{"token":"the-email-verification-token"}
```

To run the app outside Compose, set `DB_HOST=localhost`, `DB_PORT`, the `POSTGRES_*` variables, and SMTP settings in `.env`, then apply the schema before starting the server:

```bash
uv run alembic upgrade head
uv run fastapi dev
```

## CI hard gates

Pull requests to `develop` and `main` run `.github/workflows/ci.yml`:

- Conventional Commits via Commitizen (`pre-commit` commit-msg + CI `cz check`)
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run lint-imports` (import-linter architecture contracts)
- `detect-secrets-hook` against `.secrets.baseline`
- `uv run pytest`

After cloning, install hooks with `pre-commit install` (installs `pre-commit` and `commit-msg`). Optional guided commits: `uv run cz commit`.

PRs to `main` also run `.github/workflows/cd.yml`, which builds the production Docker image without pushing it.

## Production

Build and run the production image:

```bash
docker compose --env-file .env -f docker/prod/compose.yaml up --build -d
```

The API is published on port `8000`. View logs and stop the service with:

```bash
docker compose --env-file .env -f docker/prod/compose.yaml logs -f
docker compose --env-file .env -f docker/prod/compose.yaml down
```

