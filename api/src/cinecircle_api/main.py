"""FastAPI application factory. Run with: uvicorn cinecircle_api.main:create_app --factory"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from cinecircle_api.auth import current_claims, make_verifier
from cinecircle_api.catalog.omdb_client import OmdbClient
from cinecircle_api.catalog.service import TitleService
from cinecircle_api.catalog.tmdb_client import TmdbClient
from cinecircle_api.db import make_engine
from cinecircle_api.routes import health, titles
from cinecircle_api.settings import Settings, get_settings


def _db_unavailable(_: Request, __: Exception) -> JSONResponse:
    # Fixed body: the exception text carries the connection string and host.
    return JSONResponse({"detail": "db_unavailable"}, status_code=503)


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # A malformed id in the URL means "no such resource"; query/body mistakes stay 422.
    errors = exc.errors()
    if errors and all(error["loc"][0] == "path" for error in errors):
        return JSONResponse({"detail": "not_found"}, status_code=404)
    return await request_validation_exception_handler(request, exc)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    tmdb = TmdbClient(settings.tmdb_api_key) if settings.tmdb_api_key else None
    omdb = OmdbClient(settings.omdb_api_key) if settings.omdb_api_key else None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        for client in (tmdb, omdb):
            if client is not None:
                client.close()
        app.state.engine.dispose()

    # The interactive docs and schema are unauthenticated, so only the local app serves them.
    docs = settings.app_env == "local"
    app = FastAPI(
        title="CineCircle API",
        version="0.1.0",
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        lifespan=lifespan,
    )
    app.add_exception_handler(OperationalError, _db_unavailable)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    # Without a key the client is None and the title endpoints answer 503; the app still starts.
    app.state.title_service = TitleService(app.state.engine, tmdb, omdb)
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
