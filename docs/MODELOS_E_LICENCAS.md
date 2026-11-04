# Modelos de IA, licenças, hardware e limitações

Todos os componentes são gratuitos e executam localmente. Nenhuma API paga é obrigatória.

## Escolhas e licenças
| Função | Padrão | Licença | Uso comercial | Alternativas |
|---|---|---|---|---|
| Roteiro (LLM) | **Qwen2.5-7B-Instruct** via Ollama | Apache-2.0 | ✅ | `qwen2.5:1.5b-instruct` (Apache-2.0, leve); `mistral:7b` (Apache-2.0); Qwen3 (Apache-2.0). Evite `qwen2.5:3b` (licença de pesquisa). Llama 3.x exige atribuição e limite de 700M MAU |
| Fallback de roteiro | gerador por templates | código próprio | ✅ | — |
| Imagens IA | **SDXL base 1.0** (GPU) / **SD 1.5 + LCM-LoRA** (CPU) via ComfyUI | CreativeML Open RAIL++-M / OpenRAIL-M | ✅ com restrições de uso | FLUX.1-schnell (Apache-2.0, pesado). Evite SDXL-Turbo/SD-Turbo e FLUX.1-dev (não comerciais) |
| Recorte de produto | **IS-Net (DIS) `isnet-general-use`** via ONNX Runtime | Apache-2.0 (arquivo distribuído pelo rembg, MIT) | ✅ | U²-Net (Apache-2.0), BiRefNet (MIT, pesado) |
| Fotos | **Pexels API** (opcional, chave grátis) | Licença Pexels | ✅ sem atribuição | fotos próprias do cliente |
| Fundos sem IA | gerador procedural | código próprio | ✅ | — |
| Voz | **Kokoro-82M** (`pf_dora` feminina, `pm_alex`/`pm_santa` masculinas) | Apache-2.0 | ✅ | Piper `pt_BR-faber` (motor GPL-3; dataset CC0, mas *fine-tune* do modelo "lessac", cujo dataset tem termos restritivos — avalie antes de uso comercial); eSpeak NG (GPL-3, robótico) |
| Música | trilhas procedurais originais | código próprio (CC0) | ✅ | upload de músicas livres (ex.: biblioteca do YouTube, Pixabay Music) |
| Vídeo | FFmpeg (libx264), OpenCV, libass | LGPL/GPL, Apache-2.0, ISC | ✅ | — |
| Orquestração | Ollama (MIT), ComfyUI (GPL-3) | | ✅ como serviços separados | |

**Descartados**: Coqui XTTS-v2 (licença CPML, não comercial; empresa encerrada), MusicGen (pesos CC-BY-NC),
ElevenLabs/OpenAI/Runway (pagos).

> Licenças GPL (Piper, eSpeak, ComfyUI, FFmpeg com x264) não impõem obrigações ao uso como serviço (SaaS);
> obrigações surgem ao **distribuir** binários modificados.

## O que roda bem em cada hardware
| Recurso | CPU 4 vCPU | GPU |
|---|---|---|
| Roteiro 7B | 1–3 min por roteiro | 5–15 s |
| Roteiro 1.5B | 20–70 s (qualidade inferior) | < 5 s |
| Narração Kokoro | ~0,5× tempo real | — (CPU suficiente) |
| Imagem SDXL | inviável (minutos) | 5–15 s |
| Imagem SD1.5+LCM 512px | 30–90 s | 1–2 s |
| Recorte de produto (por foto, cacheado) | 2–8 s | — |
| Render 30 s 1080p | 1–3 min (cenas compostas ~+50%) | igual (FFmpeg em CPU) |

## Dica de qualidade (o que mais faz diferença)
Envie **fotos reais dos produtos** no assistente (de preferência com o produto inteiro, fundo simples e boa luz).
A plataforma recorta o produto automaticamente (~2–8 s por foto em CPU, com cache) e monta cenas de estúdio
animadas. Fotos de ambiente (fachada, salão) são usadas em tela cheia com movimento de câmera.

## Limitações conhecidas (sem esconder)
- **Recorte automático** funciona muito bem para objetos (calçados, eletrônicos, cosméticos, comida, embalagens);
  em fotos de ambiente o sistema detecta e usa a foto inteira. Objetos transparentes (vidro) e cabelos podem ter
  bordas imperfeitas — nesse caso escolha o layout "Tela cheia" na cena.
- **Sem GPU, imagens IA são lentas.** O caminho recomendado é: fotos reais do cliente → Pexels → fundo procedural.
  O fundo procedural é abstrato (gradientes + luzes animadas); fica bom com textos fortes, mas não substitui fotos.
- **LLMs pequenos (≤3B)** produzem roteiros mais genéricos; a plataforma completa lacunas (títulos, prompts) e
  valida o JSON, mas a qualidade ideal vem do 7B ou maior.
- **Voz**: Kokoro em pt-BR é natural, porém pode errar a pronúncia de nomes próprios/siglas; telefones, preços,
  porcentagens e @ são normalizados antes da síntese. Escreva nomes como se pronunciam se necessário.
- **Narração enviada pelo usuário**: as legendas são distribuídas pelo tempo de cada cena (não há transcrição
  automática); grave seguindo o roteiro.
- **Pré-visualização ao vivo** no editor é uma aproximação (transições viram *crossfade*); a "Prévia renderizada"
  mostra o resultado real em baixa resolução.
- **Música procedural** é simples; para trilhas mais ricas, envie músicas livres de direitos.
- Armazenamento é local (volume Docker). S3/MinIO pode ser adicionado implementando um novo backend em `services/storage.py`.
