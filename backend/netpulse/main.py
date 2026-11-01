import logging
from pathlib import Path
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
from netpulse.services.demo import seed_public_demo_devices
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
    static_dir: Path | None = None,
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
            if config.public_demo_mode:
                await seed_public_demo_devices(sessions)
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
    frontend_dir = static_dir or Path(__file__).parent / "static"
    if frontend_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount(
            "/",
            StaticFiles(directory=str(frontend_dir), html=True),
            name="frontend",
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def localhost_host_guard(request: Request, call_next):
        hostname = request.url.hostname
        is_huggingface_host = (
            config.public_demo_mode and hostname is not None and hostname.endswith(".hf.space")
        )
        if hostname not in config.allowed_hosts and not is_huggingface_host:
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "host_not_allowed",
                        "message": "The request host is not configured for NetPulse.",
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
