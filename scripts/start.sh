#!/usr/bin/env bash
# Uso: ./scripts/start.sh [perfis...]  ex.: ./scripts/start.sh ollama comfyui
set -euo pipefail
cd "$(dirname "$0")/.."
ARGS=(-f docker-compose.yml)
[ "${GPU:-0}" = 1 ] && ARGS+=(-f docker-compose.gpu.yml)
for p in "$@"; do ARGS+=(--profile "$p"); done
docker compose "${ARGS[@]}" up -d
docker compose ps
