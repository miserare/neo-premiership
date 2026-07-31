"""Administrative command line.

    python -m app.cli create-admin --username admin
    python -m app.cli reset-password --username admin
    python -m app.cli list-admins
    python -m app.cli revoke-sessions --username admin

The password is always read from a hidden prompt. It is never accepted as an
argument, so it cannot land in shell history, the process table, or CI logs.
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.admin import AdminUser
from app.security.passwords import hash_password, validate_password_strength
from app.security.sessions import revoke_all_for_user


def _prompt_new_password() -> str:
    if not sys.stdin.isatty():
        raise SystemExit(
            "Refusing to read a password from a non-interactive stream.\n"
            "Run this command in a terminal so the input can be hidden."
        )
    for _ in range(3):
        password = getpass.getpass("New password (input hidden): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords did not match. Try again.", file=sys.stderr)
            continue
        try:
            validate_password_strength(password)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            continue
        return password
    raise SystemExit("Too many failed attempts; no change was made.")


async def create_admin(username: str) -> int:
    username = username.strip().lower()
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(AdminUser).where(AdminUser.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            print(
                f"Administrator {username!r} already exists. "
                f"Use `reset-password` to change its password.",
                file=sys.stderr,
            )
            return 1

        password = _prompt_new_password()
        db.add(AdminUser(username=username, password_hash=hash_password(password)))
        await db.commit()

    print(f"Created administrator {username!r}.")
    return 0


async def reset_password(username: str) -> int:
    username = username.strip().lower()
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(AdminUser).where(AdminUser.username == username))
        ).scalar_one_or_none()
        if user is None:
            print(f"No administrator named {username!r}.", file=sys.stderr)
            return 1

        password = _prompt_new_password()
        user.password_hash = hash_password(password)
        await db.commit()
        # Rotating the credential must invalidate anything issued under the old one.
        revoked = await revoke_all_for_user(db, user.id)

    print(f"Password updated for {username!r}. Revoked {revoked} active session(s).")
    return 0


async def list_admins() -> int:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(AdminUser).order_by(AdminUser.username))).scalars().all()
    if not rows:
        print("No administrators exist yet. Create one with `create-admin`.")
        return 0
    print(f"{'USERNAME':<24} {'ACTIVE':<8} CREATED")
    for row in rows:
        print(f"{row.username:<24} {str(row.is_active):<8} {row.created_at:%Y-%m-%d %H:%M}")
    return 0


async def revoke_sessions(username: str) -> int:
    username = username.strip().lower()
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(AdminUser).where(AdminUser.username == username))
        ).scalar_one_or_none()
        if user is None:
            print(f"No administrator named {username!r}.", file=sys.stderr)
            return 1
        revoked = await revoke_all_for_user(db, user.id)
    print(f"Revoked {revoked} active session(s) for {username!r}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin", help="Create the first administrator")
    create.add_argument("--username", required=True)

    reset = sub.add_parser("reset-password", help="Change an administrator's password")
    reset.add_argument("--username", required=True)

    sub.add_parser("list-admins", help="List administrators")

    revoke = sub.add_parser("revoke-sessions", help="Revoke all sessions for an administrator")
    revoke.add_argument("--username", required=True)

    args = parser.parse_args(argv)

    if args.command == "create-admin":
        return asyncio.run(create_admin(args.username))
    if args.command == "reset-password":
        return asyncio.run(reset_password(args.username))
    if args.command == "list-admins":
        return asyncio.run(list_admins())
    if args.command == "revoke-sessions":
        return asyncio.run(revoke_sessions(args.username))
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
