"""FastAPI application factory. Run with: uvicorn cinecircle_api.main:create_app --factory"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cinecircle_api.auth import current_claims, make_verifier
from cinecircle_api.catalog.omdb_client import OmdbClient
from cinecircle_api.catalog.service import TitleService
from cinecircle_api.catalog.tmdb_client import TmdbClient
from cinecircle_api.db import make_engine
from cinecircle_api.routes import health, titles
from cinecircle_api.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="CineCircle API", version="0.1.0")
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    # Without a key the client is None and the title endpoints answer 503; the app still starts.
    app.state.title_service = TitleService(
        app.state.engine,
        TmdbClient(settings.tmdb_api_key) if settings.tmdb_api_key else None,
        OmdbClient(settings.omdb_api_key) if settings.omdb_api_key else None,
    )
    # None when SUPABASE_URL is unset: protected routes then answer 503 auth_unavailable.
    app.state.verifier = make_verifier(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )

    @app.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(health.router)
    # Everything except /live and /health requires sign-in; later routers get the same guard.
    app.include_router(titles.router, dependencies=[Depends(current_claims)])
    return app
