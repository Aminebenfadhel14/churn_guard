"""Modeles SQLAlchemy (Couche Authentification / multi-organisation).

Deux tables : ``organisations`` (un tenant = une entreprise cliente) et
``utilisateurs`` (rattaches a une organisation via ``organisation_id``).
Le username reste unique globalement (pas de selecteur d'organisation au
login, voir app/api/routes.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

    utilisateurs: Mapped[list["Utilisateur"]] = relationship(back_populates="organisation")


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    # Nullable : les comptes crees avant l'ajout de ce champ n'en ont pas
    # encore. Tant qu'il est absent, la connexion reste a une seule etape
    # (pas de code de verification) - voir app/api/routes.py::login.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    nom_complet: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="operateur")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)

    organisation: Mapped["Organisation"] = relationship(back_populates="utilisateurs")

    def public(self) -> dict[str, str | None]:
        return {
            "username": self.username,
            "email": self.email,
            "nom_complet": self.nom_complet,
            "role": self.role,
        }


class CodeOtp(Base):
    """Code de verification a usage unique envoye par email lors de la connexion.

    Un seul code actif par utilisateur : ``generer_code_otp`` invalide les
    codes precedents non utilises avant d'en creer un nouveau (voir
    app/auth/otp.py).
    """

    __tablename__ = "codes_otp"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tentatives: Mapped[int] = mapped_column(default=0)
    utilise: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant)
