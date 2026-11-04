# Forja Studio — vídeos comerciais com IA, 100% open source e self-hosted

Plataforma SaaS para criar vídeos promocionais (Reels, TikTok, Shorts, Stories, anúncios) a partir dos dados de uma empresa:
roteiro por IA local, cenas com imagens (IA, fotos próprias, banco gratuito ou fundos gerados), narração pt-BR, legendas
automáticas, trilha, transições e exportação MP4 — sem APIs pagas.

## Funcionalidades
- **Assistente de criação**: template por segmento → dados da empresa + fotos → formato/duração/estilo → roteiro IA editável.
- **IA local**: roteiro via Ollama (Qwen 2.5, Apache-2.0) com fallback determinístico por templates; imagens via ComfyUI
  (SDXL/SD 1.5); voz via Kokoro-82M (feminina/masculina pt-BR), Piper e eSpeak NG.
- **Render FFmpeg**: Ken Burns com OpenCV (subpixel), 20 transições `xfade`, textos animados (libass), títulos por estilo,
  selo de preço, legendas karaokê, trilha com *ducking*, normalização de loudness (-14 LUFS), marca d'água, tela final.
- **Editor**: player ao vivo, timeline com arrastar/reordenar/redimensionar, inspetor de cena, prévia renderizada rápida.
- **Projetos**: salvar, duplicar, exportar/importar (.zip), excluir; vídeos ficam disponíveis enquanto o projeto existir.
- **40 templates** em 12 segmentos. **Biblioteca** de imagens, logos, músicas e áudios com cota por usuário.
- **Admin**: usuários, projetos, histórico de renders, fila/workers, logs de erro, modelos de IA (download de modelos
  Ollama), armazenamento, templates, CPU/RAM/disco e status dos serviços.
- **Fila**: Celery + Redis com progresso, cancelamento, retentativas controladas, logs por tarefa e notificações.

## Início rápido (Ubuntu + Docker)
```bash
git clone https://github.com/BAZZUKA-ROOT/produ-o-de-v-deos.git forja && cd forja
sudo ./scripts/install.sh --ollama          # + --comfyui para imagens IA, + --gpu com NVIDIA
```
Acesse `http://IP:8080` com o e-mail/senha de admin exibidos (definidos no `.env`).

## Documentação
- [Arquitetura](docs/ARQUITETURA.md)
- [Instalação](docs/INSTALACAO.md)
- [Manutenção, backup e atualização](docs/MANUTENCAO.md)
- [Modelos de IA, licenças, hardware e limitações](docs/MODELOS_E_LICENCAS.md)

## Desenvolvimento local
```bash
# backend
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
cp ../.env.example .env   # ajuste DATABASE_URL/REDIS_URL para localhost
python -m app.cli init && uvicorn app.main:app --reload
celery -A app.workers.celery_app worker -Q default,render -c 2
pytest -q
# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173 (proxy /api -> :8000)
```
