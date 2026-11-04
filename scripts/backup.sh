#!/usr/bin/env bash
# Backup do banco (pg_dump) e dos arquivos (vídeos, imagens, áudios). Uso: ./scripts/backup.sh [--db-only]
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
DEST="${BACKUP_DIR:-./backups}/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"
echo "→ Banco de dados"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-forja}" -d "${POSTGRES_DB:-forja}" -Fc > "$DEST/db.dump"
if [ "${1:-}" != "--db-only" ]; then
  echo "→ Arquivos"
  docker run --rm -v forja_storage:/data/storage:ro -v "$(realpath "$DEST")":/backup alpine \
    tar czf /backup/storage.tar.gz -C /data storage
fi
cp .env "$DEST/env.backup"
chmod 600 "$DEST/env.backup"
# mantém os 14 backups mais recentes
ls -1dt "${BACKUP_DIR:-./backups}"/*/ 2>/dev/null | tail -n +15 | xargs -r rm -rf
echo "✓ Backup em $DEST"
