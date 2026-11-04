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

from app.video import fx
from app.video.motion import Cancelled

LAYOUTS = ["auto", "fullscreen", "hero", "price", "features", "cta", "gallery", "kinetic", "phone", "laptop"]


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
            return LayoutGeom(Box(0.5, 0.42, 0.86, 0.46), title_y=0.12, bullets_y=0.705)
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
    entry: str = "pop"                   # pop | swing | rise | slide_left
    seed: int = 1
    stage: bool = True                   # palco animado (feixes, grade, partículas)


def _stage(spec: SceneSpec, w: int, h: int, focus: tuple[float, float], floor_y: float | None):
    base = studio_background(w, h, spec.palette, focus, floor_y=floor_y)
    base = cv2.convertScaleAbs(base, alpha=0.62)  # palco escuro: contraste para luzes e objeto
    return fx.Stage(w, h, spec.palette, base, seed=spec.seed, beams=spec.stage, grid=spec.stage and floor_y is not None,
                    particles=spec.stage, floor_y=floor_y or 0.75)


def _entry_pose(entry: str, t: float, w: int, h: int) -> tuple[float, float, float, float, float, float]:
    """(escala, dx, dy, yaw, pitch, opacidade) da animação de entrada."""
    p = t / 0.85
    op = min(t / 0.3, 1.0)
    if entry == "swing":
        e = fx.ease_out_cubic(p)
        return 0.85 + 0.15 * e, (1 - e) * w * 0.25, 0.0, (1 - e) * 1.0, (1 - e) * -0.15, op
    if entry == "rise":
        e = fx.ease_out_cubic(p)
        return 0.9 + 0.1 * e, 0.0, (1 - e) * h * 0.3, 0.0, (1 - e) * 0.55, op
    if entry == "slide_left":
        e = fx.ease_out_cubic(p)
        return 1.0, (1 - e) * -w * 0.7, 0.0, (1 - e) * -0.6, 0.0, op
    e = fx.ease_out_back(p)
    return 0.6 + 0.4 * e, 0.0, 0.0, 0.0, 0.0, op


def _product_frames(spec: SceneSpec, w: int, h: int, fps: int):
    g = geometry(spec.layout, w, h)
    box = g.product
    assert box is not None and spec.product is not None
    floor = min(box.cy + box.bh / 2 + 0.02, 0.93)
    stage = _stage(spec, w, h, (box.cx, box.cy), floor)
    accent = fx.hex_bgr(spec.palette[2])
    prod = load_rgba(spec.product, int(max(w, h) * 0.9))
    ph, pw = prod.shape[:2]
    base_scale = _fit(prod, box.bw * w, box.bh * h) * 0.94
    n = max(1, int(round(spec.duration * fps)))
    for i in range(n):
        t = i / fps
        frame = stage.frame(t, zoom=1 + 0.05 * fx.ease(t / max(spec.duration, 0.1)), focus=(box.cx, box.cy))
        sc, dx, dy, yaw0, pitch0, op = _entry_pose(spec.entry, t, w, h)
        yaw = yaw0 + 0.13 * math.sin(t * 0.55 + spec.seed)
        pitch = pitch0 + 0.05 * math.sin(t * 0.4 + 1.3)
        fy = math.sin(t * 1.5) * h * 0.006
        scale = base_scale * sc * (1 + 0.04 * fx.ease(t / spec.duration))
        quad = fx.project_quad(pw, ph, scale, w * box.cx + dx, h * box.cy + dy + fy, yaw, pitch,
                               focal=max(w, h) * 1.4)
        sweep = (t - 1.0) / 1.1
        fx.draw_object(frame, prod, quad, accent, op, floor_y=int(h * floor), sweep=sweep)
        yield frame


def _rounded_card(img: np.ndarray, radius: int) -> np.ndarray:
    hh, ww = img.shape[:2]
    mask = np.zeros((hh, ww), np.uint8)
    cv2.rectangle(mask, (radius, 0), (ww - radius, hh), 255, -1)
    cv2.rectangle(mask, (0, radius), (ww, hh - radius), 255, -1)
    for cxy in ((radius, radius), (ww - radius, radius), (radius, hh - radius), (ww - radius, hh - radius)):
        cv2.circle(mask, cxy, radius, 255, -1, cv2.LINE_AA)
    # borda clara fina (acabamento de vidro)
    rgba = np.dstack([img, mask])
    cv2.rectangle(rgba, (1, 1), (ww - 2, hh - 2), (255, 255, 255, 0), 0)
    return rgba


def _gallery_frames(spec: SceneSpec, w: int, h: int, fps: int):
    vertical = h > w * 1.15
    stage = _stage(spec, w, h, (0.5, 0.5), 0.86 if vertical else 0.88)
    accent = fx.hex_bgr(spec.palette[2])
    photos = spec.photos[:4]
    k = len(photos)
    cols, rows = ((2, 2) if k >= 3 else (1, k)) if vertical else (k, 1)
    area_top, area_h = (0.22, 0.58) if vertical else (0.24, 0.6)
    cw, ch = w * 0.86 / cols, h * area_h / rows
    cards = []
    for idx, ph in enumerate(photos):
        with Image.open(ph) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            card_w, card_h = int(cw * 0.88), int(ch * 0.88)
            im = ImageOps.fit(im, (card_w, card_h), Image.Resampling.LANCZOS)
            arr = np.asarray(im)[..., ::-1].copy()
        cards.append((_rounded_card(arr, int(min(card_w, card_h) * 0.06)),
                      w * 0.07 + cw * (idx % cols + 0.5), h * area_top + ch * (idx // cols + 0.5)))
    n = max(1, int(round(spec.duration * fps)))
    for i in range(n):
        t = i / fps
        frame = stage.frame(t, zoom=1 + 0.04 * fx.ease(t / spec.duration))
        for j, (card, cx, cy) in enumerate(cards):
            lt = t - 0.16 * j
            if lt <= 0:
                continue
            e = fx.ease_out_back(lt / 0.7, 1.2)
            yaw = (1 - fx.ease_out_cubic(lt / 0.8)) * (0.9 if j % 2 else -0.9) + 0.08 * math.sin(t * 0.7 + j)
            pitch = 0.05 * math.sin(t * 0.5 + j * 1.3)
            q = fx.project_quad(card.shape[1], card.shape[0], 0.7 + 0.3 * e, cx, cy + math.sin(t * 1.1 + j) * h * 0.004,
                                yaw, pitch, roll=(1 - fx.ease(lt / 1.0)) * (0.12 if j % 2 else -0.12),
                                focal=max(w, h) * 1.3)
            fx.draw_object(frame, card, q, accent, min(lt / 0.25, 1.0), floor_y=None, rim=0.35, shadow=0.6)
        yield frame


def _kinetic_frames(spec: SceneSpec, w: int, h: int, fps: int, bg_image: Path | None):
    stage = _stage(spec, w, h, (0.5, 0.42), 0.8)
    n = max(1, int(round(spec.duration * fps)))
    for i in range(n):
        t = i / fps
        yield stage.frame(t, zoom=1 + 0.06 * fx.ease(t / max(spec.duration, 0.1)), focus=(0.5, 0.42))


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
    post = fx.Post(w, h, fx.hex_bgr(spec.palette[2]))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i, frame in enumerate(frames):
            if should_cancel and i % 15 == 0 and should_cancel():
                raise Cancelled()
            t = i / fps
            flash = max(0.0, 1 - t / 0.35) * 0.28 if i > 0 or spec.entry != "pop" else 0.0
            proc.stdin.write(post.apply(frame, i, flash).tobytes())
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
