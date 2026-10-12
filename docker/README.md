# Docker

The app uses the Python version declared in `pyproject.toml` and installs dependencies from `uv.lock`.
The development and production environments have separate Dockerfiles.

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

The API listens on port `8000` by default. Set `APP_PORT` to publish it on another host port. View logs and stop the service with:

```bash
docker compose -f docker/prod/compose.yaml logs -f
docker compose -f docker/prod/compose.yaml down
```

`pyproject.toml` currently requires Python `>=3.15`, so both Dockerfiles use the Python 3.15 release-candidate image until the stable image is available.
