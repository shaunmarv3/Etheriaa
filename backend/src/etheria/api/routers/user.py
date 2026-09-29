"""Account erasure, DELETE /user (spec 7, 10, 11.2). One transaction removes the
user's rows and checkpoint threads; the encrypted files go once it commits. The
audit log is kept for its one-year retention, with the user's reference replaced
by an HMAC of the user ID so no row names them."""

import hashlib
import hmac
from uuid import UUID

from fastapi import APIRouter, Request, Response

from etheria.api.routers.upload import StoreDep
from etheria.auth.dependencies import ClientMetaDep, CurrentUserId
from etheria.auth.router import REFRESH_COOKIE
from etheria.db.repositories import audit, users

router = APIRouter(prefix="/user", tags=["user"])


def pseudonym(user_id: UUID, key: bytes) -> str:
    digest = hmac.new(key, f"audit-user-ref:{user_id}".encode(), hashlib.sha256).hexdigest()
    return f"erased:{digest}"


@router.delete("", status_code=204)
async def erase(
    request: Request, user_id: CurrentUserId, meta: ClientMetaDep, store: StoreDep
) -> Response:
    settings = request.app.state.settings
    ref = pseudonym(user_id, settings.data_encryption_key.get_secret_value().encode())
    async with request.app.state.db.for_user(user_id) as s:
        keys = await users.erase(s, user_id, ref)
        await audit.record(s, "erasure", user_ref=ref, ip=meta.ip, user_agent=meta.user_agent)
    for key in keys:
        store.delete(key)
    response = Response(status_code=204)
    response.delete_cookie(
        REFRESH_COOKIE, path="/auth", httponly=True, samesite="lax", secure=settings.cookie_secure
    )
    return response
