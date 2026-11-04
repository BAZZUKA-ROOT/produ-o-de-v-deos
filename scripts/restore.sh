#!/usr/bin/env bash
# Restaura um backup. Uso: ./scripts/restore.sh backups/AAAAMMDD-HHMMSS
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:?informe a pasta do backup}"
set -a; . ./.env; set +a
read -r -p "Isto SUBSTITUI o banco e os arquivos atuais. Continuar? [s/N] " ok
[ "$ok" = "s" ] || exit 1
docker compose stop api worker beat
docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-forja}" -d "${POSTGRES_DB:-forja}" --clean --if-exists < "$SRC/db.dump"
if [ -f "$SRC/storage.tar.gz" ]; then
  docker run --rm -v forja_storage:/data/storage -v "$(realpath "$SRC")":/backup alpine \
    sh -c "rm -rf /data/storage/* && tar xzf /backup/storage.tar.gz -C /data"
fi
docker compose start api worker beat
echo "✓ Restaurado de $SRC"
