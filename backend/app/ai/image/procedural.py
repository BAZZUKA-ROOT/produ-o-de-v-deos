"""Fundos comerciais procedurais (sem IA): gradientes, formas e texturas a partir da paleta.

Usado como alternativa leve quando não há GPU/ComfyUI disponível.
"""

import hashlib
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 40, 40, 60


def _gradient(w: int, h: int, c1, c2, angle: float) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.deg2rad(angle)
    t = (x * np.cos(a) + y * np.sin(a))
    t = (t - t.min()) / max(float(t.max() - t.min()), 1.0)
    t = t[..., None]
    return (np.array(c1, np.float32) * (1 - t) + np.array(c2, np.float32) * t)


def generate_background(path: Path, width: int, height: int, palette: list[str], seed_text: str = "",
                        variant: str | None = None) -> Path:
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    cols = [_rgb(c) for c in (palette or ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"])]
    base, mid, accent = cols[0], cols[1 % len(cols)], cols[2 % len(cols)]
    variant = variant or rnd.choice(["blobs", "rays", "waves", "bokeh", "geometric"])

    arr = _gradient(width, height, base, mid, rnd.uniform(20, 160))
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    m = min(width, height)

    if variant == "blobs":
        for _ in range(6):
            r = rnd.uniform(0.2, 0.55) * m
            cx, cy = rnd.uniform(0, width), rnd.uniform(0, height)
            c = rnd.choice([mid, accent])
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*c, rnd.randint(70, 140)))
        layer = layer.filter(ImageFilter.GaussianBlur(m * 0.12))
    elif variant == "rays":
        cx, cy = width * rnd.uniform(0.2, 0.8), height * rnd.uniform(-0.1, 0.3)
        for i in range(14):
            ang = np.deg2rad(i * 360 / 14 + rnd.uniform(-5, 5))
            L = max(width, height) * 2
            p2 = (cx + L * np.cos(ang - 0.06), cy + L * np.sin(ang - 0.06))
            p3 = (cx + L * np.cos(ang + 0.06), cy + L * np.sin(ang + 0.06))
            d.polygon([(cx, cy), p2, p3], fill=(*accent, 38))
        layer = layer.filter(ImageFilter.GaussianBlur(m * 0.01))
    elif variant == "waves":
        for k in range(5):
            pts = []
            amp = rnd.uniform(0.03, 0.08) * height
            off = height * (0.45 + k * 0.12)
            freq = rnd.uniform(1.0, 2.2)
            for x in range(0, width + 20, 20):
                pts.append((x, off + amp * np.sin(freq * 2 * np.pi * x / width + k)))
            pts += [(width, height), (0, height)]
            d.polygon(pts, fill=(*rnd.choice([mid, accent]), 45 + k * 12))
        layer = layer.filter(ImageFilter.GaussianBlur(3))
    elif variant == "bokeh":
        for _ in range(40):
            r = rnd.uniform(0.02, 0.09) * m
            cx, cy = rnd.uniform(0, width), rnd.uniform(0, height)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*rnd.choice([accent, (255, 255, 255)]), rnd.randint(25, 80)))
        layer = layer.filter(ImageFilter.GaussianBlur(m * 0.008))
    else:
        for _ in range(9):
            s = rnd.uniform(0.1, 0.4) * m
            cx, cy = rnd.uniform(0, width), rnd.uniform(0, height)
            rot = rnd.uniform(0, np.pi)
            poly = [(cx + s * np.cos(rot + j * np.pi / 2), cy + s * np.sin(rot + j * np.pi / 2)) for j in range(4)]
            d.polygon(poly, outline=(*accent, 120), width=max(2, m // 200))
            if rnd.random() < 0.4:
                d.polygon(poly, fill=(*mid, 50))

    img = Image.alpha_composite(img.convert("RGBA"), layer)
    # vinheta + grão sutil para aparência menos "chapada"
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    dist = np.sqrt(((xx - width / 2) / (width / 2)) ** 2 + ((yy - height / 2) / (height / 2)) ** 2)
    vign = (1 - np.clip(dist - 0.6, 0, 1) * 0.55)[..., None]
    out = np.asarray(img.convert("RGB"), np.float32) * vign
    noise = np.random.default_rng(seed).normal(0, 4, (height, width, 1)).astype(np.float32)
    out = (out + noise).clip(0, 255).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(path, "JPEG", quality=92)
    return path
