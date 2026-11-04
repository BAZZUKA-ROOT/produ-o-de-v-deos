# Instalação em VPS Ubuntu

## Requisitos mínimos
| Cenário | CPU | RAM | Disco | Observação |
|---|---|---|---|---|
| Básico (sem LLM local) | 2 vCPU | 4 GB | 20 GB | roteiros por template, fotos próprias/Pexels/procedural, voz Kokoro |
| Recomendado CPU | 4–8 vCPU | 16 GB | 60 GB | Ollama `qwen2.5:7b-instruct` (~5 GB RAM), render 1080p |
| Com imagens IA em CPU | 8 vCPU | 16–32 GB | 80 GB | SD 1.5 + LCM-LoRA, ~30–90 s/imagem |
| GPU | 8 vCPU + NVIDIA 8–12 GB VRAM | 16–32 GB | 100 GB | SDXL ~5–15 s/imagem, LLM rápido |

## Passo a passo
```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/BAZZUKA-ROOT/produ-o-de-v-deos.git forja && cd forja
sudo ./scripts/install.sh --ollama
```
O script: instala Docker, cria `.env` com segredos aleatórios, baixa vozes (Kokoro/Piper), sobe os serviços e baixa o
modelo do Ollama. Opções:
- `--comfyui` — sobe o ComfyUI (imagens IA). Baixe um checkpoint: `./scripts/download-models.sh --sd15` (CPU) ou `--sdxl` (GPU).
- `--gpu` — usa `docker-compose.gpu.yml` (requer NVIDIA Container Toolkit).

### Configurar imagens sem GPU (recomendado)
1. Crie uma chave gratuita em https://www.pexels.com/api/.
2. Painel admin → **Modelos de IA** → *Imagens das cenas* → cole a chave (provedor "Automático").
3. Melhor ainda: envie fotos reais dos produtos no assistente de criação — elas têm prioridade nas cenas.

### ComfyUI em CPU (SD 1.5 + LCM)
No painel admin: checkpoint `v1-5-pruned-emaonly.safetensors`, resolução 512, passos 6, CFG 1.5,
sampler `lcm`, scheduler `sgm_uniform`, LoRA `lcm-lora-sdv1-5.safetensors`.

## HTTPS
Coloque um proxy reverso na frente da porta 8080 (ex.: Caddy):
```
seudominio.com.br {
    reverse_proxy localhost:8080
}
```
Atualize `CORS_ORIGINS` no `.env` e reinicie: `docker compose up -d`.

## Variáveis principais (`.env`)
Veja `.env.example` (comentado). Configurações de IA, render e armazenamento também podem ser alteradas
pelo painel admin (persistidas no banco, sobrepõem o `.env`).
