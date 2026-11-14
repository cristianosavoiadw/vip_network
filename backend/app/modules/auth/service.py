"""Users, sessions (JWT + rotating refresh cookie) and one-time e-mail links."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict, NotFound, Unauthorized
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from app.modules.auth.models import AuthToken, RefreshToken, User

LINK_HOURS = {"verify": 48, "activate": 72, "reset": 2}
GENERIC_LOGIN_ERROR = "E-mail ou senha incorretos."


def normalize_email(raw: str) -> str:
    try:
        return validate_email(raw.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise AppError("E-mail inválido.", code="email_invalid") from exc


def validate_password(raw: str) -> str:
    if len(raw) < 8:
        raise AppError("A senha precisa ter pelo menos 8 caracteres.", code="password_short")
    if len(raw) > 128:
        raise AppError("A senha pode ter no máximo 128 caracteres.", code="password_long")
    return raw


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return (
        await session.execute(select(User).where(User.email == email.lower()))
    ).scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str | None,
    kind: str = "member",
    is_superuser: bool = False,
    admin_role: str = "",
    org_id: uuid.UUID | None = None,
    is_org_owner: bool = False,
    departments: list[str] | None = None,
    full_name: str = "",
    job_title: str = "",
    phone: str = "",
    cnpj_relation: str = "",
    status: str = "active",
) -> User:
    email = normalize_email(email)
    if await get_by_email(session, email):
        raise Conflict("Já existe uma conta com este e-mail.", code="email_taken")
    user = User(
        email=email,
        password_hash=hash_password(validate_password(password)) if password else "",
        kind=kind,
        is_superuser=is_superuser,
        admin_role=admin_role,
        org_id=org_id,
        is_org_owner=is_org_owner,
        departments=departments or [],
        full_name=full_name.strip(),
        job_title=job_title.strip(),
        phone=phone.strip(),
        cnpj_relation=cnpj_relation,
        status=status,
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(session: AsyncSession, email: str, password: str, *, kind: str) -> User:
    try:
        email = normalize_email(email)
    except AppError as exc:
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="bad_credentials") from exc
    user = await get_by_email(session, email)
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise Unauthorized(GENERIC_LOGIN_ERROR, code="bad_credentials")
    if user.kind != kind:
        area = "painel da equipe" if user.kind == "admin" else "área das empresas"
        raise Unauthorized(f"Esta conta entra pelo {area}.", code="wrong_area")
    if user.status != "active":
        raise Unauthorized("Este acesso está bloqueado. Fale com o suporte.", code="user_blocked")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    return user


async def open_session(
    session: AsyncSession, user: User, *, user_agent: str | None, ip: str | None
) -> tuple[str, int, str]:
    """Returns (access_token, expires_in, raw_refresh_token)."""
    access, expires_in = create_access_token(user.id, user.kind)
    raw, digest = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=digest,
            expires_at=refresh_expiry(),
            user_agent=(user_agent or "")[:300],
            ip=ip,
        )
    )
    await session.flush()
    return access, expires_in, raw


async def rotate(
    session: AsyncSession, raw: str, *, user_agent: str | None, ip: str | None
) -> tuple[User, str, int, str]:
    row = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise Unauthorized("Sua sessão expirou. Entre de novo.", code="refresh_invalid")
    user = await session.get(User, row.user_id)
    if user is None or user.status != "active":
        raise Unauthorized("Este acesso está bloqueado.", code="user_blocked")
    row.revoked_at = now
    access, expires_in, new_raw = await open_session(session, user, user_agent=user_agent, ip=ip)
    return user, access, expires_in, new_raw


async def close_session(session: AsyncSession, raw: str) -> None:
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(raw), RefreshToken.revoked_at.is_(None)
        )
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


# ------------------------------------------------------------------ one-time links


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_link(session: AsyncSession, user: User, purpose: str) -> str:
    raw = secrets.token_urlsafe(32)
    session.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_digest(raw),
            expires_at=datetime.now(UTC) + timedelta(hours=LINK_HOURS[purpose]),
        )
    )
    await session.flush()
    return raw


async def peek_link(session: AsyncSession, raw: str, purpose: str) -> tuple[AuthToken, User]:
    row = (
        await session.execute(
            select(AuthToken).where(
                AuthToken.token_hash == _digest(raw), AuthToken.purpose == purpose
            )
        )
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at <= datetime.now(UTC):
        raise NotFound("Este link expirou ou já foi usado. Peça um novo.", code="link_invalid")
    user = await session.get(User, row.user_id)
    if user is None:
        raise NotFound("Este link expirou ou já foi usado. Peça um novo.", code="link_invalid")
    return row, user


async def consume_link(session: AsyncSession, row: AuthToken) -> None:
    """Spend the link with a conditional UPDATE: a double click cannot use it twice."""
    result = await session.execute(
        update(AuthToken)
        .where(AuthToken.id == row.id, AuthToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        raise NotFound("Este link já foi usado.", code="link_invalid")


async def set_password(session: AsyncSession, user: User, password: str) -> None:
    user.password_hash = hash_password(validate_password(password))
    await revoke_all(session, user.id)


async def set_password_by_email(session: AsyncSession, *, email: str, password: str) -> None:
    user = await get_by_email(session, normalize_email(email))
    if user is None:
        raise NotFound("Usuário não encontrado.")
    await set_password(session, user, password)
