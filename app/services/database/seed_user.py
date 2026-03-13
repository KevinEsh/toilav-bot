"""Seed a user into the PostgreSQL database using SQLModel."""

import sys
from os import environ
from pathlib import Path

# Allow running from repo root by adding the database package to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Override host for running outside Docker (localhost instead of container name)
environ["POSTGRES_HOST"] = "localhost"
environ.setdefault("DATABASE_ENGINE", "postgresql")

from chatbot_schema import UserRole, Users
from dbconfig import engine
from sqlmodel import Session


def seed_user():
    user = Users(
        u_email="admin@toilav.com",
        u_username="admin_kevin",
        u_password_hash="$2b$12$fakehash_admin_placeholder",
        u_role=UserRole.ADMIN,
        u_is_active=True,
    )
    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"User created: id={user.u_id}, email={user.u_email}, role={user.u_role.value}")


if __name__ == "__main__":
    seed_user()
