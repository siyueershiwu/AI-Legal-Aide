# Chat AI — FastAPI + Vue 3 全栈项目

> 流式 AI 聊天，支持多轮对话、文件上传、会话管理、原生 Function Call 工具调用。

## ✨ 功能

- 🔐 JWT 鉴权 + 完整用户体系
- 💬 SSE 流式对话（豆包 Ark 3.0）
- 🛠 原生 Function Call（calculator / get_time / weather / translate / search）
- 📁 MinIO 对象存储（图片 / PDF / Word / Markdown）
- 🗂 会话管理（置顶 / 重命名 / 删除 / 清空）
- 👍 点赞 / 点踩
- 🌓 暗色 / 浅色主题
- 📱 响应式（移动端侧边栏）

## 🛠 技术栈

**后端**：FastAPI · SQLAlchemy 2.0 async · Alembic · aiomysql · Redis · MinIO · httpx · JWT
**前端**：Vue 3 · Pinia · Vite · TypeScript · Axios · marked · DOMPurify · highlight.js

## 📂 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # REST 路由（auth, chat, sessions, files, votes）
│   │   ├── core/           # config / security / deps / exceptions
│   │   ├── db/             # async engine / session / redis
│   │   ├── models/         # SQLAlchemy ORM
│   │   ├── repositories/   # 仓储层
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # 业务逻辑（doubao / tools / storage / redis_cache）
│   │   ├── middleware/     # 限流 + 日志
│   │   └── main.py
│   ├── migrations/         # Alembic 迁移
│   ├── tests/              # pytest
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── vue.what/
│   ├── src/
│   │   ├── api/            # axios + 业务 API
│   │   ├── stores/         # Pinia
│   │   ├── composables/    # useSSEChat / useMarkdown
│   │   ├── components/
│   │   ├── views/
│   │   ├── types/
│   │   └── main.ts
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.app.json
│   └── Dockerfile.prod
├── .github/workflows/      # GitHub Actions CI
├── docker-compose.yml      # 5 服务编排
├── .env.example.docker     # compose 用的环境变量模板
├── nginx.conf.template     # HTTPS 反代模板（可选）
└── .gitignore
```

## 🚀 快速启动（全 Docker Compose）

**前置条件**：本机已装 Docker（Docker Desktop / OrbStack / Linux 包装的都行）+ Git。

### 1. 克隆并配置环境变量

```bash
git clone https://github.com/<你的用户名>/<repo名>.git
cd <repo名>

# 复制 2 份 .env 模板
cp .env.example.docker          .env
cp backend/.env.example         backend/.env
```

### 2. 生成 4 个强随机值

```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
DB_PASS=$(python   -c "import secrets; print(secrets.token_urlsafe(24))")
REDIS_PASS=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
MINIO_USER="chat_minio_$(python -c "import secrets; print(secrets.token_urlsafe(8))")"
MINIO_PASS=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
```

### 3. 填入 `.env`（compose 用）

把 4 个值替换进 `.env`：

```bash
MYSQL_ROOT_PASSWORD=$DB_PASS
REDIS_PASSWORD=$REDIS_PASS
MINIO_ROOT_USER=$MINIO_USER
MINIO_ROOT_PASSWORD=$MINIO_PASS
```

### 4. 填入 `backend/.env`（应用用）

把对应值替换进 `backend/.env`：

```bash
SECRET_KEY=$SECRET_KEY
DATABASE_URL=mysql+aiomysql://root:${DB_PASS}@mysql:3306/chat_db
REDIS_URL=redis://:${REDIS_PASS}@redis:6379/0
REDIS_PASSWORD=$REDIS_PASS
MINIO_ACCESS_KEY=$MINIO_USER
MINIO_SECRET_KEY=$MINIO_PASS
DOUBAO_API_KEY=<从 https://www.volcengine.com/product/ark 申请>
```

### 5. 启动

```bash
docker compose up -d

# 第一次启动会自动跑 alembic upgrade head 建表
docker compose logs -f backend  # 跟一下日志确认 OK
```

### 6. 访问

| 服务 | 地址 | 备注 |
|------|------|------|
| 前端 | http://localhost:5173 | Vite dev server，带 HMR |
| 后端 API | http://localhost:8000 | FastAPI |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| MinIO 控制台 | http://localhost:9001 | 端口 9001 不暴露公网，仅本机 |
| 健康检查 | http://localhost:8000/health | 含 mysql / redis 状态 |

### 7. 改代码后

```bash
# 后端代码改了 → 重新 build + 重启
docker compose up -d --build backend

# 前端代码改了 → Vite HMR 自动刷新,不用重启
```

### 8. 停服 / 清理

```bash
docker compose down            # 停容器,数据卷保留
docker compose down -v         # 停容器 + 删数据卷(慎用,丢数据)
```

---

## 🔑 安全注意

1. **生产环境务必修改 `SECRET_KEY`**：
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
2. **不要把 `.env` 提交到 git**（已在 `.gitignore`，提交前用 `git status` 确认）
3. **修改 MySQL / Redis / MinIO 默认密码**（compose 默认是 `rootpass` / 空 / `minioadmin`，仅 dev 可用）
4. **生产环境开启 HTTPS**（见 `nginx.conf.template` + 下文"Nginx + HTTPS"）
5. CORS 已按白名单配置，不要再用 `*`

## 🚢 生产部署 Checklist

> 完成下面 7 步才能上生产。**任一项遗漏都是安全漏洞**。

1. ✅ 生成 4 个强随机值（每个至少 16 字符）
2. ✅ 填 `/.env` 和 `backend/.env`，**两边的密码必须互相一致**
3. ✅ `DEBUG=false`、`CORS_ORIGINS` 写明具体域名（不要带 `*`）
4. ✅ `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d -B`（生产模式）
5. ✅ 验证：未鉴权接口应该 401 → `curl -i http://your-domain.com/api/v1/sessions`
6. ✅ 验证：MinIO bucket 私有 → `docker exec chat-minio mc anonymous get local/chat-files` 应无输出
7. ✅ 配置 HTTPS（见下方）

## 🔒 Nginx + HTTPS 模板

> 模板在 `nginx.conf.template`。把 `${DOMAIN}` 换成真实域名，挂上 certbot 证书即可。

```bash
# 1. 渲染配置
cp nginx.conf.template nginx.conf
sed -i "s|\${DOMAIN}|your-domain.com|g" nginx.conf

# 2. 申请证书(仅一次)
certbot certonly --standalone -d your-domain.com

# 3. 取消 docker-compose.yml 里 nginx 服务的注释
# 4. 启动
docker compose up -d nginx
```

`nginx.conf` 已配置 SSE 友好参数（关闭 buffer + 300s 超时）。

## 🗃 数据库迁移

```bash
# 容器内自动跑(在 Dockerfile CMD 里): alembic upgrade head
# 手动:
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
docker compose exec backend alembic revision --autogenerate -m "描述"
```

## 🧪 API 示例

### 注册
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'
```

### 流式聊天
```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message":"你好，计算 2+3*4","session_id":null}'
```

## 🧪 本地测试

```bash
# 后端
cd backend
pip install -r requirements.txt
pytest -v

# 前端
cd vue.what
npm install
npm run type-check
npm run build
```

## 🛡 项目亮点

- ✅ **真鉴权**：所有需要 user 的接口走 `Depends(get_current_user)`，user_id 永远从 JWT 来
- ✅ **类型安全**：SQLAlchemy 2.0 ORM + Pydantic v2 schema，全链路类型校验
- ✅ **真异步**：async/await 贯穿，httpx async client，async Redis
- ✅ **真工具调用**：豆包 Ark 原生 `tools` / `tool_choice`，非 prompt 贴标签
- ✅ **XSS 防护**：marked → DOMPurify 双层，链接白名单协议
- ✅ **限流**：Redis INCR + EXPIRE 滑动窗口
- ✅ **私有存储**：MinIO bucket 启动时强制 `set_bucket_policy` 为 deny 匿名

## 🤝 CI

`.github/workflows/ci.yml` 在每次 push / PR 时跑：
- 后端 `pytest`
- 前端 `vue-tsc` + `npm run build`
- `docker compose config` 验证 YAML
- `docker compose build` 验证 Dockerfile

## 📜 License

MIT
