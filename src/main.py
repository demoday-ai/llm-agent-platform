from fastapi import FastAPI

app = FastAPI(
    title="LLM Agent Platform",
    description="API gateway for LLM requests with load balancing, agent registry, and telemetry",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
