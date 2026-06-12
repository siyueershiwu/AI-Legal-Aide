"""rename knowledge tables to legal-corpus schema

Revision ID: 0004_law_kb_schema
Revises: 0003_add_knowledge_tables
Create Date: 2026-06-12

把米哈游 RAG 知识库改造为「中国法律条文知识库」：
- TRUNCATE 旧数据（米哈游遗留无意义，且 ChromaDB collection 也会同步 reset）
- rename game → law_code (民法典 / 劳动法 / 刑法 ...)
- rename category → doc_type (statute / interpretation / commentary / scenario / boundary / diff / repeal_note / other)
- 新增 effective_date / repealed_date / issuing_body / article_range / is_current
- knowledge_chunks 新增 article_no（"第N条"，索引）
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_law_kb_schema"
down_revision = "0003_add_knowledge_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 0) 先清旧数据：FK 约束要求子表先清 ===
    # 用 DELETE 而非 TRUNCATE，规避带 FK 约束时 TRUNCATE 在 InnoDB 上的限制。
    op.execute("DELETE FROM knowledge_chunks")
    op.execute("DELETE FROM knowledge_documents")

    # === 1) 删旧索引（旧列名建立的）===
    op.drop_index("ix_kb_doc_game_category_version", table_name="knowledge_documents")
    op.drop_index("ix_kb_doc_category", table_name="knowledge_documents")
    op.drop_index("ix_kb_doc_game", table_name="knowledge_documents")

    # === 2) rename + 新增列 (knowledge_documents) ===
    # MySQL 重命名列要用 CHANGE，并复述完整类型。保持 NOT NULL + 长度，
    # server_default 仍走应用层（迁移这里不强加默认值会丢约束语义）。
    op.alter_column(
        "knowledge_documents",
        "game",
        new_column_name="law_code",
        existing_type=sa.String(32),
        existing_nullable=False,
        type_=sa.String(64),
    )
    op.alter_column(
        "knowledge_documents",
        "category",
        new_column_name="doc_type",
        existing_type=sa.String(32),
        existing_nullable=False,
        type_=sa.String(32),
    )
    # version 含义从 "latest" 改为 "current"，旧默认值用脚本统一
    op.execute("UPDATE knowledge_documents SET version = 'current' WHERE version IS NULL OR version = '' OR version = 'latest'")
    op.alter_column(
        "knowledge_documents",
        "version",
        existing_type=sa.String(32),
        existing_nullable=False,
        server_default="current",
    )

    op.add_column(
        "knowledge_documents",
        sa.Column("effective_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("repealed_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("issuing_body", sa.String(64), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("article_range", sa.String(64), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    # === 3) 新索引（按法律字段查询模式建立）===
    op.create_index("ix_kb_doc_law_code", "knowledge_documents", ["law_code"])
    op.create_index("ix_kb_doc_doc_type", "knowledge_documents", ["doc_type"])
    op.create_index("ix_kb_doc_is_current", "knowledge_documents", ["is_current"])
    op.create_index(
        "ix_kb_doc_law_type_version",
        "knowledge_documents",
        ["law_code", "doc_type", "version"],
    )

    # === 4) knowledge_chunks 加 article_no ===
    op.add_column(
        "knowledge_chunks",
        sa.Column("article_no", sa.String(16), nullable=True),
    )
    op.create_index("ix_kb_chunk_article_no", "knowledge_chunks", ["article_no"])


def downgrade() -> None:
    # 回滚到 0003 的 game/category schema。旧数据已 DELETE 不可恢复（合规风险接受）。
    op.drop_index("ix_kb_chunk_article_no", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "article_no")

    op.drop_index("ix_kb_doc_law_type_version", table_name="knowledge_documents")
    op.drop_index("ix_kb_doc_is_current", table_name="knowledge_documents")
    op.drop_index("ix_kb_doc_doc_type", table_name="knowledge_documents")
    op.drop_index("ix_kb_doc_law_code", table_name="knowledge_documents")

    op.drop_column("knowledge_documents", "is_current")
    op.drop_column("knowledge_documents", "article_range")
    op.drop_column("knowledge_documents", "issuing_body")
    op.drop_column("knowledge_documents", "repealed_date")
    op.drop_column("knowledge_documents", "effective_date")

    op.alter_column(
        "knowledge_documents",
        "version",
        existing_type=sa.String(32),
        existing_nullable=False,
        server_default="latest",
    )
    op.alter_column(
        "knowledge_documents",
        "doc_type",
        new_column_name="category",
        existing_type=sa.String(32),
        existing_nullable=False,
    )
    op.alter_column(
        "knowledge_documents",
        "law_code",
        new_column_name="game",
        existing_type=sa.String(64),
        existing_nullable=False,
        type_=sa.String(32),
    )

    op.create_index("ix_kb_doc_game", "knowledge_documents", ["game"])
    op.create_index("ix_kb_doc_category", "knowledge_documents", ["category"])
    op.create_index(
        "ix_kb_doc_game_category_version",
        "knowledge_documents",
        ["game", "category", "version"],
    )
