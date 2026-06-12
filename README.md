# What's That? · AI 法律助手

> **An AI-driven multimodal Q&A chat built with FastAPI + Vue 3, powered by 豆包 Doubao.**
> Upload an image or document, ask anything, and stream replies with function-calling tools (calculator / weather / translate / web search / RAG knowledge base) and SSE streaming.

![MIT License](https://img.shields.io/badge/license-MIT-green)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Node 20](https://img.shields.io/badge/node-20-green)
![Powered by Open-Meteo](https://img.shields.io/badge/weather-Open--Meteo-orange)
![Powered by 豆包 Ark](https://img.shields.io/badge/AI-豆包-blueviolet)
![RAG · bge-small-zh](https://img.shields.io/badge/RAG-bge--small--zh-9cf)

[English](#english) · [中文](#中文)

---

<a id="english"></a>

## English

### What is this?

A self-hosted AI chat backend + frontend where users upload images or documents
and chat with an LLM (豆包 Doubao via 火山引擎 Ark) that can call five tools in
a ReAct-style loop:

- **calculator** — safe expression evaluator (replaces `eval`)
- **get_time** — current server time
- **weather** — real-time weather via [Open-Meteo](https://open-meteo.com/) (no key, no signup)
- **translate** — Baidu Translate
- **search** — Tavily Search
- **kb_search** — RAG retrieval over an admin-managed **Chinese legal knowledge base**
  (民法典 / 刑法 / 劳动法 / 劳动合同法 / 治安管理处罚法 / 个人信息保护法 /
  网络安全法 / 数据安全法 / 宪法 / etc.; ChromaDB + local
  `bge-small-zh-v1.5` embeddings; no API key)

Replies are streamed over Server-Sent Events. Sessions, messages, files, and
votes are persisted in MySQL with SQLAlchemy 2 async + aiomysql. Files live in
MinIO (S3-compatible). Redis is used for rate limiting (soft dependency —
degrades gracefully if down).

### Highlights

- **Multimodal uploads** — images (vision content array) and documents
  (PDF / docx / txt / md / csv parsed into text parts)
- **Server-Sent Events** streaming for AI replies
- **Function calling** loop with 6 tools, all routed through a registry
- **RAG legal knowledge base** — vector search over an admin-curated
  Chinese law corpus (民法典 / 刑法 / 劳动法 / 劳动合同法 / 治安管理处罚法 /
  个人信息保护法 / 网络安全法 / 数据安全法 / 宪法 / 行政处罚法 /
  民事诉讼法 / 刑事诉讼法 / 公司法) with article-level citations and
  hard anti-hallucination guards
- **JWT auth** with bcrypt-hashed passwords
- **Rate limit middleware** (pure ASGI, no `BaseHTTPMiddleware` — see [SECURITY.md](SECURITY.md))
- **100 pytest** cases passing, including mocked async HTTP

### Tech Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI · SQLAlchemy 2 async · aiomysql · Alembic |
| Frontend | Vue 3 · TypeScript · Vite · Pinia |
| AI | 豆包 Doubao (火山引擎 Ark) — vision + tool calling |
| RAG | ChromaDB · sentence-transformers · `BAAI/bge-small-zh-v1.5` (local, CPU) |
| Storage | MySQL 8 · Redis 7 · MinIO |
| Weather | Open-Meteo (zero-key) |
| Infra | Docker Compose · GitHub Actions CI |

### Quick Start

**Prerequisites**: Python 3.12+ · Node.js 20+ · Docker · MySQL 8 (local install)

```bash
# 1. Clone
git clone <repo-url> && cd what

# 2. Configure secrets
cp .env.example .env                  # Redis/MinIO passwords
cp backend/.env.example backend/.env  # MySQL / JWT / 豆包 / Tavily / Baidu

# 3. Start infrastructure
docker compose up -d                  # Redis + MinIO

# 4. Backend
cd backend
python -m venv .venv && .venv\Scripts\activate   # or source .venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload

# 5. Frontend (in a new terminal)
cd frontend
npm install
npm run dev
```

- API docs: http://localhost:8000/docs
- Web app:  http://localhost:5173

### Production

```bash
docker compose -f docker-compose.prod.yml up -d --build   # http://localhost
```

> MySQL must be running on the host (containers reach it via `host.docker.internal`).

### Run Tests

```bash
cd backend && pytest -v
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/healthz` | health check (MySQL + Redis) |
| POST | `/api/v1/auth/register` | register |
| POST | `/api/v1/auth/login` | login (returns JWT) |
| GET | `/api/v1/auth/me` | current user |
| POST | `/api/v1/auth/logout` | logout |
| POST | `/api/v1/chat/stream` | SSE streaming chat |
| POST | `/api/v1/chat/stop/{session_id}` | stop generation |
| GET | `/api/v1/knowledge/meta` | KB enums (law_code / doc_type) |
| POST | `/api/v1/knowledge/documents` | ingest a document into the KB |
| GET | `/api/v1/knowledge/documents` | list KB documents (filter by `law_code` / `doc_type` / `is_current`) |
| DELETE | `/api/v1/knowledge/documents/{id}` | delete a KB document |
| POST | `/api/v1/knowledge/documents/batch-delete` | batch delete |
| POST | `/api/v1/knowledge/rebuild` | clear & re-ingest the entire KB |
| GET | `/api/v1/knowledge/stats` | KB statistics (totals + by_law_code/by_doc_type + current/repealed counts) |
| GET | `/api/v1/knowledge/preview-search` | admin-only retrieval preview |
| GET | `/api/v1/sessions` | list sessions |
| GET | `/api/v1/sessions/{id}` | session detail |
| DELETE | `/api/v1/sessions/{id}` | delete session |
| DELETE | `/api/v1/sessions/{id}/messages` | clear messages |
| POST | `/api/v1/sessions/{id}/pin` | toggle pin |
| PUT | `/api/v1/sessions/{id}/title` | rename |
| POST | `/api/v1/files/upload` | upload file (multipart) |
| GET | `/api/v1/files` | list files |
| GET | `/api/v1/files/{id}` | file metadata |
| GET | `/api/v1/files/{id}/url` | presigned download URL |
| GET | `/api/v1/files/{id}/parse` | parsed text content |
| DELETE | `/api/v1/files/{id}` | delete file |
| POST | `/api/v1/messages/{chat_id}/vote` | like/dislike a message |
| GET | `/api/v1/history/search` | search message history |

### RAG Legal Knowledge Base

A retrieval-augmented generation (RAG) KB over **Chinese public law** lives
behind the `kb_search` tool. Any question that smells like a legal issue —
`老板拖欠工资能告吗` / `打人会判几年` / `民法典关于借款合同的规定` — triggers
a vector search over admin-ingested statutes, and the model is **forced**
to answer strictly from those retrieved snippets (no hallucinated article
numbers, no 预训练 knowledge override).

**Supported law corpus (13 种子, 1 部已内置 demo)**:

| 法律 | 状态 | 适用 |
|------|------|------|
| 民法典 | ✅ 内置 1 部 | 民事基础 |
| 刑法 / 劳动法 / 劳动合同法 / 治安管理处罚法 / 个人信息保护法 / 网络安全法 / 数据安全法 / 宪法 / 行政处罚法 / 民事诉讼法 / 刑事诉讼法 / 公司法 | 🔧 需手动补 ID | 见下方入库文档 |

**Stack**:
- Vector store: [ChromaDB](https://www.trychroma.com/) (file-based, single directory)
- Embedding: [`BAAI/bge-small-zh-v1.5`](https://huggingface.co/BAAI/bge-small-zh-v1.5)
  via `sentence-transformers` (CPU, 512-dim, ~100MB)
- Chunking (`statute` doc_type): split by `第N条` with 编/章/节 hierarchy prefix
  → re-join by 款 / 段落
- Chunking (other doc_types): generic paragraph → sentence → hard-cut (3-level fallback)
- Dedup: SHA-256 content hash
- Version isolation: ChromaDB metadata filter (`law_code`, `doc_type`, `version`, `is_current`)
- Article-level citations: every chunk carries `article_no` for exact-article lookup

**Three-layer retrieval**:
1. **Exact article match** — if the user query contains `第N条`, hit the
   relational DB directly (`chunks_by_article`)
2. **Vector recall** — bge embedding, filter `is_current=true` by default
3. **Related statute fetch** — fall back to sibling laws if step 2 returns nothing

**Hard rules enforced via system prompt + tool flow**:
1. Every legal question **must** call `kb_search` first.
2. The model may **only** use retrieved snippets; no 凭记忆 generating
   article numbers / 司法解释 / 案例编号.
3. If retrieval returns no hits, the tool emits a hard-block string and the
   model must admit the miss; pre-trained knowledge cannot be used to fill the gap.
4. Every answer carries `[1][2]…` references; the frontend renders a
   collapsible sources block under the message.
5. Hits on `is_current=false` documents are explicitly flagged as `已废止`
   in the source citation; old vs new versions are never mixed.

**KB management UI**: log in → sidebar → 📚 知识库. Admins can upload
TXT/MD/PDF/docx files, list/filter documents (by law / type / current status),
batch delete, preview retrieval quality, or wipe-and-rebuild the entire KB.

**Offline / first-run setup**: the model is auto-downloaded from
HuggingFace on first embedder call. To pre-warm before going offline:

```bash
# From the backend directory
python -c "from sentence_transformers import SentenceTransformer; \
  SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='./models')"
```

> **Note:** model weights are not committed to git. `models/` and
> `data/chroma/` are both `.gitignore`d. The prod Dockerfile pre-warms
> the model at build time, so the runtime image is self-contained.

### 法律知识库数据 — 入库指南

知识库是空的克隆后只能聊天不能查法律条文。要灌入数据，有两种方式：

**方式 A：`from-api` 自动从国家法律法规数据库抓取**（推荐）

`backend/scripts/fetch_npc_laws.py` 内置了 13 部高频法律的种子元数据
（`law_code / title / version / effective_date / issuing_body`）和每部
法律的 flk ID。脚本走两步：
1. 调 `https://flk.npc.gov.cn/law-search/download/pc?format=docx&bbbs=<id>`
   拿到带签名的 OBS 链接（华为云 OBS，1 小时有效）
2. GET 签名 URL 拉 .docx 字节流
3. `python-docx` 解析为 markdown
4. 走项目既有的 `ingest_file` 链路按「第N条」切分 + ChromaDB 写入

```bash
cd backend

# 1) 看种子清单
python -X utf8 -m scripts.fetch_npc_laws list-seed

# 2) 先测 1 部（最快 30-60s / 部）
python -X utf8 -m scripts.fetch_npc_laws from-api --only 民法典

# 3) 跑全量
python -X utf8 -m scripts.fetch_npc_laws from-api
```

跑完 `/api/v1/knowledge/stats` 应当 `total_documents: 13`。

> **注意**：`SEED_LAWS` 里 12 部法律的 `id` 字段**目前是空的**（只有民法典填了）。
> 克隆者需要去 [flk.npc.gov.cn](https://flk.npc.gov.cn/) 详情页 URL
> 里复制 `?id=` 后那段 UUID 填到 `SEED_LAWS` 字典里。这是**一次性**工作，
> 填完后 commit 一次就永久可用。

**方式 B：`from-files` 手动复制 markdown**（不依赖 flk 接口）

适用：flk 接口抽风、想收录司法解释/释义类辅助资料（`doc_type ∈ {interpretation, commentary, scenario, boundary, diff, repeal_note}`）。

```bash
# 1) 准备 markdown 文件，文件名按 _slugify_law_code() 短码
#    民法典 → mfd.md, 刑法 → xf.md, 劳动法 → ldf.md, ...
#    完整短码表见脚本 _slugify_law_code() 注释
mkdir -p data/npc_laws
# 浏览器从 flk / 其它来源复制文本后保存为 data/npc_laws/mfd.md 等
python -X utf8 -m scripts.fetch_npc_laws list-seed   # 找短码

# 2) 跑入库
python -X utf8 -m scripts.fetch_npc_laws from-files
```

**缓存与重跑**：

抓到的 markdown / docx 落到 `data/npc_laws/cache/<slug>.md`，下次
跑自动复用，避免重复下载；要强制重抓用 `--no-cache`。

**QPS 限速**：默认 0.5 req/s（每 2 秒一个请求），是 flk 公共接口的
经验安全值；调快 `--rate 1.0` / 调慢 `--rate 0.2`。

### Project Layout

```
what/
├── backend/                # FastAPI
│   ├── app/
│   │   ├── api/v1/         # routes
│   │   ├── core/           # config / security / DI
│   │   ├── db/             # MySQL & Redis sessions
│   │   ├── models/         # SQLAlchemy models
│   │   ├── repositories/   # data access
│   │   ├── schemas/        # Pydantic
│   │   ├── services/       # AI / storage / cache / tools
│   │   │   └── rag/        # ChromaDB + bge-small-zh pipeline
│   │   └── main.py
│   ├── migrations/         # Alembic
│   └── tests/              # 106 pytest cases
├── frontend/               # Vue 3
│   └── src/
│       ├── api/            # axios client
│       ├── components/
│       │   └── knowledge/  # DocumentUploader / DocumentList / StatsOverview
│       ├── composables/    # useSSEChat …
│       ├── layouts/        # DefaultLayout (sidebar nav)
│       ├── stores/         # Pinia
│       └── views/          # ChatRoom / Knowledge
├── docker-compose.yml      # dev: Redis + MinIO
├── docker-compose.prod.yml # prod: full stack + kb_data volume
├── nginx.conf.template
├── .github/workflows/      # CI
├── LICENSE                 # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── SECURITY.md
```

### License

MIT — see [LICENSE](LICENSE).

### Acknowledgments

[Open-Meteo](https://open-meteo.com/) · [WMO Weather codes](https://open-meteo.com/en/docs) ·
[DOMPurify](https://github.com/cure53/DOMPurify) · [marked](https://github.com/markedjs/marked) ·
[highlight.js](https://highlightjs.org/) · [Pinia](https://pinia.vuejs.org/) · [FastAPI](https://fastapi.tiangolo.com/)

---

<a id="中文"></a>

## 中文

### 这是什么？

一个自托管的多模态 AI 对话全栈项目（FastAPI + Vue 3 + 豆包 Doubao）。支持：

- **上传图片** —— AI 视觉理解
- **上传文档**（pdf / docx / txt / md / csv）—— 抽取文本给 AI 阅读
- **5 工具调用**（ReAct 风格循环）：
  - `calculator` — 安全数学运算（取代 `eval`）
  - `get_time` — 当前时间
  - `weather` — 实时天气，**零密钥**（[Open-Meteo](https://open-meteo.com/)，免注册）
  - `translate` — 百度翻译
  - `search` — Tavily 搜索
- **SSE 流式回复**
- **会话管理**（建/查/删/置顶/重命名）
- **消息点赞点踩 + 历史搜索**
- **JWT 用户认证**

### 核心特性

- 多模态上传：图片走豆包 Vision content 数组，文档先解析再注入
- SSE 流式 AI 回复，首帧带 `session_id`（修复同会话多 session 漏同步）
- 工具调用循环，注册中心模式（共 6 个工具：calculator / get_time / weather / translate / search / **kb_search**）
- **中国法律 RAG 知识库**：向量检索增强生成，admin 上传法条 → 按「第N条」切分+向量化+入库；模型回答强制基于检索结果，可溯源、零幻觉、对废止法条显式标注
- 限流中间件（纯 ASGI，避开 `BaseHTTPMiddleware` 的 `ExceptionGroup` 坑）
- 106 个 pytest 用例全过（含 mock 异步 HTTP）

### 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI · SQLAlchemy 2 async · aiomysql · Alembic |
| 前端 | Vue 3 · TypeScript · Vite · Pinia |
| AI | 豆包 Doubao（[火山引擎 Ark](https://www.volcengine.com/product/ark)）|
| RAG | ChromaDB · sentence-transformers · `BAAI/bge-small-zh-v1.5`（本地 CPU）|
| 存储 | MySQL 8 · Redis 7 · MinIO |
| 天气 | Open-Meteo（零密钥） |
| 工程 | Docker Compose · GitHub Actions CI |

### 快速开始

**前置条件**：Python 3.12+ · Node.js 20+ · Docker Desktop · MySQL 8（本地安装）

```bash
# 1. 克隆
git clone <repo-url> && cd what

# 2. 复制环境变量模板
cp .env.example .env                  # Redis / MinIO 密码
cp backend/.env.example backend/.env  # MySQL / JWT / 豆包 / Tavily / 百度

# 3. 启动基础设施
docker compose up -d                  # Redis + MinIO

# 4. 启动后端
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows | source .venv/bin/activate 是 *nix
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload

# 5. 启动前端（新开终端）
cd frontend
npm install
npm run dev
```

- API 文档：http://localhost:8000/docs
- Web 应用：http://localhost:5173

### 生产部署

```bash
docker compose -f docker-compose.prod.yml up -d --build   # 访问 http://localhost
```

> MySQL 必须在宿主机上跑（容器通过 `host.docker.internal` 访问）。

### 测试

```bash
cd backend && pytest -v
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/healthz` | 健康检查（MySQL + Redis） |
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录（返回 JWT） |
| GET | `/api/v1/auth/me` | 当前用户 |
| POST | `/api/v1/auth/logout` | 登出 |
| POST | `/api/v1/chat/stream` | SSE 流式聊天 |
| POST | `/api/v1/chat/stop/{session_id}` | 停止生成 |
| GET | `/api/v1/knowledge/meta` | KB 枚举（law_code / doc_type） |
| POST | `/api/v1/knowledge/documents` | 入库一个新文档 |
| GET | `/api/v1/knowledge/documents` | 列出 KB 文档（按 law_code / doc_type 过滤） |
| DELETE | `/api/v1/knowledge/documents/{id}` | 删除 KB 文档 |
| POST | `/api/v1/knowledge/documents/batch-delete` | 批量删除 |
| POST | `/api/v1/knowledge/rebuild` | 清空 + 重新入库 |
| GET | `/api/v1/knowledge/stats` | KB 统计（总量 + 按 law_code / doc_type） |
| GET | `/api/v1/knowledge/preview-search` | admin 检索预览 |
| GET | `/api/v1/sessions` | 会话列表 |
| GET | `/api/v1/sessions/{id}` | 会话详情 |
| DELETE | `/api/v1/sessions/{id}` | 删除会话 |
| DELETE | `/api/v1/sessions/{id}/messages` | 清空消息 |
| POST | `/api/v1/sessions/{id}/pin` | 切换置顶 |
| PUT | `/api/v1/sessions/{id}/title` | 重命名 |
| POST | `/api/v1/files/upload` | 上传文件（multipart） |
| GET | `/api/v1/files` | 文件列表 |
| GET | `/api/v1/files/{id}` | 文件元信息 |
| GET | `/api/v1/files/{id}/url` | 预签名下载 URL |
| GET | `/api/v1/files/{id}/parse` | 解析后的文本 |
| DELETE | `/api/v1/files/{id}` | 删除文件 |
| POST | `/api/v1/messages/{chat_id}/vote` | 消息点赞/点踩 |
| GET | `/api/v1/history/search` | 历史消息搜索 |

### 常见问题

- **MySQL 拒绝连接**：检查 `backend/.env` 里的 `DATABASE_URL` 用户名/密码；MySQL 8 默认使用 `caching_sha2_password`，aiomysql 需要服务端的 `sha256_password` 或 `mysql_native_password` 兼容（一般 OK）。
- **MinIO 桶没建**：启动后访问 http://localhost:9001 用 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 登录，手动建桶 `chat-files`，或在 backend 启动后调用内部初始化。
- **豆包 401**：`backend/.env` 里 `DOUBAO_API_KEY` 错；火山引擎控制台「在线推理」创建接入点，把 **接入点 URL 末尾的模型 ID** 填到 `DOUBAO_MODEL`。
- **CORS 报错**：开发时 `CORS_ORIGINS` 必须是前端实际地址（含端口），不能省略端口。
- **SSE 中断**：浏览器 DevTools Network 过滤 `text/event-stream`；nginx 反代时记得 `proxy_buffering off` 和 `proxy_read_timeout` 调大。
- **首次启动慢**：`kb_search` 工具首次调用时会从 HuggingFace 下载 `BAAI/bge-small-zh-v1.5`（~100MB）；离线环境先在 `backend/` 下执行：
  ```bash
  python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='./models')"
  ```
  生产环境 Dockerfile 已经在 build 阶段预热，runtime 不需再下。

### RAG 法律知识库

内置一个**中国法律条文**的检索增强生成（RAG）知识库，对应工具 `kb_search`。
用户问到法律相关问题（`老板拖欠工资能告吗` / `打人会判几年` / `民法典关于借款合同的规定`）
时，模型会**强制**先检索知识库，再基于检索到的素材作答，**禁止**直接用预训练
知识凭空编法条号 / 司法解释 / 案例编号，保证**零幻觉 + 可溯源 + 版本隔离**。

**已收录法律**（13 部）：民法典（demo 已内置）/ 刑法 / 劳动法 / 劳动合同法 /
治安管理处罚法 / 个人信息保护法 / 网络安全法 / 数据安全法 / 宪法 /
行政处罚法 / 民事诉讼法 / 刑事诉讼法 / 公司法。

**技术栈**：
- 向量库：[ChromaDB](https://www.trychroma.com/)（单目录持久化，零外部服务）
- 嵌入模型：[`BAAI/bge-small-zh-v1.5`](https://huggingface.co/BAAI/bge-small-zh-v1.5)，
  通过 `sentence-transformers`（CPU，512 维，约 100MB）
- 切分：`doc_type=statute` 走 `law_chunker`（按「第N条」+ 编/章/节 层级前缀），
  其它 doc_type 走通用段落 → 句号 → 硬切（三级回退，保留自然边界）
- 去重：基于 SHA-256 内容哈希
- 版本隔离：ChromaDB metadata 过滤（`law_code` / `doc_type` / `version` / `is_current`）

**三段式检索**（retriever.py）：
1. **精确条号命中**：若用户问题带「第N条」，走关系库 `chunks_by_article()` 直接拉
2. **向量召回**：`is_current=true` 过滤，bge-small-zh 编码 + top-k 余弦
3. **相关法条拉取**：步骤 2 无结果时，按 `law_code` 拉兄弟法律

**硬性规则**（系统提示 + 工具流强制）：
1. 法律相关问题**必须**先调 `kb_search`。
2. 模型**只能**基于检索到的素材作答，禁止凭记忆编法条号 / 司法解释 / 案例号。
3. 检索不到时返回硬阻止串（`未检索到对应法律条款…`），模型必须如实告知用户。
4. 每个回答末尾附 `[1][2]…` 引用编号；前端在 AI 消息下方展示可折叠的来源区。
5. 命中 `is_current=false` 的文档会显式标 `已废止` 标签，不与现行版本混引。
6. 系统提示尾部附免责声明：法律建议仅供参考，重大事项请咨询执业律师。

**管理 UI**：登录 → 侧边栏 → 📚 知识库。Admin 可上传 TXT/MD/PDF/docx，
按法律 / 类型 / 现行状态过滤查看文档，批量删除，预览检索质量，或一键清空重建。

**离线部署 / 首次预热**：模型首次使用时从 HuggingFace 自动下载到
`EMBEDDING_CACHE_DIR`（默认 `./models`）。模型文件**不会** commit 到
git（已在 `.gitignore`），首次启动会下载；prod Dockerfile 在 build 阶段
预热，runtime 镜像自带。

### 法律知识库数据 — 入库指南

知识库是空的，克隆后只能聊天不能查法律条文。要灌入数据，有两种方式：

**方式 A：`from-api` 自动从国家法律法规数据库抓取**（推荐）

`backend/scripts/fetch_npc_laws.py` 内置了 13 部高频法律的种子元数据
（`law_code / title / version / effective_date / issuing_body`）和每部
法律的 flk ID。脚本走两步：
1. 调 `https://flk.npc.gov.cn/law-search/download/pc?format=docx&bbbs=<id>`
   拿到带签名的 OBS 链接（华为云 OBS，1 小时有效）
2. GET 签名 URL 拉 .docx 字节流
3. `python-docx` 解析为 markdown
4. 走项目既有的 `ingest_file` 链路按「第N条」切分 + ChromaDB 写入

```bash
cd backend

# 1) 看种子清单
python -X utf8 -m scripts.fetch_npc_laws list-seed

# 2) 先测 1 部（最快 30-60s / 部）
python -X utf8 -m scripts.fetch_npc_laws from-api --only 民法典

# 3) 跑全量
python -X utf8 -m scripts.fetch_npc_laws from-api
```

跑完 `/api/v1/knowledge/stats` 应当 `total_documents: 13`。

> **注意**：`SEED_LAWS` 里 12 部法律的 `id` 字段**目前是空的**（只有民法典填了）。
> 克隆者需要去 [flk.npc.gov.cn](https://flk.npc.gov.cn/) 详情页 URL
> 里复制 `?id=` 后那段 UUID 填到 `SEED_LAWS` 字典里。这是**一次性**工作，
> 填完后 commit 一次就永久可用。

**方式 B：`from-files` 手动复制 markdown**（不依赖 flk 接口）

适用：flk 接口抽风、想收录司法解释 / 释义类辅助资料（`doc_type ∈ {interpretation, commentary, scenario, boundary, diff, repeal_note}`）。

```bash
# 1) 准备 markdown 文件，文件名按 _slugify_law_code() 短码
#    民法典 → mfd.md, 刑法 → xf.md, 劳动法 → ldf.md, ...
#    完整短码表见脚本 _slugify_law_code() 注释
mkdir -p data/npc_laws
# 浏览器从 flk / 其它来源复制文本后保存为 data/npc_laws/mfd.md 等
python -X utf8 -m scripts.fetch_npc_laws list-seed   # 找短码

# 2) 跑入库
python -X utf8 -m scripts.fetch_npc_laws from-files
```

**缓存与重跑**：

抓到的 markdown / docx 落到 `data/npc_laws/cache/<slug>.md`，下次
跑自动复用，避免重复下载；要强制重抓用 `--no-cache`。

**QPS 限速**：默认 0.5 req/s（每 2 秒一个请求），是 flk 公共接口的
经验安全值；调快 `--rate 1.0` / 调慢 `--rate 0.2`。

### 项目结构

```
what/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/         # 路由
│   │   ├── core/           # 配置 / 安全 / 依赖注入
│   │   ├── db/             # MySQL & Redis 连接
│   │   ├── models/         # SQLAlchemy 模型
│   │   ├── repositories/   # 数据访问
│   │   ├── schemas/        # Pydantic
│   │   ├── services/       # AI / 存储 / 缓存 / 工具
│   │   │   └── rag/        # ChromaDB + bge-small-zh 流水线
│   │   └── main.py
│   ├── migrations/         # Alembic
│   └── tests/              # 106 个 pytest
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── api/            # axios 客户端
│       ├── components/
│       │   └── knowledge/  # DocumentUploader / DocumentList / StatsOverview
│       ├── composables/    # useSSEChat …
│       ├── layouts/        # DefaultLayout（侧边栏导航）
│       ├── stores/         # Pinia
│       └── views/          # ChatRoom / Knowledge
├── docker-compose.yml      # 开发环境：Redis + MinIO
├── docker-compose.prod.yml # 生产环境：全栈 + kb_data volume
├── nginx.conf.template
├── .github/workflows/      # CI
├── LICENSE                 # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── SECURITY.md
```

### 许可

MIT —— 见 [LICENSE](LICENSE)。

### 致谢

[Open-Meteo](https://open-meteo.com/) · [WMO Weather codes](https://open-meteo.com/en/docs) ·
[DOMPurify](https://github.com/cure53/DOMPurify) · [marked](https://github.com/markedjs/marked) ·
[highlight.js](https://highlightjs.org/) · [Pinia](https://pinia.vuejs.org/) · [FastAPI](https://fastapi.tiangolo.com/)
