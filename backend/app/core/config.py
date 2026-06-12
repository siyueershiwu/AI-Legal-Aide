"""
应用配置 - 单一 Settings 类，全部从环境变量加载。
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ===== App =====
    APP_NAME: str = "Chat API"
    DEBUG: bool = False

    # CORS: 逗号分隔字符串或 list
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    # ===== Security =====
    SECRET_KEY: str = "insecure-default-please-override"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    SESSION_EXPIRE_SECONDS: int = 3600 * 24 * 7

    # ===== Database =====
    DATABASE_URL: str = "mysql+aiomysql://root:password@localhost:3306/chat_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # ===== Redis =====
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str | None = None

    # ===== MinIO =====
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "chat-files"
    MINIO_SECURE: bool = False
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

    # ===== Doubao / Volcengine Ark =====
    DOUBAO_API_KEY: str = ""
    DOUBAO_MODEL: str = "doubao-seed-2-0-pro-260215"
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"

    # ===== Rate limit =====
    RATE_LIMIT_MAX_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ===== Third-party API =====
    # Tavily Search (https://tavily.com)
    TAVILY_API_KEY: str = ""
    # 百度翻译 (https://api.fanyi.baidu.com)
    BAIDU_APPID: str = ""
    BAIDU_SECRET: str = ""

    # ===== RAG / Vector Store =====
    # ChromaDB 持久化目录（gitignored）
    VECTOR_DB_PATH: str = "./data/chroma"
    # 嵌入模型（HuggingFace model id，首次启动自动下载）
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_DIM: int = 512
    EMBEDDING_DEVICE: str = "cpu"  # cpu / cuda
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_CACHE_DIR: str = "./models"  # HF 缓存（gitignored）
    # 文本切分
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    # 检索
    RETRIEVAL_TOP_K: int = 5
    # 余弦距离阈值（= 1 - 相似度，越低越相似）。
    # 口语 query 经改写后 top-k 距离通常落在 0.35-0.50；0.45 能在放行
    # 多场景边缘 case 的同时把无关 query（top 距离 0.5+）拦在 top-k 之外。
    RETRIEVAL_SCORE_THRESHOLD: float = 0.45

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_csv(cls, v):
        """支持 CORS_ORIGINS=http://a,http://b 的字符串写法"""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
