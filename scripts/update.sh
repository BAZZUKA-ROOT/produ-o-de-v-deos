#!/usr/bin/env bash
# Atualiza o código, faz backup e reconstrói. Migrações rodam automaticamente na inicialização da API.
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/backup.sh
git pull --ff-only
docker compose build
docker compose up -d
