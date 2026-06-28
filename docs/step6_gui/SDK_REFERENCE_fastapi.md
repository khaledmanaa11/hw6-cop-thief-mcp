# SDK Ground-Truth - FastAPI + Uvicorn for Step 6 GUI

Verified on 2026-06-27 against the current FastAPI, Uvicorn, and PyPI pages. This file is authoritative for the Step 6 Developer session: do not guess the web API shape.

## Versions to pin

Use `uv`, not manual dependency edits:

```powershell
uv add fastapi==0.138.1 "uvicorn[standard]==0.49.0" httpx==0.28.1
```

- `fastapi==0.138.1` is the current PyPI release, released 2026-06-25.
- `uvicorn[standard]==0.49.0` is the current PyPI release, released 2026-06-03. The `standard` extra provides the normal production/dev extras for the ASGI server.
- `httpx==0.28.1` is required because FastAPI's `TestClient` is based on HTTPX and the docs say to install `httpx` before using it.

## Minimal app and JSON route shape

FastAPI's current first-steps docs show this canonical shape:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}
```

Returning plain dicts from route functions is the correct JSON response path for the Step 6 `/api/*` routes.

## Static files

FastAPI's current static-files docs use this import and mount shape:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
```

For Step 6, `directory` must be the real `src/gui/static` path computed with `Path(__file__).with_name("static")`, not a cwd-dependent literal.

## TestClient

FastAPI's current testing docs use:

```python
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get("/")
assert response.status_code == 200
assert response.json() == {"msg": "Hello World"}
```

Step 6 endpoint tests should create the app in-process with `create_app(config)` and use `TestClient`; they must not open real sockets, a browser, or any API key.

## Programmatic Uvicorn run

Uvicorn's current deployment docs say programmatic startup uses:

```python
uvicorn.run(app, host="127.0.0.1", port=5000)
```

For Step 6, pass the `FastAPI` app object returned by `create_app(config)`, and pass `host=config.gui["host"]`, `port=config.gui["port"]`. Do not hard-code these values in `src/gui/`.

## Optional live/SSE stretch

FastAPI's current custom-response docs expose `StreamingResponse` as:

```python
from fastapi.responses import StreamingResponse


@app.get("/api/live")
async def live():
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

This is optional only. The required Step 6 deliverable is the deterministic JSONL replayer.

## Sources

- FastAPI first steps: https://fastapi.tiangolo.com/tutorial/first-steps/
- FastAPI static files: https://fastapi.tiangolo.com/tutorial/static-files/
- FastAPI testing: https://fastapi.tiangolo.com/tutorial/testing/
- FastAPI custom responses / StreamingResponse: https://fastapi.tiangolo.com/advanced/custom-response/
- Uvicorn programmatic run: https://www.uvicorn.org/deployment/
- PyPI FastAPI: https://pypi.org/project/fastapi/
- PyPI Uvicorn: https://pypi.org/project/uvicorn/
- PyPI HTTPX: https://pypi.org/project/httpx/
