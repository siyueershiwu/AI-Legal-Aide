from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UpdatedAt, UUIDStrPK

if TYPE_CHECKING:
    from app.models.file import FileRecord
    from app.models.user import User


# 知识库支持的元数据枚举值（法律语境）
# law_code: 法律名称代码（用全称便于直接展示，无需额外映射）
LAW_CODE_VALUES = (
    "民法典",
    "刑法",
    "劳动法",
    "劳动合同法",
    "治安管理处罚法",
    "个人信息保护法",
    "网络安全法",
    "数据安全法",
    "宪法",
    "行政处罚法",
    "民事诉讼法",
    "刑事诉讼法",
    "公司法",
    "其他",
)

# doc_type: 文档在法律语料中的角色
# statute        - 法律正文条文
# interpretation - 司法解释 / 立法解释
# commentary     - 逐条释义 / 学理注解
# scenario       - 高频场景适用说明
# boundary       - 条款适用边界 / 例外情形
# diff           - 新旧法条修订对比
# repeal_note    - 废止 / 失效条款标注
# other          - 其它辅助资料
DOC_TYPE_VALUES = (
    "statute",
    "interpretation",
    "commentary",
    "scenario",
    "boundary",
    "diff",
    "repeal_note",
    "other",
)

SOURCE_TYPE_VALUES = ("upload", "url", "manual")


class KnowledgeDocument(Base):
    """法律知识库文档：一份入库的源文件对应一行。

    文件本身存 MinIO；本表只存元信息 + 切分计数。向量存 ChromaDB，
    按 (document_id, chunk_id) 反查正文走 KnowledgeChunk。

    版本隔离: is_current=True 视为现行版本，retriever 默认过滤；
    需要新旧对比时显式打开 include_repealed。
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index(
            "ix_kb_doc_law_type_version",
            "law_code", "doc_type", "version",
        ),
    )

    id: Mapped[UUIDStrPK]
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 法律名称代码（民法典 / 劳动法 / 刑法 ...）
    law_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 文档类型（statute / interpretation / ...）
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 版本：current / repealed-YYYY / 具体修正版本号（如 "2020-修正"）
    version: Mapped[str] = mapped_column(String(32), default="current", nullable=False)
    # 是否现行（默认 True；废止版本入库时显式置 False）
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    # 该版本生效日期
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 该版本废止日期（非 null 即过期版本，应与 is_current=False 配合）
    repealed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 发布机关（全国人大常委会 / 最高人民法院 ...）
    issuing_body: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 该 doc 覆盖的条款范围，如 "第1条-第50条" / "第三编 合同"
    article_range: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_type: Mapped[str] = mapped_column(String(16), default="upload", nullable=False)
    file_id: Mapped[str | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    file: Mapped["FileRecord | None"] = relationship()
    owner: Mapped["User | None"] = relationship()


class KnowledgeChunk(Base):
    """法律文本切片：向量存 ChromaDB，正文 + 元数据存本表。

    article_no: 该 chunk 所在主条款号（"第N条"标准化为阿拉伯数字字符串，如 "584"）。
    法条正文的 chunk 必填；释义/场景/对比类可选（用于关联回正文条号）。
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_kb_chunk_doc_index"),
    )

    id: Mapped[UUIDStrPK]
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 条款号（阿拉伯数字字符串，便于精准匹配；释义/场景可空）
    article_no: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    created_at: Mapped[CreatedAt]

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")
