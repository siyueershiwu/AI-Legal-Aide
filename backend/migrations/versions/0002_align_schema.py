"""align schema to current ORM (rename time columns)

Revision ID: 0002_align_schema
Revises: 0001_initial
Create Date: 2026-06-04

用裸 SQL 改列名，绕开 alembic 的类型跟踪（避免需要原列类型）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_align_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    res = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table, "c": column},
    ).scalar()
    return bool(res)


def _rename_if_needed(table: str, old: str, new: str, new_type: str = "DATETIME") -> None:
    if _has_column(table, old) and not _has_column(table, new):
        op.execute(
            f"ALTER TABLE `{table}` CHANGE `{old}` `{new}` {new_type} "
            f"NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )


def upgrade() -> None:
    _rename_if_needed("users", "create_time", "created_at")
    _rename_if_needed("users", "update_time", "updated_at")
    op.execute(
        "ALTER TABLE `users` MODIFY `updated_at` DATETIME "
        "NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )

    _rename_if_needed("sessions", "create_time", "created_at")
    _rename_if_needed("sessions", "update_time", "updated_at")
    op.execute(
        "ALTER TABLE `sessions` MODIFY `updated_at` DATETIME "
        "NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )

    _rename_if_needed("chat_history", "create_time", "created_at")
    _rename_if_needed("files", "create_time", "created_at")


def downgrade() -> None:
    _rename_if_needed("users", "created_at", "create_time")
    _rename_if_needed("users", "updated_at", "update_time")
    _rename_if_needed("sessions", "created_at", "create_time")
    _rename_if_needed("sessions", "updated_at", "update_time")
    _rename_if_needed("chat_history", "created_at", "create_time")
    _rename_if_needed("files", "created_at", "create_time")
