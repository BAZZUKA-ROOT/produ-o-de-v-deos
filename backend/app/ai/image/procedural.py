"""Fundos comerciais procedurais (sem IA): gradientes "mesh" suaves, luz de estúdio e textura sutil.

Alternativa leve quando não há GPU/ComfyUI nem banco de fotos configurado.
"""

import colorsys
import hashlib
import random
from pathlib import Path

import numpy as np
from PIL import Image


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 40, 40, 60


def _shade(c: tuple[int, int, int], light: float, sat: float = 1.0) -> np.ndarray:
    h, l_, s = colorsys.rgb_to_hls(*(x / 255 for x in c))
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l_ * light)), max(0.0, min(1.0, s * sat)))
    return np.array([r, g, b], np.float32) * 255


def generate_background(path: Path, width: int, height: int, palette: list[str], seed_text: str = "",
                        variant: str | None = None) -> Path:
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    cols = [_rgb(c) for c in (palette or ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"])]
    base, mid, accent = cols[0], cols[1 % len(cols)], cols[2 % len(cols)]
    variant = variant or rnd.choice(["mesh", "spotlight", "aurora", "split"])

    # trabalha em baixa resolução (gradientes suaves) e amplia: rápido e sem serrilhado
    sw, sh = max(64, width // 4), max(64, height // 4)
    y, x = np.mgrid[0:sh, 0:sw].astype(np.float32)
    x /= sw
    y /= sh
    aspect = sw / sh
    img = np.empty((sh, sw, 3), np.float32)
    img[:] = _shade(base, 0.55)

    def blob(cx: float, cy: float, r: float, color: np.ndarray, strength: float) -> None:
        d2 = ((x - cx) * aspect) ** 2 + (y - cy) ** 2
        w = np.exp(-d2 / (2 * r * r))[..., None] * strength
        img[:] = img * (1 - w) + color * w

    if variant == "spotlight":
        img[:] = _shade(base, 0.35)
        blob(0.5, 0.42, 0.42, _shade(mid, 1.0), 0.95)
        blob(0.5, 0.38, 0.18, _shade(mid, 1.45, 0.9), 0.6)
        floor = np.clip((y - 0.72) / 0.28, 0, 1)[..., None] * 0.55
        img[:] = img * (1 - floor) + _shade(base, 0.25) * floor
        blob(rnd.uniform(0.15, 0.85), 0.1, 0.12, _shade(accent, 1.0), 0.25)
    elif variant == "aurora":
        for k in range(3):
            yy = 0.25 + 0.25 * k + rnd.uniform(-0.05, 0.05)
            band = np.exp(-((y - yy - 0.08 * np.sin(x * 6 + k * 2)) ** 2) / 0.01)[..., None]
            c = _shade(mid if k % 2 == 0 else accent, 1.05)
            img[:] = img * (1 - band * 0.55) + c * band * 0.55
        blob(0.8, 0.15, 0.3, _shade(accent, 0.9), 0.35)
    elif variant == "split":
        ang = rnd.uniform(-0.35, 0.35)
        t = np.clip(((y - 0.55) + (x - 0.5) * ang) * 9, -1, 1)
        w = ((t + 1) / 2)[..., None]
        img[:] = _shade(mid, 0.95) * (1 - w) + _shade(base, 0.5) * w
        blob(0.85, 0.2, 0.25, _shade(accent, 1.0), 0.45)
        blob(0.1, 0.9, 0.3, _shade(mid, 0.8), 0.35)
    else:  # mesh
        pts = [(rnd.uniform(0, 1), rnd.uniform(0, 1)) for _ in range(5)]
        colors = [_shade(mid, 1.0), _shade(accent, 0.95), _shade(mid, 0.7), _shade(base, 0.9), _shade(accent, 0.7)]
        for (cx, cy), c in zip(pts, colors):
            blob(cx, cy, rnd.uniform(0.22, 0.38), c, rnd.uniform(0.55, 0.85))

    # vinheta suave
    dist = np.sqrt(((x - 0.5) * 1.1) ** 2 + ((y - 0.5) * 1.0) ** 2)
    img *= (1 - np.clip(dist - 0.35, 0, 1) * 0.6)[..., None]
    small = Image.fromarray(img.clip(0, 255).astype(np.uint8), "RGB")
    big = np.asarray(small.resize((width, height), Image.Resampling.BICUBIC), np.float32)
    # grão fino para evitar banding em gradientes
    big += np.random.default_rng(seed).normal(0, 2.2, (height, width, 1)).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(big.clip(0, 255).astype(np.uint8)).save(path, "JPEG", quality=93)
    return path
