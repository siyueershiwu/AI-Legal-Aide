"""
测试 fixtures
- 默认连本地 MySQL (复用用户的 .env)，跑 calculator/tool 纯单测时不需要 DB
- 跑集成测试时在 .env 里设 MYSQL_TEST_DATABASE，避免污染生产数据
"""
import os

# 不强制覆盖 DATABASE_URL - 走 .env
# 强制 test 模式
os.environ.setdefault("DEBUG", "True")
