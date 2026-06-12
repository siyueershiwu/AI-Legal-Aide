"""VectorStore: ChromaDB PersistentClient 封装（法律知识库）。

- 启动时创建 ./data/chroma 目录 + law_kb collection
- metadata: {document_id, chunk_id, law_code, doc_type, version, is_current, article_no, title}
- 距离度量: cosine (hnsw:space=cosine)
- distance 越小越相似（0=相同, 2=正交）

启动时若检测到旧版 mihoyo_kb collection 会自动删除，避免与新 schema 错位。
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.core.config import settings

# 关 ChromaDB 上报（避免 posthog 7.x 跟 chromadb 0.5.x API 不兼容的噪音日志）
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "law_kb"
_LEGACY_COLLECTION_NAME = "mihoyo_kb"


class VectorStore:
    """单 collection (law_kb) 持久化。"""

    def __init__(self) -> None:
        self._client = None
        self._col = None
        self._lock = asyncio.Lock()

    def _ensure(self):
        if self._col is not None:
            return
        import chromadb

        os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
        self._client = chromadb.PersistentClient(path=settings.VECTOR_DB_PATH)
        # 一次性清理旧 collection（迁移前 mihoyo_kb 残留）
        try:
            existing = {c.name for c in self._client.list_collections()}
            if _LEGACY_COLLECTION_NAME in existing:
                self._client.delete_collection(_LEGACY_COLLECTION_NAME)
                logger.info("Removed legacy collection: %s", _LEGACY_COLLECTION_NAME)
        except Exception as e:
            logger.warning("Legacy collection cleanup skipped: %s", e)

        self._col = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection ready: %s", self._col.name)

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """同步 add。CPU 操作，调用方应包 to_thread。"""
        self._ensure()
        # chromadb 单次 add 限制 41666 条，理论单文档超不过，安全
        self._col.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    async def add_async(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(self.add, ids, embeddings, documents, metadatas)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """同步 query。返回 [{id, document, metadata, distance}, ...]"""
        self._ensure()
        res = self._col.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        out: list[dict[str, Any]] = []
        # ChromaDB 返回 batch 形式，外面包了一层 [0]
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i, d, m, dist in zip(ids, docs, metas, dists):
            out.append({
                "id": i,
                "document": d,
                "metadata": m or {},
                "distance": float(dist),
            })
        return out

    async def query_async(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.query, query_embedding, top_k, where)

    def delete_by_document(self, document_id: str) -> int:
        """删除某文档对应的所有向量。返回删除条数。"""
        self._ensure()
        existing = self._col.get(where={"document_id": document_id})
        ids = existing.get("ids") or []
        if not ids:
            return 0
        self._col.delete(ids=ids)
        return len(ids)

    async def delete_by_document_async(self, document_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_document, document_id)

    def count(self, where: dict[str, Any] | None = None) -> int:
        self._ensure()
        return self._col.count(where=where)

    def reset(self) -> None:
        """清空 collection（保留 client/目录）。用于 rebuild。"""
        self._ensure()
        # ChromaDB 没有直接 empty collection；删 + 重建最稳
        name = self._col.name
        self._client.delete_collection(name)
        self._col = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector collection reset: %s", name)

    async def reset_async(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self.reset)


vector_store = VectorStore()
