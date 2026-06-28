# syntax=docker/dockerfile:1.4
# HW6 — Cop-and-Thief MCP Server container.
# Build:  docker build -t hw6-mcp .
# Run cop:   docker run --env MCP_ROLE=cop   --env PORT=8080 --env COP_AUTH_TOKEN   -p 8080:8080 hw6-mcp
# Run thief: docker run --env MCP_ROLE=thief --env PORT=8080 --env THIEF_AUTH_TOKEN -p 8080:8080 hw6-mcp

FROM python:3.11-slim

# Install the uv binary from the official Astral image layer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# --- dependency layer: only rebuilds when pyproject.toml / uv.lock change ---
COPY pyproject.toml uv.lock ./

# Install pinned deps. NOTE: this project declares all deps (incl. runtime ones
# like fastmcp/pyyaml) in the `dev` dependency-group, so we must NOT pass --no-dev
# or the runtime packages are excluded and the server crashes with ModuleNotFoundError.
RUN uv sync --frozen

# --- application layer: copy source after deps for better cache ---
COPY src/ ./src/
COPY config.yaml ./

# --- security: run as non-root ---
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app
USER appuser

# venv python on PATH; Cloud Run injects PORT and MCP_ROLE at runtime
ENV PATH="/app/.venv/bin:$PATH"
ENV MCP_ROLE=cop

# Dispatch: MCP_ROLE=cop → cop_server, MCP_ROLE=thief → thief_server
# exec ensures Python is PID 1 and receives SIGTERM correctly
CMD ["sh", "-c", "exec python -m src.mcp_servers.${MCP_ROLE}_server"]
