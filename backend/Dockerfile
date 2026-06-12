# 多阶段构建 - 减小镜像体积 + 提升安全性
FROM python:3.12-slim AS builder
WORKDIR /app

# 仅装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# 预热 embedding 模型到镜像里（~100MB）。失败也不阻塞 build——运行时再下。
# 这样 prod 启动时不需要联网下载模型，离线部署也能跑。
FROM python:3.12-slim AS prewarmer
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels && \
    mkdir -p /app/models && \
    python -c "from sentence_transformers import SentenceTransformer; \
      SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='/app/models')" \
      || echo "[prewarmer] model download failed, will retry at runtime"


FROM python:3.12-slim AS runtime

# 健康检查依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 非 root 用户
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

# 复制预热好的模型（prewarmer 阶段下载的）到 runtime
COPY --from=prewarmer --chown=app:app /app/models /app/models

# 复制应用代码
COPY --chown=app:app app ./app
COPY --chown=app:app alembic.ini ./alembic.ini
COPY --chown=app:app migrations ./migrations

# RAG 持久化目录（chroma）—— 挂卷
RUN mkdir -p /app/data/chroma && chown -R app:app /app/data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# 启动前自动跑迁移
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers 2"]
