"""
测试 fixtures
- 本地: 默认连用户的 MySQL (走 .env)，需要 .env 中 DATABASE_URL 可达
- CI:  显式设 sqlite+aiosqlite:///:memory:，零依赖、可重入、并行安全
- 集成测试想跑真 MySQL：在 CI 把 DATABASE_URL 注入为指向 test schema 的 MySQL
  DSN，并在 conftest 用 mysql+aiomysql://... 而不是 sqlite
"""
import os

# CI 默认走 in-memory sqlite（与 .github/workflows/ci.yml 的 Run tests env 一致）
# 本地有 .env 时不会覆盖；CI 没 .env 时给一个安全的 fallback，避免 import 期
# Settings() 拿到 mysql+aiomysql://root:password@localhost... 这种根本连不上的 DSN
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-86-characters-long-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
os.environ.setdefault("DOUBAO_API_KEY", "test-key")
os.environ.setdefault("DEBUG", "True")
