"""Preparação de imagens (cover / contain com fundo desfocado), tela final e camadas auxiliares."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

MOTION_MARGIN = 1.22


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    return ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS, centering=(0.5, 0.45))


def prepare_source(image_path: Path, w: int, h: int, fit: str = "cover", motion: str = "zoom_in") -> np.ndarray:
    """Retorna imagem BGR com margem para movimento (Ken Burns sem upsampling excessivo)."""
    k = 1.0 if motion == "none" else MOTION_MARGIN
    sw, sh = int(w * k), int(h * k)
    with Image.open(image_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if fit == "contain_blur":
            bg = _cover(im, max(sw // 4, 2), max(sh // 4, 2)).filter(ImageFilter.GaussianBlur(12))
            bg = bg.resize((sw, sh), Image.Resampling.BICUBIC)
            bg = Image.eval(bg, lambda v: int(v * 0.55))
            fg = im.copy()
            fg.thumbnail((int(sw * 0.86), int(sh * 0.80)), Image.Resampling.LANCZOS)
            shadow = Image.new("L", (fg.width + 60, fg.height + 60), 0)
            shadow.paste(180, (30, 30, fg.width + 30, fg.height + 30))
            shadow = shadow.filter(ImageFilter.GaussianBlur(22))
            x, y = (sw - fg.width) // 2, (sh - fg.height) // 2
            bg.paste((0, 0, 0), (x - 30, y - 18), shadow)
            bg.paste(fg, (x, y))
            out = bg
        else:
            out = _cover(im, sw, sh)
    return cv2.cvtColor(np.asarray(out), cv2.COLOR_RGB2BGR)


def shade_overlay(path: Path, w: int, h: int, captions: bool, title_positions: set[str]) -> Path:
    """PNG RGBA com gradientes escuros onde há texto, garantindo legibilidade."""
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    alpha = np.zeros((h, 1), np.float32)
    if captions or "bottom" in title_positions:
        alpha = np.maximum(alpha, np.clip((y - 0.55) / 0.45, 0, 1) ** 1.4 * 0.72)
    if "top" in title_positions:
        alpha = np.maximum(alpha, np.clip((0.35 - y) / 0.35, 0, 1) ** 1.4 * 0.6)
    if "center" in title_positions:
        alpha = np.maximum(alpha, (1 - np.clip(np.abs(y - 0.45) / 0.3, 0, 1)) * 0.28)
    a = np.repeat((alpha * 255).astype(np.uint8), w, axis=1)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(path)
    return path


def end_card_image(path: Path, w: int, h: int, palette: list[str], logo_path: Path | None, bg_path: Path) -> tuple[Path, float]:
    """Monta a imagem de fundo da tela final; retorna (caminho, posição vertical do bloco de texto 0..1)."""
    with Image.open(bg_path) as bg:
        base = _cover(bg.convert("RGB"), w, h)
    base = base.filter(ImageFilter.GaussianBlur(max(w, h) // 120))
    base = Image.eval(base, lambda v: int(v * 0.55))
    text_y = 0.36 if h > w else 0.3
    if logo_path and logo_path.exists():
        with Image.open(logo_path) as lg:
            lg = lg.convert("RGBA")
            box = int(min(w, h) * 0.34)
            lg.thumbnail((box, box), Image.Resampling.LANCZOS)
            pad = int(box * 0.12)
            card = Image.new("RGBA", (lg.width + pad * 2, lg.height + pad * 2), (255, 255, 255, 235))
            mask = Image.new("L", card.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=pad, fill=255)
            card.alpha_composite(lg, (pad, pad))
            x = (w - card.width) // 2
            y = int(h * 0.12) if h > w else int(h * 0.08)
            base.paste(card, (x, y), mask)
            text_y = (y + card.height) / h + 0.08
    base.save(path, "JPEG", quality=92)
    return path, min(text_y, 0.6)
