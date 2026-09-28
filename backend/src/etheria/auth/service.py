"""Authentication use cases (spec 9): argon2id passwords, 15-minute access
tokens, and rotating refresh tokens whose reuse revokes the whole family."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.auth.passwords import dummy_hash, hash_password, needs_rehash, verify_password
from etheria.auth.schemas import UserOut
from etheria.auth.tokens import create_access_token, hash_refresh_token, new_refresh_token
from etheria.core.clock import utcnow
from etheria.core.errors import AppError, Conflict, NotAuthenticated
from etheria.core.settings import Settings
from etheria.db.models import RefreshToken, User
from etheria.db.repositories import audit, refresh_tokens, users
from etheria.db.session import Database

INVALID_CREDENTIALS = "Invalid email or password"
SESSION_EXPIRED = "Your session has expired, please sign in again"
EMAIL_TAKEN = "An account with this email already exists"


@dataclass(frozen=True)
class ClientMeta:
    ip: str | None
    user_agent: str | None


@dataclass(frozen=True)
class IssuedTokens:
    user: UserOut
    access_token: str
    expires_in: int
    refresh_token: str


def _normalise(email: str) -> str:
    return email.strip().lower()


def _password_ok(user: User | None, password: str) -> bool:
    # Unknown emails still pay for one hash check, so timing does not reveal accounts.
    return verify_password(user.password_hash if user else dummy_hash(), password)


class AuthService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    async def register(
        self, email: str, password: str, display_name: str | None, meta: ClientMeta
    ) -> IssuedTokens:
        email = _normalise(email)
        password_hash = await asyncio.to_thread(hash_password, password)  # CPU-bound
        try:
            async with self._db.system() as s:
                if await users.get_by_email(s, email) is not None:
                    raise Conflict(EMAIL_TAKEN, code="email_taken")
                user = await users.create(
                    s, email=email, password_hash=password_hash, display_name=display_name
                )
                issued = await self._issue(s, user, family_id=uuid4(), meta=meta)
                await audit.record(
                    s, "register", user_ref=str(user.id), ip=meta.ip, user_agent=meta.user_agent
                )
        except IntegrityError as e:  # a concurrent registration won the unique index
            raise Conflict(EMAIL_TAKEN, code="email_taken") from e
        return issued

    async def login(self, email: str, password: str, meta: ClientMeta) -> IssuedTokens:
        email = _normalise(email)
        issued: IssuedTokens | None = None
        async with self._db.system() as s:
            user = await users.get_by_email(s, email)
            if user is None or not await asyncio.to_thread(_password_ok, user, password):
                await audit.record(
                    s,
                    "login_failed",
                    user_ref=str(user.id) if user else None,
                    ip=meta.ip,
                    user_agent=meta.user_agent,
                )
            else:
                if needs_rehash(user.password_hash):
                    user.password_hash = await asyncio.to_thread(hash_password, password)
                issued = await self._issue(s, user, family_id=uuid4(), meta=meta)
                await audit.record(
                    s, "login", user_ref=str(user.id), ip=meta.ip, user_agent=meta.user_agent
                )
        if issued is None:
            raise NotAuthenticated(INVALID_CREDENTIALS, code="invalid_credentials")
        return issued

    async def refresh(self, raw_token: str, meta: ClientMeta) -> IssuedTokens:
        now = utcnow()
        failure: AppError | None = None
        issued: IssuedTokens | None = None
        async with self._db.system() as s:
            row = await refresh_tokens.get_for_update(s, hash_refresh_token(raw_token))
            if row is None:
                failure = NotAuthenticated(SESSION_EXPIRED, code="invalid_refresh")
            elif row.replaced_by is not None:
                # A token we already rotated came back: someone holds a copy. Kill the family.
                await refresh_tokens.revoke_family(s, row.family_id, now)
                await audit.record(
                    s,
                    "refresh_token_reuse",
                    user_ref=str(row.user_id),
                    ip=meta.ip,
                    user_agent=meta.user_agent,
                    details={"family_id": str(row.family_id)},
                )
                failure = NotAuthenticated(SESSION_EXPIRED, code="refresh_reused")
            elif row.revoked_at is not None or row.expires_at <= now:
                failure = NotAuthenticated(SESSION_EXPIRED, code="invalid_refresh")
            else:
                user = await users.get(s, row.user_id)
                if user is None:
                    failure = NotAuthenticated(SESSION_EXPIRED, code="invalid_refresh")
                else:
                    issued = await self._issue(
                        s, user, family_id=row.family_id, meta=meta, replaces=row, now=now
                    )
        # Raised after the transaction commits, so revocation and audit rows persist.
        if failure is not None:
            raise failure
        assert issued is not None
        return issued

    async def logout(self, raw_token: str | None, meta: ClientMeta) -> None:
        if not raw_token:
            return
        async with self._db.system() as s:
            row = await refresh_tokens.get_for_update(s, hash_refresh_token(raw_token))
            if row is not None:
                await refresh_tokens.revoke_family(s, row.family_id, utcnow())
                await audit.record(
                    s, "logout", user_ref=str(row.user_id), ip=meta.ip, user_agent=meta.user_agent
                )

    async def get_user(self, user_id: UUID) -> UserOut:
        async with self._db.system() as s:
            user = await users.get(s, user_id)
        if user is None:
            raise NotAuthenticated(SESSION_EXPIRED, code="token_invalid")
        return UserOut.model_validate(user)

    async def _issue(
        self,
        s: AsyncSession,
        user: User,
        *,
        family_id: UUID,
        meta: ClientMeta,
        replaces: RefreshToken | None = None,
        now: datetime | None = None,
    ) -> IssuedTokens:
        now = now or utcnow()
        raw = new_refresh_token()
        row = await refresh_tokens.create(
            s,
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id,
            expires_at=now + timedelta(days=self._settings.refresh_token_ttl_days),
            user_agent=meta.user_agent,
        )
        if replaces is not None:
            replaces.revoked_at = now
            replaces.replaced_by = row.id
        ttl = self._settings.access_token_ttl_seconds
        access = create_access_token(user.id, self._settings.jwt_secret.get_secret_value(), ttl)
        return IssuedTokens(UserOut.model_validate(user), access, ttl, raw)
