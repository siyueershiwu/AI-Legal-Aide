"""测试 RAG embedder：mock sentence_transformers 避免真下载/真跑模型。

要点:
- 懒加载：首次 embed 触发加载
- normalize_embeddings=True：验证传给 encode 的参数
- 批量：单 batch 多句
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core.config import settings
from app.services.rag.embedder import Embedder


@pytest.fixture
def fake_model() -> Any:
    """返回固定 512 维向量的假模型。"""
    model = MagicMock()
    dim = settings.EMBEDDING_DIM

    def fake_encode(texts, **_kwargs):
        # 给每个文本返回不同的"伪"向量（用 hash 让不同文本的向量不同）
        vecs = []
        for t in texts:
            seed = abs(hash(t)) % (2**31)
            rng = np.random.default_rng(seed)
            v = rng.random(dim).astype(np.float32)
            v /= np.linalg.norm(v)  # 单位向量 → 模拟 normalize
            vecs.append(v)
        return np.stack(vecs)

    model.encode = fake_encode
    return model


@pytest.fixture
def embedder_with_mock(fake_model: Any) -> Embedder:
    """patch sentence_transformers.SentenceTransformer，避免真加载。"""
    e = Embedder()
    with patch(
        "sentence_transformers.SentenceTransformer",
        return_value=fake_model,
    ) as cls:
        e._model = None
        # 把 fake_model 预置好
        e._model = fake_model
    return e


class TestEmbedder:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, embedder_with_mock: Embedder) -> None:
        result = await embedder_with_mock.embed_documents([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_query_returns_single_vector(self, embedder_with_mock: Embedder) -> None:
        v = await embedder_with_mock.embed_query("原神钟离")
        assert isinstance(v, list)
        assert len(v) == settings.EMBEDDING_DIM
        assert all(isinstance(x, float) for x in v)

    @pytest.mark.asyncio
    async def test_embed_documents_returns_list_of_vectors(self, embedder_with_mock: Embedder) -> None:
        texts = ["原神钟离", "星穹铁道", "崩坏3"]
        vecs = await embedder_with_mock.embed_documents(texts)
        assert len(vecs) == 3
        for v in vecs:
            assert len(v) == settings.EMBEDDING_DIM
        # 不同文本应得不同向量（hash 种子不同）
        assert vecs[0] != vecs[1]

    @pytest.mark.asyncio
    async def test_same_text_returns_same_vector(self, embedder_with_mock: Embedder) -> None:
        v1 = await embedder_with_mock.embed_query("原神钟离")
        v2 = await embedder_with_mock.embed_query("原神钟离")
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_passes_normalize_to_encode(self, fake_model: Any) -> None:
        """验证 encode 被以 normalize_embeddings=True 调用（这是 cosine 等价内积的关键）。"""
        captured: dict = {}
        def capturing_encode(texts, **kwargs):
            captured.update(kwargs)
            captured["texts"] = texts
            return np.zeros((len(texts), settings.EMBEDDING_DIM), dtype=np.float32)
        fake_model.encode = capturing_encode

        e = Embedder()
        e._model = fake_model
        await e.embed_documents(["test"])
        assert captured.get("normalize_embeddings") is True
        assert captured.get("show_progress_bar") is False
        assert captured.get("batch_size") == settings.EMBEDDING_BATCH_SIZE

    @pytest.mark.asyncio
    async def test_lazy_loads_on_first_call(self) -> None:
        """首次调用前 _model 为 None；调用后非 None。"""
        e = Embedder()
        # 强制让 _model 为 None（fixture 之外）
        e._model = None
        assert e._model is None

        fake = MagicMock()
        def fake_encode(texts, **_):
            return np.zeros((len(texts), 512), dtype=np.float32)
        fake.encode = fake_encode

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=fake,
        ):
            await e.embed_query("hi")

        assert e._model is fake
