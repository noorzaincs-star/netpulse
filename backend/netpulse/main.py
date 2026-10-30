import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker

from netpulse.api.devices import router as devices_router
from netpulse.api.health import router as health_router
from netpulse.api.live import router as live_router
from netpulse.api.monitoring import router as monitoring_router
from netpulse.core.config import Settings
from netpulse.db.database import create_database_engine, initialize_database
from netpulse.services.events import EventBroker
from netpulse.services.interfaces import InterfaceSampler
from netpulse.services.monitoring import MonitoringService
from netpulse.services.worker import MonitoringWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(
    settings: Settings | None = None,
    *,
    start_worker: bool = True,
) -> FastAPI:
    config = settings or Settings.from_environment()
    engine = create_database_engine(config.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    broker = EventBroker()
    monitoring = MonitoringService(sessions, config, broker)
    worker = MonitoringWorker(sessions, monitoring, config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await initialize_database(engine)
            if start_worker:
                worker.start()
            yield
        finally:
            await worker.stop()
            await engine.dispose()

    app = FastAPI(
        title="NetPulse API",
        description="Local network monitoring service. Checks run only for explicitly configured targets.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.sessions = sessions
    app.state.settings = config
    app.state.broker = broker
    app.state.monitoring = monitoring
    app.state.worker = worker
    app.state.interface_sampler = InterfaceSampler()
    app.include_router(health_router, prefix="/api")
    app.include_router(devices_router, prefix="/api")
    app.include_router(monitoring_router, prefix="/api")
    app.include_router(live_router, prefix="/api")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def localhost_host_guard(request: Request, call_next):
        hostname = request.url.hostname
        if hostname not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "local_only",
                        "message": "NetPulse accepts requests only through localhost.",
                    }
                },
            )
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": jsonable_encoder(exc.errors()),
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        _: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": detail.get("code", "http_error"),
                    "message": detail.get("message", str(exc.detail)),
                    "details": detail.get("details"),
                }
            },
        )

    return app


app = create_app()
