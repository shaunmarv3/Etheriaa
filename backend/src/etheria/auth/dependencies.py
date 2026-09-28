"""FastAPI dependencies for auth. They read clients from app.state, which the
api factory populates (settings, db, redis)."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from etheria.auth.service import AuthService, ClientMeta
from etheria.auth.tokens import InvalidToken, decode_access_token
from etheria.cache.rate_limit import RateLimiter
from etheria.core.errors import Forbidden, NotAuthenticated

_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def get_auth_service(request: Request) -> AuthService:
    return AuthService(request.app.state.db, request.app.state.settings)


def get_rate_limiter(request: Request) -> RateLimiter:
    return RateLimiter(request.app.state.redis)


def client_meta(request: Request) -> ClientMeta:
    user_agent = (request.headers.get("user-agent") or "")[:512] or None
    return ClientMeta(ip=request.client.host if request.client else None, user_agent=user_agent)


async def current_user_id(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UUID:
    if credentials is None:
        raise NotAuthenticated("Sign in required", headers=_CHALLENGE)
    secret = request.app.state.settings.jwt_secret.get_secret_value()
    try:
        return decode_access_token(credentials.credentials, secret).user_id
    except InvalidToken:
        raise NotAuthenticated(
            "Your session has expired, please sign in again",
            code="token_invalid",
            headers=_CHALLENGE,
        ) from None


def require_same_origin(request: Request) -> None:
    """CSRF guard for the cookie-authenticated endpoints (spec 9)."""
    origin = request.headers.get("origin")
    if (
        request.headers.get("x-requested-with") is None
        or origin not in request.app.state.settings.cors_origins
    ):
        raise Forbidden("Cross-site request blocked", code="csrf_failed")


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
ClientMetaDep = Annotated[ClientMeta, Depends(client_meta)]
CurrentUserId = Annotated[UUID, Depends(current_user_id)]
