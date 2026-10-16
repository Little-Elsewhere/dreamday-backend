# Docker

Development and production have separate Dockerfiles. Both install locked dependencies from `uv.lock`; production omits development dependencies and runs as a non-root user.

## Application settings

Settings are validated at application startup. When running the backend directly, Pydantic loads `apps/backend/.env`; Docker Compose also passes that project-local file into the container. Create it from the backend example while in `apps/backend`:

```bash
cp .env.example .env
```

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `APP_NAME` | non-empty string | required | FastAPI application title |
| `APP_DEBUG` | boolean | `false` | Enables FastAPI debug mode; accepted values include `true` and `false` |

The monorepo's root Compose file can independently pass `env/backend/.env` to the backend service. This backend project does not depend on that parent path. Run the commands below from `apps/backend`.

## Development

Start the API with reload enabled:

```bash
docker compose -f docker/dev/compose.yaml up --build
```

The API is available at <http://localhost:8000>. Stop it with:

```bash
docker compose -f docker/dev/compose.yaml down
```

## Production

Build and run the production image:

```bash
docker compose -f docker/prod/compose.yaml up --build -d
```

The API is published on port `8000`. View logs and stop the service with:

```bash
docker compose -f docker/prod/compose.yaml logs -f
docker compose -f docker/prod/compose.yaml down
```

