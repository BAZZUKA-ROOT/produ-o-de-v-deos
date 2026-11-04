#!/usr/bin/env bash
# Baixa os modelos de voz (Kokoro + Piper). Opcional: SDXL/SD1.5 para o ComfyUI com --sdxl ou --sd15.
set -euo pipefail
cd "$(dirname "$0")/.."
MODELS="${MODELS_PATH:-./models}"
mkdir -p "$MODELS/kokoro" "$MODELS/piper" "$MODELS/comfyui/checkpoints" "$MODELS/comfyui/loras"

fetch() { # url destino
  if [ -s "$2" ]; then echo "✓ $(basename "$2") já existe"; return; fi
  echo "↓ $(basename "$2")"
  curl -fL --retry 4 --retry-delay 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

KOKORO=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
fetch "$KOKORO/kokoro-v1.0.int8.onnx" "$MODELS/kokoro/kokoro-v1.0.int8.onnx"
fetch "$KOKORO/voices-v1.0.bin" "$MODELS/kokoro/voices-v1.0.bin"

PIPER=https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium
fetch "$PIPER/pt_BR-faber-medium.onnx" "$MODELS/piper/pt_BR-faber-medium.onnx"
fetch "$PIPER/pt_BR-faber-medium.onnx.json" "$MODELS/piper/pt_BR-faber-medium.onnx.json"

# Recorte de produtos (remoção de fundo) — IS-Net (Apache-2.0), arquivo distribuído pelo projeto rembg (MIT)
mkdir -p "$MODELS/rembg"
fetch https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx "$MODELS/rembg/isnet-general-use.onnx"

for arg in "$@"; do
  case "$arg" in
    --sdxl)
      fetch https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors \
        "$MODELS/comfyui/checkpoints/sd_xl_base_1.0.safetensors" ;;
    --sd15)
      fetch https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors \
        "$MODELS/comfyui/checkpoints/v1-5-pruned-emaonly.safetensors"
      fetch https://huggingface.co/latent-consistency/lcm-lora-sdv1-5/resolve/main/pytorch_lora_weights.safetensors \
        "$MODELS/comfyui/loras/lcm-lora-sdv1-5.safetensors" ;;
  esac
done
chmod -R a+rX "$MODELS"
echo "Modelos prontos em $MODELS"
