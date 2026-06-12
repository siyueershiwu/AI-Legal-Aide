# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-Meteo 实时天气工具（零密钥、零配置、零注册）
- 文档上传多模态支持（pdf / docx / txt / md / csv）经文件解析 API
- 图片上传多模态支持（豆包 Vision content 数组）
- 统一附件抽象 `services/attachments.py`（image_url + text parts）
- 5 个工具调用：calculator / get_time / weather / translate / search
- 用户认证：JWT 注册 / 登录 / 登出 / 当前用户查询
- 会话管理：创建 / 列表 / 详情 / 删除 / 清空 / 置顶 / 重命名
- SSE 流式 AI 回复 + 同会话多提问 session_id 同步
- 消息点赞点踩
- 历史对话关键字搜索
- 限流中间件（Redis 软依赖，降级不阻塞）
- 完整 pytest 异步测试覆盖（106 passed）

### Changed
- `weather` 工具从 QWeather 切换到 Open-Meteo，避开 GeoAPI 权限延迟
- 前端浮层菜单一律 `Teleport to="body"`，修复 overflow:auto 列表的 z-index 陷阱
- 路径统一：前端目录 `vue.what/` → `frontend/`
- 健康检查路径统一为 `/healthz`（k8s 惯例）

### Fixed
- 文件上传 `MissingGreenlet` on `server_default` 列：repo `create()` 改用 `await session.refresh()`
- 文件上传触发 `ExceptionGroup`：`BaseHTTPMiddleware` 全部替换为纯 ASGI 实现
- 同会话多 session bug：SSE 首帧未带 session_id 导致重复建会话
- 历史对话下拉菜单被下项 hover 状态盖住：`Teleport to="body"` + 动态坐标

## [1.0.0] - 2026-06-12

### Added
- 初始发布：FastAPI + Vue 3 + 豆包多模态 AI 对话后端与前端
- 5 工具调用 + 4 文件类型上传 + 会话管理 + 用户认证
