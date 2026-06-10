from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.middleware.security import SecurityHeadersMiddleware
from app.routers import auth, health, v1
from app.services.s3 import ensure_bucket


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        ensure_bucket()
    except Exception:
        # MinIO may not be ready on first boot; readiness endpoint reports status.
        pass
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Partifi API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(v1.router)

    return app


app = create_app()
