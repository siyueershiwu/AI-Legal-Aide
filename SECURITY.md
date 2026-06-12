# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not file a public GitHub issue for security vulnerabilities.**

Send a private report to **security@[your-domain]** (replace with the project's
actual contact). Include:

- A clear description of the issue and its impact
- Reproduction steps (proof-of-concept code is welcome)
- Affected component / file path
- Your name / handle for credit (optional)

We aim to acknowledge within **72 hours** and triage within **7 days**.

## Threat Model

This is a self-hosted single-tenant demo. It is **not** designed to be exposed
to the public internet without additional hardening (WAF, reverse proxy with
rate limiting, network segmentation, etc.). If you deploy it publicly, you do
so at your own risk.

## Middleware Rules

- **Never use `starlette.middleware.base.BaseHTTPMiddleware`** for any route
  that may produce streaming responses (SSE) or large file uploads. The
  streaming response `ExceptionGroup` traps uncaught exceptions and surfaces a
  500 to the client without proper context. Write pure ASGI middleware instead.
- Rate limit middleware is implemented as pure ASGI in
  `backend/app/middleware/`. Do not "simplify" it back to `BaseHTTPMiddleware`.

## Secret Hygiene

The repo ships with `.env.example` files containing **placeholders only**.
Real secrets live in `.env` (gitignored) or your deployment secret store.

> **If you ever pasted or shared the contents of a real `.env` (e.g. in a
> chat, screenshot, or commit), rotate every key immediately:**
>
> - `SECRET_KEY` (JWT signing)
> - `DOUBAO_API_KEY` (火山引擎 console)
> - `TAVILY_API_KEY` (Tavily dashboard)
> - `BAIDU_APPID` / `BAIDU_SECRET` (百度翻译开放平台)
> - MySQL `root` password
> - Redis password
> - MinIO `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`

`SECRET_KEY` should be at least **86 random characters**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Secret Scanning

This repo is configured for [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning).
If you accidentally push a real key, GitHub will revoke it automatically — but
**rotate it yourself first**; the alert is just a heads-up.

## Disclosure Timeline

1. Reporter emails privately.
2. Maintainer triages within 7 days.
3. Patch developed privately; embargo typically 30-90 days.
4. CVE assigned if applicable.
5. Public disclosure + release + credit.
