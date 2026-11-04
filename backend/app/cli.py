"""Comandos administrativos: python -m app.cli <comando>."""

import argparse
import getpass
import logging
import subprocess
import sys

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Role, User

log = logging.getLogger("forja.cli")


def migrate() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


def ensure_admin(email: str, password: str, name: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if user:
            if user.role != Role.admin:
                user.role = Role.admin
                db.commit()
            print(f"admin já existe: {email}")
            return
        db.add(User(email=email.lower(), name=name, password_hash=hash_password(password), role=Role.admin))
        db.commit()
        print(f"admin criado: {email}")
    finally:
        db.close()


def seed(with_music: bool = True) -> None:
    from app.ai.music import MOODS
    from app.seed.templates import seed_templates
    from app.services.pipeline import ensure_system_music

    db = SessionLocal()
    try:
        print(f"templates criados: {seed_templates(db)}")
        if with_music:
            for mood in MOODS:
                ensure_system_music(db, mood)
            print("trilhas do sistema prontas")
    finally:
        db.close()


def init() -> None:
    s = get_settings()
    migrate()
    seed()
    if s.admin_email and s.admin_password:
        ensure_admin(s.admin_email, s.admin_password, s.admin_name)


def main() -> None:
    p = argparse.ArgumentParser(prog="forja")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="migrações + seeds + admin do .env")
    sub.add_parser("migrate")
    sub.add_parser("seed")
    ca = sub.add_parser("create-admin")
    ca.add_argument("--email", required=True)
    ca.add_argument("--name", default="Administrador")
    args = p.parse_args()
    if args.cmd == "init":
        init()
    elif args.cmd == "migrate":
        migrate()
    elif args.cmd == "seed":
        seed()
    elif args.cmd == "create-admin":
        pw = getpass.getpass("Senha: ")
        if len(pw) < 8:
            sys.exit("senha muito curta")
        ensure_admin(args.email, pw, args.name)


if __name__ == "__main__":
    main()
