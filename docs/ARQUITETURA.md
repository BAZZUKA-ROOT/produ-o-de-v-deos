# Arquitetura

```
 Navegador ──► nginx (web) ──► /api ──► FastAPI (api) ──► PostgreSQL
                    │                        │   └──────► Redis (broker + rate limit + cancelamento)
                    │ X-Accel-Redirect        ▼
                    └──── /data/storage ◄── Celery worker(s) ──► Ollama (LLM) · ComfyUI (SD) · Kokoro/Piper/eSpeak
                                             │                    FFmpeg + OpenCV + libass
                                          Celery beat (limpeza de temporários, tarefas travadas)
```

## Serviços (docker-compose)
| Serviço | Função |
|---|---|
| `web` | nginx: SPA React, proxy `/api`, entrega de mídia via `X-Accel-Redirect` (suporta *range*) |
| `api` | FastAPI: auth JWT, projetos, cenas, biblioteca, admin; roda migrações + seeds na inicialização |
| `worker` | Celery: roteiro, imagens, narração, prévia, render, download de modelos (filas `default` e `render`) |
| `beat` | agendamentos: limpeza de temporários (1h) e marcação de tarefas travadas (10 min) |
| `postgres` / `redis` | persistência e fila |
| `ollama` (perfil) | LLM local |
| `comfyui` (perfil) | Stable Diffusion (CPU ou GPU) |

## Backend (`backend/app`)
```
api/          rotas REST (auth, projects, assets, general, admin) + serialização
core/         config (.env), db, segurança (argon2, JWT, URLs de mídia assinadas), catálogo de opções
models/       SQLAlchemy: User, Project, Scene, Asset, Template, Job, Notification, ErrorLog, SystemSetting
schemas/      validação Pydantic de entrada
services/     storage (validação/sanitização de uploads), jobs (fila/progresso/cancelamento), pipeline, runtime_settings
ai/llm        roteiro: Ollama com JSON Schema + fallback por templates
ai/image      ComfyUI → Pexels → fundo procedural; cutout.py (remoção de fundo do produto)
ai/tts        Kokoro → Piper → eSpeak (cadeia de fallback)
ai/music      trilhas procedurais originais (sem direitos autorais)
video/        timeline (sincronia/ajuste de duração), frames, motion (OpenCV), ass (textos), renderer (FFmpeg)
workers/      app Celery e tarefas
seed/         templates por segmento
```

### Pipeline de renderização
1. **Imagens** faltantes geradas (provedor configurado, com fallback).
2. **Narração** por cena (assinatura texto+voz+velocidade evita regerar áudio inalterado).
3. **Timeline**: duração efetiva = máx(duração da cena, narração + margens); ajuste automático ao alvo
   (remove folgas → acelera narração até 1,2× → avisa se ainda exceder); legendas fatiadas e sincronizadas.
4. **Cenas**: cada cena tem um layout (`auto` resolve por papel + foto disponível):
   - `hero`, `price`, `features`, `cta`: produto recortado (IS-Net, cache como asset derivado) composto em camadas
     (`video/compose.py`): fundo de estúdio com parallax, brilho, sombra de contato, reflexo, entrada animada,
     flutuação e faixa de luz;
   - `gallery`: cartões com as fotos do projeto entrando em sequência;
   - `kinetic`: tipografia animada (palavras grandes + bloco de cor) para cenas sem foto;
   - `fullscreen`: foto inteira com movimento de câmera (Ken Burns subpixel).
   Frames brutos são enviados ao FFmpeg (x264).
5. **Composição FFmpeg**: `xfade` entre cenas, gradiente de legibilidade, textos ASS animados (libass),
   marca d'água, narração com `adelay`, trilha em loop com `sidechaincompress` (ducking) e `loudnorm`.
6. Saída MP4 H.264/AAC `+faststart`, miniatura, notificação ao usuário.

### Modularidade da IA
Cada capacidade tem uma fachada com provedores intercambiáveis (`ai/llm/script.py`, `ai/image/__init__.py`,
`ai/tts/__init__.py`). Trocar de modelo = alterar configuração no painel admin; novo provedor = nova função registrada.

## Segurança
- Senhas com **Argon2id**; JWT com `token_version` (troca de senha/desativação invalida sessões).
- Limite de tentativas de login por IP+e-mail (Redis); resposta de tempo constante para e-mail inexistente.
- Autorização por dono do recurso (404 para recursos alheios); rotas admin exigem papel `admin`.
- Uploads: extensão + verificação de conteúdo; imagens **re-encodadas** (Pillow, sem EXIF), áudios **transcodificados**
  (FFmpeg) — nada é servido como enviado; limites de tamanho e cota; nomes aleatórios; arquivos `0640`.
- Mídia servida por URL assinada (HMAC, expiração) com `nosniff`, `Content-Disposition` e CSP `sandbox`.
- Importação de projetos valida caminhos do ZIP e reprocessa todos os arquivos.
- Containers rodam como usuário não-root.
