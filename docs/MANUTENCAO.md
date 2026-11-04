# Manutenção

| Ação | Comando |
|---|---|
| Iniciar | `./scripts/start.sh ollama` (perfis: `ollama`, `comfyui`, `full`; `GPU=1` para GPU) |
| Parar | `./scripts/stop.sh` |
| Logs | `./scripts/logs.sh api worker` |
| Backup (banco + arquivos) | `./scripts/backup.sh` (`--db-only` só banco). Mantém os 14 mais recentes em `./backups` |
| Restaurar | `./scripts/restore.sh backups/AAAAMMDD-HHMMSS` |
| Atualizar | `./scripts/update.sh` (faz backup, `git pull`, rebuild; migrações automáticas) |
| Criar admin | `docker compose exec api python -m app.cli create-admin --email voce@empresa.com` |
| Escalar workers | `docker compose up -d --scale worker=3` ou `WORKER_CONCURRENCY` no `.env` |

## Backup automático (cron)
```
0 3 * * * cd /opt/forja && ./scripts/backup.sh >> backups/backup.log 2>&1
```

## Monitoramento
Painel admin → **Visão geral** (CPU/RAM/disco, status de PostgreSQL, Redis, workers, FFmpeg, Ollama, ComfyUI, TTS),
**Tarefas** (fila, logs detalhados, cancelar/repetir) e **Logs de erros** (com traceback).

## Armazenamento
- Arquivos em volume `forja_storage`; temporários limpos a cada hora (retenção configurável).
- Painel → **Armazenamento**: uso por tipo, limpeza de temporários, verificação/remoção de arquivos órfãos.
- Vídeos renderizados ficam disponíveis enquanto o projeto existir; excluir o projeto remove renders e narrações
  (fotos enviadas permanecem na biblioteca).

## Solução de problemas
| Sintoma | Causa provável |
|---|---|
| Roteiro "modo template" | Ollama offline ou modelo não baixado (Admin → Modelos de IA → Baixar) |
| Cenas com fundo procedural | sem ComfyUI/Pexels configurado e sem fotos enviadas |
| Voz robótica | modelos Kokoro ausentes → `./scripts/download-models.sh` |
| Tarefa "travada" | worker reiniciado; o beat marca como falha em até ~1h; use "Repetir" |
