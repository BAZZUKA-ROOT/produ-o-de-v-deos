"""Efeitos visuais de alto nível: palco animado, produto em 3D, pós-processamento cinematográfico.

Tudo em OpenCV/numpy com operações uint8 vetorizadas (rápidas em CPU).
"""

import math

import cv2
import numpy as np


def hex_bgr(c: str) -> tuple[int, int, int]:
    h = c.lstrip("#")
    return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_out_cubic(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_out_back(t: float, s: float = 1.6) -> float:
    t = min(max(t, 0.0), 1.0) - 1
    return t * t * ((s + 1) * t + s) + 1


# --------------------------------------------------------------------------------------------- palco

class Stage:
    """Fundo de palco animado: gradiente de estúdio, feixes de luz, brilhos que se movem,
    grade em perspectiva rolando no chão e partículas com profundidade."""

    def __init__(self, w: int, h: int, palette: list[str], base: np.ndarray, seed: int = 1,
                 beams: bool = True, grid: bool = True, particles: bool = True, floor_y: float = 0.72):
        self.w, self.h = w, h
        self.base = base
        self.rng = np.random.default_rng(seed)
        self.accent = hex_bgr(palette[2])
        self.mid = hex_bgr(palette[1])
        self.beams = beams
        self.grid = grid
        self.floor_y = floor_y
        self.lw, self.lh = max(64, w // 4), max(64, h // 4)
        xs = [0.12, 0.38, 0.62, 0.88]
        self.beam_src = [(x + self.rng.uniform(-0.06, 0.06), -0.04, (0.5 - x) * 0.7, self.rng.uniform(0.18, 0.32),
                          self.rng.uniform(0, 6.28)) for x in xs]
        fade = np.clip(1 - np.linspace(0, 1, h, dtype=np.float32) / max(floor_y, 0.3), 0, 1) ** 1.3
        self.beam_fade = cv2.merge([(fade * 255).astype(np.uint8)[:, None].repeat(w, 1)] * 3)
        n = 70 if particles else 0
        self.p_xy = self.rng.uniform(0, 1, (n, 2)).astype(np.float32)
        self.p_z = self.rng.uniform(0.2, 1.0, n).astype(np.float32)       # profundidade
        self.p_ph = self.rng.uniform(0, 6.28, n).astype(np.float32)
        self.p_gold = self.rng.uniform(0, 1, n) < 0.65
        self.m = min(w, h)

    def _beams(self, t: float) -> np.ndarray:
        lw, lh = self.lw, self.lh
        layer = np.zeros((lh, lw, 3), np.uint8)
        for k, (sx, sy, ang0, spread, ph) in enumerate(self.beam_src):
            ang = ang0 + 0.25 * math.sin(t * 0.45 + ph)
            L = lh * 1.6
            cx, cy = sx * lw, sy * lh
            p1 = (cx + L * math.sin(ang - spread * 0.18), cy + L * math.cos(ang - spread * 0.18))
            p2 = (cx + L * math.sin(ang + spread * 0.18), cy + L * math.cos(ang + spread * 0.18))
            col = self.accent if k % 2 == 0 else self.mid
            inten = 0.2 + 0.07 * math.sin(t * 1.3 + ph)
            c = tuple(int(v * inten) for v in col)
            cv2.fillPoly(layer, [np.array([(cx, cy), p1, p2], np.int32)], c, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), lw * 0.012)
        layer = cv2.resize(layer, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        return cv2.multiply(layer, self.beam_fade, scale=1 / 255)

    def _glows(self, t: float) -> np.ndarray:
        lw, lh = self.lw, self.lh
        layer = np.zeros((lh, lw, 3), np.uint8)
        for k in range(3):
            x = (0.5 + 0.38 * math.sin(t * 0.21 + k * 2.1)) * lw
            y = (0.45 + 0.3 * math.cos(t * 0.17 + k * 1.7)) * lh
            col = self.accent if k == 0 else self.mid
            cv2.circle(layer, (int(x), int(y)), int(lw * 0.22), tuple(int(v * 0.22) for v in col), -1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), lw * 0.12)
        return cv2.resize(layer, (self.w, self.h), interpolation=cv2.INTER_LINEAR)

    def _grid(self, t: float) -> np.ndarray:
        w, h = self.w, self.h
        layer = np.zeros((h, w, 3), np.uint8)
        hy = int(h * self.floor_y)
        col = tuple(int(v * 0.55) for v in self.accent)
        col2 = tuple(int(v * 0.45) for v in self.mid)
        vx = w / 2
        for i in range(-12, 13):
            x_bottom = vx + i * w * 0.16
            cv2.line(layer, (int(vx + i * w * 0.012), hy), (int(x_bottom), h), col2, 1, cv2.LINE_AA)
        # linhas horizontais rolando em direção à câmera
        off = (t * 0.35) % 1.0
        for k in range(10):
            d = (k + off) / 10
            y = hy + (h - hy) * d ** 2.2
            cv2.line(layer, (0, int(y)), (w, int(y)), col, 1, cv2.LINE_AA)
        fade = np.clip((np.arange(h, dtype=np.float32) - hy) / max(h - hy, 1), 0, 1) ** 0.7
        fade = (fade * (1 - fade * 0.3))[:, None, None]
        layer = (layer * fade).astype(np.uint8)
        # brilho do horizonte
        cv2.line(layer, (0, hy), (w, hy), tuple(int(v * 0.6) for v in self.accent), max(1, self.m // 500), cv2.LINE_AA)
        return cv2.GaussianBlur(layer, (3, 3), 0)

    def _particles(self, t: float) -> np.ndarray:
        w, h = self.w // 2, self.h // 2
        layer = np.zeros((h, w, 3), np.uint8)
        if not len(self.p_z):
            return layer
        y = (self.p_xy[:, 1] - t * 0.03 * self.p_z) % 1.0
        x = (self.p_xy[:, 0] + 0.02 * np.sin(t * 0.6 + self.p_ph)) % 1.0
        tw = 0.5 + 0.5 * np.sin(t * 2.5 + self.p_ph * 3)
        for i in range(len(self.p_z)):
            r = max(1, int(self.m / 2 * 0.004 * (0.4 + self.p_z[i])))
            b = float(tw[i] * self.p_z[i])
            col = self.accent if self.p_gold[i] else (255, 255, 255)
            cv2.circle(layer, (int(x[i] * w), int(y[i] * h)), r, tuple(int(c * b) for c in col), -1, cv2.LINE_AA)
        glow = cv2.GaussianBlur(layer, (0, 0), 3)
        layer = cv2.add(layer, glow)
        return cv2.resize(layer, (self.w, self.h), interpolation=cv2.INTER_LINEAR)

    def frame(self, t: float, zoom: float = 1.0, focus: tuple[float, float] = (0.5, 0.5)) -> np.ndarray:
        f = self.base
        if zoom > 1.001:
            m = cv2.getRotationMatrix2D((self.w * focus[0], self.h * focus[1]), 0, zoom)
            f = cv2.warpAffine(f, m, (self.w, self.h), borderMode=cv2.BORDER_REFLECT)
        else:
            f = f.copy()
        f = cv2.add(f, self._glows(t))
        if self.beams:
            f = cv2.add(f, self._beams(t))
        if self.grid:
            f = cv2.add(f, self._grid(t))
        return cv2.add(f, self._particles(t))


# --------------------------------------------------------------------------------------------- produto 3D

def project_quad(pw: int, ph: int, scale: float, cx: float, cy: float, yaw: float, pitch: float,
                 roll: float = 0.0, focal: float = 1800.0) -> np.ndarray:
    """Cantos projetados de um plano (pw x ph) girado em 3D e centrado em (cx, cy)."""
    hw, hh = pw * scale / 2, ph * scale / 2
    pts = np.array([[-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0]], np.float64)
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    p = pts @ (rz @ rx @ ry).T
    z = p[:, 2] + focal
    out = np.stack([cx + p[:, 0] * focal / z, cy + p[:, 1] * focal / z], axis=1)
    return out.astype(np.float32)


def warp_rgba(src: np.ndarray, quad: np.ndarray, W: int, H: int):
    """Warp do RGBA para a região que contém o quadrilátero. Retorna (rgba_roi, x0, y0) ou None."""
    x0, y0 = np.floor(quad.min(axis=0)).astype(int) - 2
    x1, y1 = np.ceil(quad.max(axis=0)).astype(int) + 2
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1c - x0c < 2 or y1c - y0c < 2:
        return None
    sh, sw = src.shape[:2]
    srcq = np.array([[0, 0], [sw, 0], [sw, sh], [0, sh]], np.float32)
    dst = quad - np.array([x0c, y0c], np.float32)
    M = cv2.getPerspectiveTransform(srcq, dst)
    roi = cv2.warpPerspective(src, M, (x1c - x0c, y1c - y0c), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return roi, x0c, y0c


def blend_roi(dst: np.ndarray, rgb: np.ndarray, a: np.ndarray, x: int, y: int) -> None:
    """Alpha blend uint8 (a em 0..1 float32)."""
    h, w = a.shape[:2]
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    sx, sy = x0 - x, y0 - y
    aa = a[sy:sy + y1 - y0, sx:sx + x1 - x0, None]
    roi = dst[y0:y1, x0:x1].astype(np.float32)
    src = rgb[sy:sy + y1 - y0, sx:sx + x1 - x0].astype(np.float32)
    dst[y0:y1, x0:x1] = (roi + (src - roi) * aa).astype(np.uint8)


def add_roi(dst: np.ndarray, rgb: np.ndarray, x: int, y: int) -> None:
    h, w = rgb.shape[:2]
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    sx, sy = x0 - x, y0 - y
    dst[y0:y1, x0:x1] = cv2.add(dst[y0:y1, x0:x1], rgb[sy:sy + y1 - y0, sx:sx + x1 - x0])


def draw_object(frame: np.ndarray, src: np.ndarray, quad: np.ndarray, accent: tuple[int, int, int],
                opacity: float = 1.0, floor_y: int | None = None, rim: float = 0.55, shadow: float = 0.55,
                sweep: float | None = None) -> None:
    """Desenha objeto RGBA em perspectiva com sombra projetada, reflexo, luz de contorno e faixa de brilho."""
    H, W = frame.shape[:2]
    r = warp_rgba(src, quad, W, H)
    if r is None:
        return
    roi, x0, y0 = r
    a = roi[..., 3].astype(np.float32) / 255 * opacity
    rgb = roi[..., :3]
    oh, ow = a.shape
    m = min(W, H)
    # sombra projetada (desfocada, deslocada para baixo)
    if shadow > 0:
        sh = cv2.GaussianBlur(a, (0, 0), max(4, m * 0.018)) * shadow
        blend_roi(frame, np.zeros_like(rgb), sh, x0 + int(m * 0.012), y0 + int(m * 0.03))
    # reflexo no chão
    if floor_y is not None:
        bottom = y0 + oh
        refl_h = int(oh * 0.32)
        if refl_h > 4 and bottom < H:
            fr = rgb[::-1][:refl_h]
            fa = a[::-1][:refl_h] * np.linspace(0.18, 0, refl_h, dtype=np.float32)[:, None]
            blend_roi(frame, fr, fa, x0, bottom + 2)
    # faixa de brilho
    if sweep is not None and 0 <= sweep <= 1:
        yy, xx = np.mgrid[0:oh, 0:ow].astype(np.float32)
        pos = (xx / ow + yy / oh * 0.5) - (sweep * 1.9 - 0.4)
        band = (np.exp(-(pos ** 2) / 0.008) * 110 * (a > 0.2)).astype(np.uint8)
        rgb = cv2.add(rgb, cv2.merge([band, band, band]))
    blend_roi(frame, rgb, a, x0, y0)
    # luz de contorno (rim light)
    if rim > 0:
        ai = (a * 255).astype(np.uint8)
        k = max(3, int(m * 0.004)) | 1
        edge = cv2.subtract(ai, cv2.erode(ai, np.ones((k, k), np.uint8)))
        edge = cv2.GaussianBlur(edge, (0, 0), k * 0.6).astype(np.float32) / 255 * rim
        glow = np.dstack([edge * accent[0], edge * accent[1], edge * accent[2]]).clip(0, 255).astype(np.uint8)
        add_roi(frame, glow, x0, y0)


# --------------------------------------------------------------------------------------------- pós

class Post:
    """Pós-processamento cinematográfico: bloom, vinheta, granulação e flash de transição."""

    def __init__(self, w: int, h: int, accent: tuple[int, int, int], bloom: float = 0.55, grain: bool = True):
        self.w, self.h = w, h
        self.bloom = bloom
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
        v = ((1 - np.clip(d - 0.55, 0, 1) * 0.55) * 255).astype(np.uint8)
        self.vig = cv2.merge([v, v, v])
        rng = np.random.default_rng(3)
        self.noise = [rng.integers(0, 7, (h, w, 1), dtype=np.uint8).repeat(3, axis=2) for _ in range(6)] if grain else []
        self.accent = accent

    def apply(self, frame: np.ndarray, i: int, flash: float = 0.0) -> np.ndarray:
        if self.bloom > 0:
            small = cv2.resize(frame, (self.w // 4, self.h // 4), interpolation=cv2.INTER_AREA)
            hi = cv2.subtract(small, (150, 150, 150, 0))
            hi = cv2.GaussianBlur(hi, (0, 0), max(2, self.w // 160))
            hi = cv2.resize(hi, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
            frame = cv2.addWeighted(frame, 1.0, hi, self.bloom, 0)
        if flash > 0.01:
            glow = np.full_like(frame, 0)
            glow[:] = tuple(int(min(255, c * 0.6 + 100) * flash) for c in self.accent)
            frame = cv2.add(frame, glow)
        frame = cv2.multiply(frame, self.vig, scale=1 / 255)
        if self.noise:
            n1 = self.noise[i % len(self.noise)]
            n2 = self.noise[(i + 3) % len(self.noise)]
            frame = cv2.subtract(cv2.add(frame, n1), n2)
        return frame
