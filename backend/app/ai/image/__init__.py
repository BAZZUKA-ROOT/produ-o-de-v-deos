"""Fachada de geração de imagens com fallback automático."""

import logging
from collections.abc import Callable
from pathlib import Path

from app.ai.image import comfyui, procedural

log = logging.getLogger(__name__)


def generate_scene_image(prompt: str, out_path: Path, width: int, height: int, ai_cfg: dict, palette: list[str],
                         style_hint: str = "", should_cancel: Callable[[], bool] | None = None) -> tuple[Path, str, str | None]:
    """Retorna (caminho, engine, aviso)."""
    if ai_cfg.get("image_provider") == "comfyui" and prompt.strip():
        full = f"{prompt}, {style_hint}".strip(", ") if style_hint and style_hint not in prompt else prompt
        try:
            p = comfyui.generate(full + ", high quality, detailed, professional photo", out_path.with_suffix(".png"),
                                 ai_cfg, width, height, should_cancel)
            return p, f"comfyui:{ai_cfg.get('comfyui_checkpoint')}", None
        except comfyui.ComfyUIError as exc:
            if str(exc) == "cancelado":
                raise
            log.warning("ComfyUI falhou, usando procedural: %s", exc)
            warn = f"ComfyUI indisponível ({exc}); fundo procedural utilizado."
    else:
        warn = None
    p = procedural.generate_background(out_path.with_suffix(".jpg"), width, height, palette, seed_text=prompt or str(out_path))
    return p, "procedural", warn
