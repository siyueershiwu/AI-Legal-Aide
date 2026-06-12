"""add knowledge_documents and knowledge_chunks tables for RAG

Revision ID: 0003_add_knowledge_tables
Revises: 0002_align_schema
Create Date: 2026-06-12

为米哈游 RAG 知识库新增两张表：
- knowledge_documents: 文档元信息（标题/游戏/分类/版本/来源/chunk 数/字符数）
- knowledge_chunks: 文本切片正文 + sha256 去重 hash（向量存 ChromaDB）
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_add_knowledge_tables"
down_revision = "0002_align_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ⚠️ 与 files/users 保持排序规则一致（utf8mb4_unicode_ci），否则 FK 报 3780
    _collate = "utf8mb4_unicode_ci"
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("game", sa.String(32), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("version", sa.String(32), nullable=False, server_default="latest"),
        sa.Column("source_type", sa.String(16), nullable=False, server_default="upload"),
        sa.Column(
            "file_id",
            sa.String(36, collation=_collate),
            sa.ForeignKey("files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("char_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "owner_id",
            sa.String(36, collation=_collate),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate=_collate,
    )
    op.create_index("ix_kb_doc_game", "knowledge_documents", ["game"])
    op.create_index("ix_kb_doc_category", "knowledge_documents", ["category"])
    op.create_index(
        "ix_kb_doc_game_category_version",
        "knowledge_documents",
        ["game", "category", "version"],
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(36, collation=_collate), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36, collation=_collate),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column("content_hash", sa.String(64, collation=_collate), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunk_doc_index"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate=_collate,
    )
    op.create_index("ix_kb_chunk_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_kb_chunk_content_hash", "knowledge_chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_kb_chunk_content_hash", table_name="knowledge_chunks")
    op.drop_index("ix_kb_chunk_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_kb_doc_game_category_version", table_name="knowledge_documents")
    op.drop_index("ix_kb_doc_category", table_name="knowledge_documents")
    op.drop_index("ix_kb_doc_game", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
