"""Bearer token authentication middleware for FastAPI."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.auth.token_store import validate_token

if TYPE_CHECKING:
    from fastapi import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)

PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
})

AGENT_ALLOWED_PREFIXES: tuple[str, ...] = (
    "/v1/chat/completions",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Check Authorization: Bearer <token> on non-public endpoints."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        if path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Unauthorized request to %s - missing/invalid auth header", path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: missing or invalid Bearer token"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        token_info = await validate_token(token)

        if token_info is None:
            logger.warning("Unauthorized request to %s - invalid token", path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: invalid token"},
            )

        if not token_info.is_master:
            allowed = any(path.startswith(p) for p in AGENT_ALLOWED_PREFIXES)
            if not allowed:
                logger.warning(
                    "Forbidden: agent %s tried to access %s",
                    token_info.agent_id,
                    path,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Forbidden: agent tokens can only access /v1/chat/completions",
                    },
                )

        request.state.token_info = token_info
        return await call_next(request)
