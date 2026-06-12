# Contributing

Thanks for your interest in improving **What's That? · AI 法律助手**!
This project welcomes bug reports, feature requests, documentation fixes, and
pull requests.

## Code of Conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
Be respectful and constructive.

## How to Contribute

### 1. File an Issue

- **Bug?** Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) template.
- **Idea?** Use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) template.
- Search existing issues first — duplicate reports slow everyone down.

### 2. Open a Pull Request

1. Fork & create a branch: `git checkout -b feat/short-description` or
   `fix/issue-number-description`.
2. Make your changes.
3. Run the test suite (see below) — **all tests must pass**.
4. Push to your fork: `git push origin feat/...`
5. Open a PR using the [PR template](.github/PULL_REQUEST_TEMPLATE.md).
6. Link the related issue (e.g. `Closes #42`).

## Development Setup

See [README.md → Quick Start](README.md#quick-start) for prerequisites and
step-by-step local setup. The short version:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Tests

```bash
# Backend (106 cases)
cd backend && pytest -v

# Frontend
cd frontend
npm run type-check
npm run test
npm run build
```

CI runs both. A green local run is a strong signal your PR will pass CI.

## Style

### Python

- Type hints everywhere (`from __future__ import annotations` is allowed).
- 4-space indent, LF line endings, UTF-8 (see [`.editorconfig`](.editorconfig)).
- Async-first — never block the event loop on network or DB I/O.
- Prefer pure ASGI middleware; **never** use `BaseHTTPMiddleware` (ExceptionGroup
  traps SSE / streaming uploads). See [SECURITY.md](SECURITY.md#middleware-rules).
- Run `pytest backend/tests/` before pushing.

### TypeScript / Vue

- 2-space indent.
- `<script setup lang="ts">` for new components.
- Composables go in `src/composables/`, stores in `src/stores/`.
- Float-layer dropdowns / modals must use `<Teleport to="body">` to escape
  parent `overflow: auto` containers.

### Commits

- Use [Conventional Commits](https://www.conventionalcommits.org/):
  `feat: …`, `fix: …`, `docs: …`, `chore: …`, `test: …`, `refactor: …`.
- Keep commits focused — one logical change per commit.

## Reporting Security Issues

**Do not** file public issues for security vulnerabilities. See
[SECURITY.md](SECURITY.md) for private disclosure instructions.
