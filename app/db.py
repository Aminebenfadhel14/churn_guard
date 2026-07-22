"""Connexion base de donnees (Couche Authentification / multi-organisation).

SQLAlchemy, SQLite en local (fichier ``churnguard.db``) et Postgres en
production — meme jeu de modeles, seule ``settings.database_url`` change.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Dependance FastAPI : fournit une session DB, refermee apres la requete."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
