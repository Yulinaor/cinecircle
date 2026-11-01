"""FastAPI application factory. Run with: uvicorn cinecircle_api.main:create_app --factory"""

from fastapi import FastAPI

from cinecircle_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="CineCircle API", version="0.1.0")
    app.state.settings = settings

    @app.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    return app
