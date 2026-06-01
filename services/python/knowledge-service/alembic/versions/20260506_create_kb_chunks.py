"""create kb_chunks table

Revision ID: 20260506_create_kb_chunks
Revises: fabf9f0368a7
Create Date: 2026-05-06 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260506_create_kb_chunks"
down_revision: str | None = "fabf9f0368a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("doc_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page_no", sa.Integer, nullable=True),
        sa.Column("section_title", sa.String(256), nullable=True),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column("chunk_type", sa.String(16), nullable=False, server_default="TEXT"),
        sa.Column("milvus_id", sa.String(128), nullable=True),
        sa.Column("embedding_model", sa.String(64), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        schema="knowledge",
    )

    # 唯一约束：同一文档内 chunk_index 唯一
    op.create_unique_constraint(
        "uq_kb_chunks_doc_index",
        "kb_chunks",
        ["doc_id", "chunk_index"],
        schema="knowledge",
    )

    # CHECK 约束
    op.create_check_constraint(
        "chk_kb_chunks_token",
        "kb_chunks",
        sa.text("token_count > 0 AND token_count <= 600"),
        schema="knowledge",
    )
    op.create_check_constraint(
        "chk_kb_chunks_type",
        "kb_chunks",
        sa.text("chunk_type IN ('TEXT', 'TABLE', 'IMAGE_CAPTION')"),
        schema="knowledge",
    )

    # 索引
    op.create_index(
        "idx_kb_chunks_doc_id",
        "kb_chunks",
        ["doc_id"],
        schema="knowledge",
    )
    op.create_index(
        "idx_kb_chunks_milvus_id",
        "kb_chunks",
        ["milvus_id"],
        schema="knowledge",
    )


def downgrade() -> None:
    op.drop_table("kb_chunks", schema="knowledge")
