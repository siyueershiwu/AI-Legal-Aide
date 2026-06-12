"""Embedder: sentence-transformers 懒加载单例。

- 模型首次使用时从 HuggingFace 下载到 EMBEDDING_CACHE_DIR（~100MB）
- normalize_embeddings=True: 余弦相似度等价内积
- embed_query / embed_documents 都走 to_thread，避免阻塞事件循环
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class Embedder:
    """bge-small-zh-v1.5 嵌入器（512 维，中文检索 SOTA 轻量模型）。"""

    def __init__(self) -> None:
        self._model: "SentenceTransformer | None" = None
        self._lock = asyncio.Lock()

    def _load_sync(self) -> "SentenceTransformer":
        """同步加载。sentence-transformers 内部已是线程安全，懒一次即可。"""
        if self._model is not None:
            return self._model
        from sentence_transformers import SentenceTransformer

        logger.info(
            "Loading embedding model %s on %s ...",
            settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE,
        )
        self._model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
            cache_folder=settings.EMBEDDING_CACHE_DIR,
        )
        logger.info("Embedding model loaded (dim=%d)", settings.EMBEDDING_DIM)
        return self._model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入。CPU 阻塞，丢到默认 executor。"""
        if not texts:
            return []
        # 懒加载串行化（避免并发下载/初始化）
        async with self._lock:
            model = await asyncio.to_thread(self._load_sync)
        vecs = await asyncio.to_thread(
            model.encode,
            texts,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.tolist()

    async def embed_query(self, text: str) -> list[float]:
        vecs = await self.embed_documents([text])
        return vecs[0]


embedder = Embedder()
