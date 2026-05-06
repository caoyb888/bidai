"""add parsed_text_path to kb_documents

Revision ID: fabf9f0368a7
Revises:
Create Date: 2026-05-06 13:53:01.215631

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fabf9f0368a7"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "kb_documents",
        sa.Column("parsed_text_path", sa.String(1024), nullable=True),
        schema="knowledge",
    )


def downgrade() -> None:
    op.drop_column("kb_documents", "parsed_text_path", schema="knowledge")
