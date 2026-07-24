"""ajout mot_de_passe_temporaire utilisateurs

Revision ID: a1b2c3d4e5f6
Revises: 27f5284bedc6
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '27f5284bedc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default=false() : les comptes existants ne sont pas concernes par
    # le changement force de mot de passe (leur mot de passe n'est pas provisoire).
    op.add_column(
        'utilisateurs',
        sa.Column(
            'mot_de_passe_temporaire',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('utilisateurs', 'mot_de_passe_temporaire')
