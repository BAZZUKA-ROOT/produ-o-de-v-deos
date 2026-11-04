#!/usr/bin/env bash
# Instalação em Ubuntu 22.04/24.04. Uso: sudo ./scripts/install.sh [--ollama] [--comfyui] [--gpu]
set -euo pipefail
cd "$(dirname "$0")/.."
PROFILES=()
GPU=0
for a in "$@"; do
  case "$a" in
    --ollama) PROFILES+=(--profile ollama) ;;
    --comfyui) PROFILES+=(--profile comfyui) ;;
    --gpu) GPU=1 ;;
  esac
done

if ! command -v docker >/dev/null; then
  echo "→ Instalando Docker"
  apt-get update -y && apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -y && apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

if [ ! -f .env ]; then
  echo "→ Criando .env com segredos aleatórios"
  cp .env.example .env
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 16)|" .env
  ADMIN_PW="$(openssl rand -base64 12 | tr -d '/+=')A1"
  sed -i "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$ADMIN_PW|" .env
  echo "   Senha inicial do admin: $ADMIN_PW (altere após o primeiro login)"
fi

./scripts/download-models.sh

COMPOSE=(docker compose -f docker-compose.yml)
[ "$GPU" = 1 ] && COMPOSE+=(-f docker-compose.gpu.yml)
echo "→ Construindo e iniciando serviços"
"${COMPOSE[@]}" "${PROFILES[@]}" up -d --build

if printf '%s ' "${PROFILES[@]}" | grep -q ollama; then
  MODEL=$(grep -E '^OLLAMA_MODEL=' .env | cut -d= -f2)
  echo "→ Baixando modelo $MODEL no Ollama (pode demorar)"
  "${COMPOSE[@]}" "${PROFILES[@]}" exec -T ollama ollama pull "$MODEL" || echo "  (baixe depois pelo painel admin > Modelos de IA)"
fi
echo "✓ Pronto: http://$(hostname -I | awk '{print $1}'):$(grep -E '^HTTP_PORT=' .env | cut -d= -f2)"
