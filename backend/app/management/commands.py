"""Management commands behind ``manage.py`` (Django-style, same as AIDeed and BR Licitar).

Each command is a plain function that receives parsed arguments and returns an exit code.
Prompts loop until the answer validates; every prompt has a flag; ``--noinput`` fails instead
of asking.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import subprocess
import sys
from collections.abc import Callable

from app.core.config import get_settings
from app.core.errors import AppError


class CommandError(Exception):
    pass


def _email(value: str) -> str:
    from app.modules.auth.service import normalize_email

    try:
        return normalize_email(value)
    except AppError as exc:
        raise CommandError(exc.message) from exc


def _password(value: str) -> str:
    from app.modules.auth.service import validate_password

    try:
        return validate_password(value)
    except AppError as exc:
        raise CommandError(exc.message) from exc


def _prompt(label: str, *, validator: Callable[[str], str]) -> str:
    while True:
        try:
            raw = input(f"{label}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada.")
            raise SystemExit(1) from None
        if not raw:
            print("  Este campo não pode ficar em branco.")
            continue
        try:
            return validator(raw)
        except CommandError as exc:
            print(f"  {exc}")


def _prompt_password() -> str:
    while True:
        try:
            first = getpass.getpass("Senha: ")
            second = getpass.getpass("Senha (de novo): ")
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada.")
            raise SystemExit(1) from None
        if first != second:
            print("  As senhas não conferem. Tente de novo.")
            continue
        try:
            return _password(first)
        except CommandError as exc:
            print(f"  {exc}")


def _run(coro_factory: Callable[[], object]) -> object:
    from app.db.session import engine

    async def wrapper() -> object:
        try:
            return await coro_factory()  # type: ignore[misc]
        finally:
            await engine.dispose()

    return asyncio.run(wrapper())


def createsuperuser_command(args: argparse.Namespace) -> int:
    """VIP Network team administrator (``/admin``). The e-mail is the login."""
    env_password = os.getenv("VIP_SUPERUSER_PASSWORD")
    if args.noinput:
        if not args.email:
            raise CommandError("Com --noinput informe: --email")
        password = args.password or env_password
        if not password:
            raise CommandError("Com --noinput informe --password ou VIP_SUPERUSER_PASSWORD.")
        email, password = _email(args.email), _password(password)
    else:
        print(f"Criar superusuário do painel da equipe (ambiente: {get_settings().env})")
        email = _email(args.email) if args.email else _prompt("E-mail", validator=_email)
        given = args.password or env_password
        password = _password(given) if given else _prompt_password()

    async def run() -> str:
        from app.db.session import SessionLocal
        from app.modules.auth import service

        async with SessionLocal() as session:
            try:
                user = await service.create_user(
                    session,
                    email=email,
                    password=password,
                    kind="admin",
                    is_superuser=True,
                    admin_role="owner",
                )
                await session.commit()
            except AppError as exc:
                raise CommandError(exc.message) from exc
            return str(user.id)

    user_id = _run(run)
    print(f"Superusuário criado: {email} ({user_id}). Entre em /admin/entrar.")
    return 0


def changepassword_command(args: argparse.Namespace) -> int:
    email = _email(args.email) if args.email else _prompt("E-mail", validator=_email)
    password = _password(args.password) if args.password else _prompt_password()

    async def run() -> None:
        from app.db.session import SessionLocal
        from app.modules.auth import service

        async with SessionLocal() as session:
            try:
                await service.set_password_by_email(session, email=email, password=password)
                await session.commit()
            except AppError as exc:
                raise CommandError(exc.message) from exc

    _run(run)
    print(f"Senha alterada para {email}.")
    return 0


def migrate_command(args: argparse.Namespace) -> int:
    return subprocess.call([sys.executable, "-m", "alembic", "upgrade", args.revision or "head"])


def makemigrations_command(args: argparse.Namespace) -> int:
    return subprocess.call(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", args.message]
    )


def runserver_command(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", args.host]
    cmd += ["--port", str(args.port or get_settings().port)]
    if not args.noreload:
        cmd.append("--reload")
    return subprocess.call(cmd)


def check_command(_: argparse.Namespace) -> int:
    from sqlalchemy import text

    s = get_settings()
    print(f"Ambiente: {s.env} · porta {s.port}")
    print(f"Stripe: {'real' if s.stripe_live else 'simulado (sem chave)'}")
    print(f"E-mail: {s.email_provider or 'só registro em log'}")
    print(f"WeOS: {'configurado' if s.weos_api_token else 'cálculo local'}")

    async def files() -> str:
        from app.core import storage

        return await storage.check()

    try:
        print(f"Arquivos: {asyncio.run(files())}")
    except Exception as exc:  # noqa: BLE001
        print(f"Arquivos: falhou ({exc.__class__.__name__}: {exc})")

    async def run() -> str | None:
        from app.db.session import engine

        async with engine.connect() as conn:
            return (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()

    try:
        version = _run(run)
    except Exception as exc:  # noqa: BLE001 - report, do not crash
        print(f"Banco: falhou ({exc.__class__.__name__}: {exc})")
        return 1
    print(f"Banco: ok (migração {version})")
    return 0


def checkmail_command(_: argparse.Namespace) -> int:
    from app.core import mail

    try:
        result = asyncio.run(mail.check_connection())
    except mail.MailError as exc:
        raise CommandError(f"Servidor de e-mail: {exc}") from exc
    print(f"Servidor de e-mail: {result}")
    return 0


def sendtestemail_command(args: argparse.Namespace) -> int:
    from app.core import mail

    to = _email(args.to)
    try:
        sent = asyncio.run(
            mail.send_mail(
                to=to,
                subject="Teste de e-mail · VIP Network",
                text="Este é um e-mail de teste da VIP Network.\n",
                html="<p>Este é um e-mail de teste da <strong>VIP Network</strong>.</p>",
            )
        )
    except mail.MailError as exc:
        raise CommandError(f"Falhou: {exc}") from exc
    print("Enviado." if sent else "E-mail desligado (VIP_EMAIL_PROVIDER vazio): só registrado.")
    return 0


def seed_command(args: argparse.Namespace) -> int:
    """Platform defaults (settings, e-mail templates, mentor) and, with --demo, example data."""

    async def run() -> list[str]:
        from app.db.session import SessionLocal
        from app.modules.admin import seed

        async with SessionLocal() as session:
            out = await seed.run(session, demo=args.demo)
            await session.commit()
            return out

    for line in _run(run):  # type: ignore[union-attr]
        print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manage.py", description="Comandos da VIP Network")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("createsuperuser", help="Cria um administrador do painel da equipe")
    p.add_argument("--email")
    p.add_argument("--password", help="Prefira a variável VIP_SUPERUSER_PASSWORD")
    p.add_argument("--noinput", action="store_true")
    p.set_defaults(func=createsuperuser_command)

    p = sub.add_parser("changepassword", help="Troca a senha de um usuário")
    p.add_argument("email", nargs="?")
    p.add_argument("--password")
    p.set_defaults(func=changepassword_command)

    p = sub.add_parser("migrate", help="Aplica as migrações (alembic upgrade)")
    p.add_argument("revision", nargs="?")
    p.set_defaults(func=migrate_command)

    p = sub.add_parser("makemigrations", help="Gera uma migração a partir dos modelos")
    p.add_argument("-m", "--message", required=True)
    p.set_defaults(func=makemigrations_command)

    p = sub.add_parser("runserver", help="Sobe a API (uvicorn)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int)
    p.add_argument("--noreload", action="store_true")
    p.set_defaults(func=runserver_command)

    sub.add_parser("check", help="Confere configuração e banco").set_defaults(func=check_command)
    sub.add_parser("checkmail", help="Testa o SMTP sem enviar").set_defaults(func=checkmail_command)
    p = sub.add_parser("sendtestemail", help="Envia um e-mail de teste")
    p.add_argument("to")
    p.set_defaults(func=sendtestemail_command)

    p = sub.add_parser("seed", help="Cria configurações e modelos de e-mail padrão")
    p.add_argument("--demo", action="store_true", help="Também cria empresas de exemplo")
    p.set_defaults(func=seed_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except CommandError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
