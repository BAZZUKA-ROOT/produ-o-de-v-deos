"""Compositor em camadas para apresentação de produtos.

Cada cena é montada quadro a quadro (OpenCV/numpy) com: fundo de estúdio com parallax, brilho atrás do produto,
produto recortado com entrada animada, flutuação, sombra no chão, reflexo e faixa de luz passando.
Os textos continuam em ASS (libass) por cima, posicionados conforme o layout.
"""

import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.video.motion import Cancelled

LAYOUTS = ["auto", "fullscreen", "hero", "price", "features", "cta", "gallery", "kinetic"]


def _hex(c: str) -> np.ndarray:
    h = c.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)  # BGR


def _ease_out_back(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


@dataclass
class Box:
    cx: float
    cy: float
    bw: float
    bh: float


@dataclass
class LayoutGeom:
    product: Box | None
    title_y: float
    title_align: str = "center"   # center | left
    text_x: float = 0.5
    subtitle_gap: float = 0.03
    bullets_y: float | None = None
    badge: tuple[float, float] | None = None
    text_w: float = 0.36


def geometry(layout: str, w: int, h: int) -> LayoutGeom:
    vertical = h > w * 1.15
    square = not vertical and w < h * 1.15
    if layout == "hero":
        if vertical:
            return LayoutGeom(Box(0.5, 0.54, 0.9, 0.54), title_y=0.15)
        if square:
            return LayoutGeom(Box(0.5, 0.58, 0.7, 0.58), title_y=0.13)
        return LayoutGeom(Box(0.68, 0.53, 0.5, 0.74), title_y=0.42, title_align="left", text_x=0.07, text_w=0.36)
    if layout == "price":
        if vertical:
            return LayoutGeom(Box(0.46, 0.45, 0.78, 0.38), title_y=0.13, badge=(0.7, 0.63))
        if square:
            return LayoutGeom(Box(0.4, 0.55, 0.62, 0.62), title_y=0.12, badge=(0.75, 0.62))
        return LayoutGeom(Box(0.33, 0.55, 0.45, 0.75), title_y=0.3, title_align="left", text_x=0.6, badge=(0.75, 0.62), text_w=0.33)
    if layout == "features":
        if vertical:
            return LayoutGeom(Box(0.5, 0.41, 0.86, 0.42), title_y=0.12, bullets_y=0.67)
        if square:
            return LayoutGeom(Box(0.3, 0.55, 0.48, 0.62), title_y=0.12, title_align="left", text_x=0.56, bullets_y=0.42, text_w=0.4)
        return LayoutGeom(Box(0.3, 0.53, 0.45, 0.78), title_y=0.25, title_align="left", text_x=0.58, bullets_y=0.45, text_w=0.36)
    if layout == "cta":
        if vertical:
            return LayoutGeom(Box(0.5, 0.3, 0.62, 0.3), title_y=0.58)
        return LayoutGeom(Box(0.3, 0.52, 0.42, 0.66), title_y=0.42, title_align="left", text_x=0.56, text_w=0.38)
    if layout == "kinetic":
        return LayoutGeom(None, title_y=0.45)
    if layout == "gallery":
        return LayoutGeom(None, title_y=0.13 if vertical else 0.12)
    return LayoutGeom(None, title_y=0.42 if vertical else 0.4)


def studio_background(w: int, h: int, palette: list[str], focus: tuple[float, float] = (0.5, 0.5),
                      floor_y: float | None = 0.72) -> np.ndarray:
    """Fundo de estúdio: luz central, vinheta, chão com leve gradiente e brilho de destaque atrás do produto."""
    sw, sh = max(96, w // 4), max(96, h // 4)
    y, x = np.mgrid[0:sh, 0:sw].astype(np.float32)
    x /= sw
    y /= sh
    asp = sw / sh
    base, mid, accent = _hex(palette[0]), _hex(palette[1]), _hex(palette[2])
    light = np.clip(mid * 1.25 + 25, 0, 255)
    d = np.sqrt(((x - focus[0]) * asp) ** 2 + (y - focus[1] + 0.05) ** 2)
    t = np.clip(d / 0.75, 0, 1)[..., None]
    img = light * (1 - t) ** 1.6 + base * 0.55 * (1 - (1 - t) ** 1.6)
    glow = np.exp(-(((x - focus[0]) * asp) ** 2 + (y - focus[1]) ** 2) / 0.02)[..., None]
    img = img * (1 - glow * 0.35) + accent * glow * 0.35
    if floor_y is not None:
        f = np.clip((y - floor_y) / (1 - floor_y), 0, 1)[..., None]
        img = img * (1 - f * 0.55) + base * 0.35 * f * 0.55
        line = np.exp(-((y - floor_y) ** 2) / 0.0004)[..., None] * 0.12
        img = img + line * 255 * (1 - np.clip(np.abs(x - 0.5) * 2, 0, 1))[..., None]
    out = cv2.resize(img.clip(0, 255).astype(np.uint8), (w, h), interpolation=cv2.INTER_CUBIC)
    noise = np.random.default_rng(7).normal(0, 2.0, (h, w, 1)).astype(np.float32)
    return (out.astype(np.float32) + noise).clip(0, 255).astype(np.uint8)


def load_rgba(path: Path, max_side: int) -> np.ndarray:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGBA")
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        arr = np.asarray(im).copy()
    arr[..., :3] = arr[..., 2::-1][..., :3]  # RGB -> BGR
    return arr


def _fit(prod: np.ndarray, bw: float, bh: float) -> float:
    ph, pw = prod.shape[:2]
    return min(bw / pw, bh / ph)


def _blend(dst: np.ndarray, src_bgr: np.ndarray, alpha: np.ndarray, x: int, y: int) -> None:
    h, w = alpha.shape[:2]
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    sx0, sy0 = x0 - x, y0 - y
    a = alpha[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    if a.ndim == 2:
        a = a[..., None]
    roi = dst[y0:y1, x0:x1].astype(np.float32)
    s = src_bgr[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)].astype(np.float32)
    dst[y0:y1, x0:x1] = (roi * (1 - a) + s * a).astype(np.uint8)


@dataclass
class SceneSpec:
    layout: str
    duration: float
    palette: list[str]
    product: Path | None = None          # PNG com transparência
    photos: list[Path] = field(default_factory=list)
    entry: str = "pop"                   # pop | slide_left | slide_up


def _product_frames(spec: SceneSpec, w: int, h: int, fps: int):
    g = geometry(spec.layout, w, h)
    box = g.product
    assert box is not None and spec.product is not None
    bg = studio_background(w, h, spec.palette, (box.cx, box.cy), floor_y=min(box.cy + box.bh / 2, 0.92))
    prod = load_rgba(spec.product, int(max(w, h) * 0.9))
    base_scale = _fit(prod, box.bw * w, box.bh * h)
    ph, pw = prod.shape[:2]
    # sombra de contato (elipse desfocada)
    sh_w, sh_h = int(pw * base_scale * 0.85), max(8, int(ph * base_scale * 0.08))
    shadow = np.zeros((sh_h * 3, sh_w + sh_h * 2), np.float32)
    cv2.ellipse(shadow, (shadow.shape[1] // 2, shadow.shape[0] // 2), (sh_w // 2, sh_h // 2), 0, 0, 360, 1.0, -1)
    shadow = cv2.GaussianBlur(shadow, (0, 0), sh_h * 0.6) * 0.55
    black = np.zeros((*shadow.shape, 3), np.uint8)
    n = max(1, int(round(spec.duration * fps)))
    for i in range(n):
        t = i / fps
        frame = bg.copy()
        # parallax: fundo aproxima devagar
        z = 1 + 0.04 * (t / max(spec.duration, 0.1))
        if z > 1.001:
            m = cv2.getRotationMatrix2D((w * box.cx, h * box.cy), 0, z)
            frame = cv2.warpAffine(frame, m, (w, h), borderMode=cv2.BORDER_REFLECT)
        enter = _ease_out_back(t / 0.75)
        alpha_in = min(t / 0.35, 1.0)
        scale = base_scale * (0.72 + 0.28 * enter if spec.entry == "pop" else 1.0) * (1 + 0.05 * _ease(t / spec.duration))
        float_y = math.sin(t * 1.6) * h * 0.006
        dx = 0.0
        if spec.entry == "slide_left":
            dx = (1 - _ease(t / 0.7)) * w * 0.6
        dy = (1 - _ease(t / 0.7)) * h * 0.25 if spec.entry == "slide_up" else 0.0
        sw_, sh_ = max(2, int(pw * scale)), max(2, int(ph * scale))
        p = cv2.resize(prod, (sw_, sh_), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        cx, cy = w * box.cx + dx, h * box.cy + float_y + dy
        x, y = int(cx - sw_ / 2), int(cy - sh_ / 2)
        floor = int(h * box.cy + base_scale * ph / 2)
        # sombra
        _blend(frame, black, shadow * alpha_in * (1 - 0.3 * (float_y / (h * 0.006) + 1) / 2),
               int(cx - shadow.shape[1] / 2), int(floor - shadow.shape[0] / 2))
        a = p[..., 3].astype(np.float32) / 255 * alpha_in
        rgb = p[..., :3]
        # reflexo
        refl_h = int(sh_ * 0.35)
        if refl_h > 4 and floor + refl_h < h + refl_h:
            r_rgb = rgb[::-1][:refl_h]
            r_a = a[::-1][:refl_h] * np.linspace(0.22, 0, refl_h, dtype=np.float32)[:, None]
            _blend(frame, r_rgb, r_a, x, floor + 2)
        # faixa de luz passando (uma vez, após a entrada)
        sweep_t = (t - 0.9) / 1.0
        if 0 <= sweep_t <= 1:
            yy, xx = np.mgrid[0:sh_, 0:sw_].astype(np.float32)
            pos = (xx / sw_ + yy / sh_ * 0.5) - (sweep_t * 1.9 - 0.4)
            band = np.exp(-(pos ** 2) / 0.006)[..., None] * 0.45
            rgb = np.clip(rgb.astype(np.float32) + band * 255 * (a[..., None] > 0.1), 0, 255).astype(np.uint8)
        _blend(frame, rgb, a, x, y)
        yield frame


def _gallery_frames(spec: SceneSpec, w: int, h: int, fps: int):
    vertical = h > w * 1.15
    bg = studio_background(w, h, spec.palette, (0.5, 0.55), floor_y=None)
    photos = spec.photos[:4]
    k = len(photos)
    if vertical:
        cols, rows = (2, 2) if k >= 3 else (1, k)
    else:
        cols, rows = (k, 1)
    area_top, area_h = (0.22, 0.58) if vertical else (0.24, 0.6)
    cw, ch = w * 0.86 / cols, h * area_h / rows
    cards = []
    for idx, ph in enumerate(photos):
        with Image.open(ph) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            card_w, card_h = int(cw * 0.9), int(ch * 0.9)
            im = ImageOps.fit(im, (card_w, card_h), Image.Resampling.LANCZOS)
            arr = np.asarray(im)[..., ::-1].copy()
        r = int(min(card_w, card_h) * 0.06)
        mask = np.zeros((card_h, card_w), np.float32)
        cv2.rectangle(mask, (r, 0), (card_w - r, card_h), 1.0, -1)
        cv2.rectangle(mask, (0, r), (card_w, card_h - r), 1.0, -1)
        for cxy in ((r, r), (card_w - r, r), (r, card_h - r), (card_w - r, card_h - r)):
            cv2.circle(mask, cxy, r, 1.0, -1)
        col, row = idx % cols, idx // cols
        cx = w * 0.07 + cw * (col + 0.5)
        cy = h * area_top + ch * (row + 0.5)
        cards.append((arr, mask, cx, cy, (idx % 2 * 2 - 1) * 3.0))
    n = max(1, int(round(spec.duration * fps)))
    for i in range(n):
        t = i / fps
        frame = bg.copy()
        for j, (arr, mask, cx, cy, rot) in enumerate(cards):
            lt = t - 0.18 * j
            if lt <= 0:
                continue
            e = _ease_out_back(lt / 0.6)
            s = 0.6 + 0.4 * e
            drift = math.sin(t * 1.2 + j) * 0.004 * h
            hh, ww = mask.shape
            m = cv2.getRotationMatrix2D((ww / 2, hh / 2), rot * (1 - _ease(lt / 1.2)) + rot * 0.3, s)
            pad = int(max(ww, hh) * 0.15)
            m[0, 2] += pad
            m[1, 2] += pad
            size = (ww + pad * 2, hh + pad * 2)
            a = cv2.warpAffine(mask, m, size) * min(lt / 0.25, 1)
            img = cv2.warpAffine(arr, m, size)
            shadow = cv2.GaussianBlur(a, (0, 0), max(4, ww * 0.03)) * 0.5
            x, y = int(cx - size[0] / 2), int(cy - size[1] / 2 + drift)
            _blend(frame, np.zeros_like(img), shadow, x + int(ww * 0.02), y + int(hh * 0.03))
            _blend(frame, img, a, x, y)
        yield frame


def _kinetic_frames(spec: SceneSpec, w: int, h: int, fps: int, bg_image: Path | None):
    if bg_image is not None:
        with Image.open(bg_image) as im:
            base = ImageOps.fit(im.convert("RGB"), (w, h), Image.Resampling.LANCZOS)
            bg = np.asarray(base)[..., ::-1].copy()
    else:
        bg = studio_background(w, h, spec.palette, (0.5, 0.45), floor_y=None)
    n = max(1, int(round(spec.duration * fps)))
    for i in range(n):
        t = i / fps
        z = 1 + 0.06 * _ease(t / max(spec.duration, 0.1))
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 0, z)
        yield cv2.warpAffine(bg, m, (w, h), borderMode=cv2.BORDER_REFLECT)


def render_scene(spec: SceneSpec, out: Path, w: int, h: int, fps: int, preset: str, crf: int,
                 bg_image: Path | None = None, on_frame: Callable[[int, int], None] | None = None,
                 should_cancel: Callable[[], bool] | None = None) -> Path:
    if spec.layout == "gallery":
        frames = _gallery_frames(spec, w, h, fps)
    elif spec.layout == "kinetic":
        frames = _kinetic_frames(spec, w, h, fps, bg_image)
    else:
        frames = _product_frames(spec, w, h, fps)
    total = max(1, int(round(spec.duration * fps)))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i, frame in enumerate(frames):
            if should_cancel and i % 15 == 0 and should_cancel():
                raise Cancelled()
            proc.stdin.write(frame.tobytes())
            if on_frame and i % 10 == 0:
                on_frame(i, total)
        proc.stdin.close()
        if proc.wait(timeout=600) != 0:
            raise RuntimeError("FFmpeg falhou na cena composta: " + proc.stderr.read().decode(errors="ignore")[-400:])
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    return out
