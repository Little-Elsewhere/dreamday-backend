from fastapi import FastAPI

app = FastAPI()


@app.get('/')
async def root():
  return {'message': 'Hello World'}


@app.get('/health', include_in_schema=False)
async def health_check() -> dict[str, str]:
  return {'status': 'ok'}
