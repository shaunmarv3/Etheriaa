"""/auth endpoints (spec 9, 10)."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response

from etheria.auth.dependencies import (
    AuthServiceDep,
    ClientMetaDep,
    CurrentUserId,
    RateLimiterDep,
    require_same_origin,
)
from etheria.auth.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from etheria.auth.service import IssuedTokens
from etheria.core.errors import NotAuthenticated
from etheria.core.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "etheria_refresh"
LOGIN_LIMIT = (5, 60)  # per IP + email, per minute
REGISTER_LIMIT = (5, 60)  # per IP, per minute
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _token_out(issued: IssuedTokens, response: Response, settings: Settings) -> TokenOut:
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86_400,
        path="/auth",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return TokenOut(
        access_token=issued.access_token, expires_in=issued.expires_in, user=issued.user
    )


@router.post("/register", status_code=201)
async def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    svc: AuthServiceDep,
    limiter: RateLimiterDep,
    meta: ClientMetaDep,
) -> TokenOut:
    await limiter.enforce(f"register:{meta.ip}", *REGISTER_LIMIT)
    issued = await svc.register(body.email, body.password, body.display_name, meta)
    return _token_out(issued, response, _settings(request))


@router.post("/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    svc: AuthServiceDep,
    limiter: RateLimiterDep,
    meta: ClientMetaDep,
) -> TokenOut:
    await limiter.enforce(f"login:{meta.ip}:{body.email}", *LOGIN_LIMIT)
    issued = await svc.login(body.email, body.password, meta)
    return _token_out(issued, response, _settings(request))


@router.post("/refresh", dependencies=[Depends(require_same_origin)])
async def refresh(
    request: Request,
    response: Response,
    svc: AuthServiceDep,
    meta: ClientMetaDep,
    token: RefreshCookie = None,
) -> TokenOut:
    if not token:
        raise NotAuthenticated(
            "Your session has expired, please sign in again", code="invalid_refresh"
        )
    issued = await svc.refresh(token, meta)
    return _token_out(issued, response, _settings(request))


@router.post("/logout", status_code=204, dependencies=[Depends(require_same_origin)])
async def logout(
    request: Request, svc: AuthServiceDep, meta: ClientMetaDep, token: RefreshCookie = None
) -> Response:
    await svc.logout(token, meta)
    response = Response(status_code=204)
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/auth",
        httponly=True,
        samesite="lax",
        secure=_settings(request).cookie_secure,
    )
    return response


@router.get("/me")
async def me(user_id: CurrentUserId, svc: AuthServiceDep) -> UserOut:
    return await svc.get_user(user_id)
