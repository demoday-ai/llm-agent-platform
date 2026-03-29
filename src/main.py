from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from src.api.agents import router as agents_router
from src.api.completions import router as completions_router
from src.api.metrics_endpoint import router as metrics_router
from src.api.providers import router as providers_router
from src.auth.middleware import AuthMiddleware
from src.core.config import settings
from src.guardrails.pipeline import GuardrailsPipeline
from src.guardrails.prompt_injection import PromptInjectionGuardrail
from src.guardrails.secret_leak import SecretLeakGuardrail
from src.providers.seed import seed_providers
from src.telemetry.logging import configure_logging
from src.telemetry.middleware import TracingMiddleware
from src.telemetry.setup import init_telemetry

configure_logging(level=settings.LOG_LEVEL)
init_telemetry()

guardrails_pipeline = GuardrailsPipeline(
    guardrails=[PromptInjectionGuardrail(), SecretLeakGuardrail()],
    enabled=settings.GUARDRAILS_ENABLED,
)


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

app.add_middleware(AuthMiddleware)
app.add_middleware(TracingMiddleware)
app.include_router(completions_router)
app.include_router(metrics_router)
app.include_router(agents_router)
app.include_router(providers_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def custom_openapi():  # noqa: ANN202
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "Master token или agent token",
        },
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
