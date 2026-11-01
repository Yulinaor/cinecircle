"""FastAPI application factory. Run with: uvicorn cinecircle_api.main:create_app --factory"""

from fastapi import FastAPI

from cinecircle_api.db import make_engine
from cinecircle_api.routes import health
from cinecircle_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="CineCircle API", version="0.1.0")
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)

    @app.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(health.router)
    return app
