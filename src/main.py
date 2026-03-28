from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.agents import router as agents_router
from src.api.completions import router as completions_router
from src.api.metrics_endpoint import router as metrics_router
from src.api.providers import router as providers_router
from src.core.config import settings
from src.providers.seed import seed_providers
from src.telemetry.logging import configure_logging
from src.telemetry.middleware import TracingMiddleware
from src.telemetry.setup import init_telemetry

configure_logging(level=settings.LOG_LEVEL)
init_telemetry()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await seed_providers()
    yield


app = FastAPI(
    title="LLM Agent Platform",
    description="API gateway for LLM requests with load balancing, agent registry, and telemetry",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(TracingMiddleware)
app.include_router(completions_router)
app.include_router(metrics_router)
app.include_router(agents_router)
app.include_router(providers_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
