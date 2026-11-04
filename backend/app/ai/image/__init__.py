"""Fachada de geração de imagens: ComfyUI (IA) -> Pexels (fotos grátis) -> fundo procedural."""

import logging
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageEnhance

from app.ai.image import comfyui, procedural, stock

log = logging.getLogger(__name__)


def _grade(path: Path) -> Path:
    """Correção leve de cor para fotos (contraste/saturação) e normalização para JPEG."""
    out = path.with_suffix(".graded.jpg")
    with Image.open(path) as im:
        im = im.convert("RGB")
        im = ImageEnhance.Contrast(im).enhance(1.06)
        im = ImageEnhance.Color(im).enhance(1.08)
        im.save(out, "JPEG", quality=93)
    path.unlink(missing_ok=True)
    return out


def generate_scene_image(prompt: str, out_path: Path, width: int, height: int, ai_cfg: dict, palette: list[str],
                         style_hint: str = "", should_cancel: Callable[[], bool] | None = None,
                         seed_text: str = "") -> tuple[Path, str, str | None]:
    """Retorna (caminho, engine, aviso)."""
    provider = ai_cfg.get("image_provider", "procedural")
    warn: str | None = None
    order = {"comfyui": ["comfyui", "pexels"], "pexels": ["pexels"], "auto": ["comfyui", "pexels"]}.get(provider, [])
    for name in order:
        if not prompt.strip():
            break
        try:
            if name == "comfyui":
                full = f"{prompt}, {style_hint}" if style_hint and style_hint not in prompt else prompt
                p = comfyui.generate(full + ", high quality, detailed, professional photo", out_path.with_suffix(".png"),
                                     ai_cfg, width, height, should_cancel)
                return p, f"comfyui:{ai_cfg.get('comfyui_checkpoint')}", warn
            if name == "pexels" and ai_cfg.get("pexels_api_key"):
                p = stock.generate(prompt, out_path.with_suffix(".src"), ai_cfg["pexels_api_key"], width, height, seed_text)
                return _grade(p), "pexels", warn
        except comfyui.ComfyUIError as exc:
            if str(exc) == "cancelado":
                raise
            log.warning("ComfyUI falhou: %s", exc)
            if provider == "comfyui":
                warn = f"ComfyUI indisponível ({exc})."
        except stock.StockError as exc:
            log.warning("Pexels falhou: %s", exc)
            warn = (warn + " " if warn else "") + f"Banco de fotos: {exc}."
    p = procedural.generate_background(out_path.with_suffix(".jpg"), width, height, palette,
                                       seed_text=seed_text or prompt or str(out_path))
    if warn:
        warn += " Fundo procedural utilizado."
    return p, "procedural", warn
