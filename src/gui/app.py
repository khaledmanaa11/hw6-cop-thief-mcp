from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.game.config import load_config
from src.gui.replay import list_runs, load_run


def _static_dir() -> Path:
    return Path(__file__).with_name("static")


def _safe_run_path(run_dir: Path, name: str) -> Path | None:
    if Path(name).name != name or not name.endswith(".jsonl"):
        return None
    root = run_dir.resolve()
    candidate = (root / name).resolve()
    if candidate.parent != root:
        return None
    return candidate


def create_app(config) -> FastAPI:
    app = FastAPI(title="HW6 Cop-and-Thief Replay GUI")
    run_dir = Path(config.gui["run_dir"])
    static_dir = _static_dir()
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/api/runs")
    def api_runs():
        return {"runs": list_runs(run_dir)}

    @app.get("/api/runs/{name}")
    def api_run(name: str):
        path = _safe_run_path(run_dir, name)
        if path is None or not path.exists():
            raise HTTPException(status_code=404, detail="run not found")
        try:
            return load_run(path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def main() -> None:
    config = load_config("config.yaml")
    uvicorn.run(create_app(config), host=config.gui["host"], port=config.gui["port"])


if __name__ == "__main__":
    main()
