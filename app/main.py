# -*- coding: utf-8 -*-
"""
WeChat Smart Watering Reporting System - main entry.
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from loguru import logger

try:
    from app.core.config import settings
    from app.core.exceptions import AppException
    from app.models.database import init_database
    from app.routes import admin, wechat
except ModuleNotFoundError:
    # Support running `python app/main.py` from the project root.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.config import settings
    from app.core.exceptions import AppException
    from app.models.database import init_database
    from app.routes import admin, wechat


def setup_logging():
    logger.remove()
    logger.add(
        "logs/app.log",
        rotation=settings.logging.rotation,
        retention=settings.logging.retention,
        compression=settings.logging.compression,
        level=settings.logging.level,
        format=settings.logging.format,
    )
    logger.add(sys.stdout, level=settings.logging.level, format=settings.logging.format)
    return logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting app...")
    os.makedirs("logs", exist_ok=True)

    try:
        init_database()
        logger.info("database initialized")
    except Exception as exc:
        logger.warning(f"database init failed: {exc}")

    logger.info("app started")
    yield
    logger.info("shutting down app...")
    logger.info("app shutdown complete")


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        debug=settings.app.debug,
        lifespan=lifespan,
    )

    if settings.cors.enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors.allow_origins,
            allow_credentials=settings.cors.allow_credentials,
            allow_methods=settings.cors.allow_methods,
            allow_headers=settings.cors.allow_headers,
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.code,
            content={"error": exc.message, "code": exc.code},
        )

    app.include_router(wechat.router)
    app.include_router(admin.router)

    @app.get("/")
    async def root():
        return {
            "name": settings.app.name,
            "version": settings.app.version,
            "status": "running",
        }

    @app.head("/")
    async def root_head():
        return Response(status_code=200)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        icon_path = Path(__file__).resolve().parent / "static" / "favicon.ico"
        return FileResponse(str(icon_path), media_type="image/x-icon")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        log_level=settings.logging.level.lower(),
    )
