#!/usr/bin/env bash
cd "$(dirname "$0")/.."
docker compose logs -f --tail=200 "${@:-api worker}"
