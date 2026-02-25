# AGENTS.md

## Cursor Cloud specific instructions

### Overview

**Get My Subtitle** is a Python microservices system for automated subtitle management (download, translate, track) for media servers. It uses FastAPI, RabbitMQ, Redis, and OpenAI.

### Services

| Service | Port | Purpose |
|---------|------|---------|
| Manager (FastAPI) | 8000 | API server, orchestrator, event consumer |
| Scanner | 8001 | File system watcher, Jellyfin webhook receiver |
| Downloader | — | Worker: downloads subtitles from OpenSubtitles |
| Translator | — | Worker: translates subtitles via OpenAI |
| Consumer | — | Worker: processes events, updates Redis state |
| Redis | 6379 | Job state storage |
| RabbitMQ | 5672/15672 | Message broker |

### Running services

- **Infrastructure**: `sudo docker compose up -d redis rabbitmq` (requires Docker; see setup notes below).
- **Manager API (dev)**: `cd src/manager && PYTHONPATH=/workspace/src uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Standard commands are documented in `Makefile` (`make help` lists all targets) and `README.md`.

### Lint / Test / Build

- **Lint**: `black --check .` and `isort --check-only .` and `flake8 .` (or `make lint` for black+isort only).
- **Unit tests**: `PYTHONPATH=src pytest -m unit --no-cov` — no Docker required.
- **Integration tests**: Require Redis + RabbitMQ running. Use `make test-integration-full` for full Docker environment.
- **All tests**: `PYTHONPATH=src pytest --no-cov`

### Non-obvious gotchas

1. **PYTHONPATH**: Always set `PYTHONPATH=src` (or `/workspace/src`) when running tests or services outside Docker. The `conftest.py` adds `src/` to `sys.path`, but the settings module loads at import time and needs the path set.

2. **`.env` file and `SCANNER_MEDIA_EXTENSIONS`**: The `env.template` uses comma-separated format for `SCANNER_MEDIA_EXTENSIONS` (e.g. `.mp4,.mkv,...`), but pydantic-settings v2 expects JSON array format for `List[str]` fields loaded from `.env`. When creating `.env` from `env.template`, change this line to JSON format: `SCANNER_MEDIA_EXTENSIONS=[".mp4",".mkv",".avi",".mov",".m4v",".webm"]`. Otherwise, config loading fails with `SettingsError`.

3. **Docker in Cloud Agent VM**: Docker must be installed with `fuse-overlayfs` storage driver and `iptables-legacy` for the nested container environment. The daemon must be started with `sudo dockerd` before using `docker compose`.

4. **`~/.local/bin` on PATH**: pip installs CLI tools (pytest, black, isort, flake8, uvicorn, etc.) to `~/.local/bin`. Ensure this is on PATH: `export PATH="$HOME/.local/bin:$PATH"`.

5. **Pre-existing lint issues**: The repository has pre-existing black formatting and flake8 issues in test files. These are not caused by setup.
