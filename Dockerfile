# syntax=docker/dockerfile:1
# The RollCall image (docs/SPEC.md, Deployment): the web app built with Node, served by the
# Python server, which runs as a non-root user. x86-64 only. Base images are pinned by
# digest; see docs/deploy.md for how they are checked and updated.

# --- The web app ------------------------------------------------------------------------------
FROM node:24-trixie-slim@sha256:0820eaa85e07d0490446dd01d14707e17e6108a36988cf374899cd057eb3812d AS web
# npm 11.21.2: the npm bundled with Node 24 carries undici and brace-expansion versions with
# known advisories. This stage is thrown away; only the built files are kept.
RUN npm install --global --no-audit --no-fund npm@11.21.2
WORKDIR /src/web
COPY web/package.json web/package-lock.json web/.npmrc ./
# Install scripts are not run; packages are checked against the lockfile's hashes.
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- The server and its dependencies ----------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS server
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
WORKDIR /app
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY server/src ./src
RUN uv sync --locked --no-dev --no-editable

# --- The image --------------------------------------------------------------------------------
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
# Debian security updates published since the base image was built.
RUN apt-get update \
    && apt-get upgrade --yes --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 rollcall \
    && useradd --system --uid 10001 --gid rollcall --no-create-home --home-dir /data rollcall \
    && mkdir /data /backups \
    && chown rollcall:rollcall /data /backups \
    && chmod 0700 /data /backups
COPY --from=server /app/.venv /app/.venv
COPY --from=web /src/web/build /app/web
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    WEB_DIR=/app/web \
    DATABASE_URL=sqlite:////data/filament.db \
    BACKUP_DIR=/backups
LABEL org.opencontainers.image.source="https://github.com/sirmeili/rollcall" \
      org.opencontainers.image.title="RollCall" \
      org.opencontainers.image.description="Self-hosted tracker for Bambu Lab filament spools"
USER rollcall
WORKDIR /data
VOLUME ["/data", "/backups"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import json, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4); assert json.load(r)['status'] == 'ok'"]
CMD ["uvicorn", "filament_tracker.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
