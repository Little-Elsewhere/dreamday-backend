# Docker

The backend runs on its own: development and production each have a Dockerfile and a Compose file here. Run every command from `apps/backend`.

## Environment

Each place the app runs has its own env file, copied from its example:

| File | Used by | `DATABASE_URL` points to |
| --- | --- | --- |
| `.env` | `cargo run`, `cargo test`, `sqlx-cli` on the host | `localhost:5432` (the dev `backend-db` service) |
| `docker/dev/.env` | `docker/dev/compose.yaml`, also the root repo's stack | `backend-db:5432` (Compose service name) |
| `docker/prod/.env` | `docker/prod/compose.yaml` | the production database |

```bash
cp .env.example .env
cp docker/dev/.env.example docker/dev/.env
```

| Key | Notes |
| --- | --- |
| `APP_PORT` | Defaults to `8000` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Only in `docker/dev/.env`; create the dev database. Keep them in sync with `DATABASE_URL` in `.env` and `docker/dev/.env` |
| `DATABASE_URL` | Connection string the app and `cargo test` use |
| `DATA_ENCRYPTION_KEY`, `DATA_HMAC_KEY` | 32 random bytes in base64 each; generate every key with `openssl rand -base64 32` and never commit one. Personal data is encrypted with them; the app refuses to start without them. Each environment gets its own pair; back up the production pair outside the server, because losing it makes stored personal data unreadable |

## Development

```bash
docker compose -f docker/dev/compose.yaml up --build
```

- API: <http://localhost:8000>
- Postgres: `localhost:5432` (also used by `cargo test` on the host)

The source tree is bind-mounted into the container, and `watchexec` recompiles and restarts the API whenever `src/`, `migrations/`, `Cargo.toml` or `Cargo.lock` changes. After changing dependencies, also rebuild with `up --build` so they are cached in the image instead of being recompiled each time the container is recreated.

```bash
docker compose -f docker/dev/compose.yaml down
```

## Production

Production does not start a database; `DATABASE_URL` in `docker/prod/.env` must point to one. Migrations run when the app starts.

```bash
cp docker/prod/.env.example docker/prod/.env
docker compose -f docker/prod/compose.yaml up --build -d
docker compose -f docker/prod/compose.yaml logs -f
docker compose -f docker/prod/compose.yaml down
```

The API is published on port `8000`.
