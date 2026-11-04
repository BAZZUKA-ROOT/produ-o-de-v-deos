"""Movimento de câmera (Ken Burns) com interpolação subpixel via OpenCV, codificado por FFmpeg."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from app.video.frames import MOTION_MARGIN


class Cancelled(Exception):
    pass


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def _window(motion: str, p: float, k: float) -> tuple[float, float, float]:
    """Retorna (zoom relativo z>=1, cx, cy) normalizados (0..1) para o progresso p."""
    e = _ease(p)
    zmax = k
    if motion == "zoom_in":
        return 1 + (zmax - 1) * 0.85 * e, 0.5, 0.5
    if motion == "zoom_out":
        return 1 + (zmax - 1) * 0.85 * (1 - e), 0.5, 0.5
    if motion == "zoom_in_left":
        return 1 + (zmax - 1) * 0.85 * e, 0.5 - 0.06 * e, 0.5
    if motion == "zoom_in_right":
        return 1 + (zmax - 1) * 0.85 * e, 0.5 + 0.06 * e, 0.5
    z = 1 + (zmax - 1) * 0.6
    span = (1 - 1 / z) / 2 * 0.9
    if motion == "pan_left":
        return z, 0.5 + span - 2 * span * e, 0.5
    if motion == "pan_right":
        return z, 0.5 - span + 2 * span * e, 0.5
    if motion == "pan_up":
        return z, 0.5, 0.5 + span - 2 * span * e
    if motion == "pan_down":
        return z, 0.5, 0.5 - span + 2 * span * e
    return 1.0, 0.5, 0.5


def render_clip(source: np.ndarray, out: Path, w: int, h: int, duration: float, fps: int, motion: str,
                preset: str = "veryfast", crf: int = 16,
                on_frame: Callable[[int, int], None] | None = None,
                should_cancel: Callable[[], bool] | None = None) -> Path:
    frames = max(1, int(round(duration * fps)))
    sh, sw = source.shape[:2]
    k = sw / w if motion != "none" else 1.0
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    static = None
    if motion == "none":
        static = cv2.resize(source, (w, h), interpolation=cv2.INTER_AREA).tobytes()
    try:
        for i in range(frames):
            if should_cancel and i % 15 == 0 and should_cancel():
                raise Cancelled()
            if static is not None:
                buf = static
            else:
                z, cx, cy = _window(motion, i / max(frames - 1, 1), min(k, MOTION_MARGIN))
                ws, hs = sw / z, sh / z
                x0 = np.clip(cx * sw - ws / 2, 0, sw - ws)
                y0 = np.clip(cy * sh - hs / 2, 0, sh - hs)
                a = ws / w
                m = np.array([[a, 0, x0], [0, a, y0]], np.float32)
                frame = cv2.warpAffine(source, m, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                                       borderMode=cv2.BORDER_REFLECT)
                buf = frame.tobytes()
            proc.stdin.write(buf)
            if on_frame and i % 10 == 0:
                on_frame(i, frames)
        proc.stdin.close()
        rc = proc.wait(timeout=600)
        if rc != 0:
            raise RuntimeError("FFmpeg falhou ao codificar cena: " + proc.stderr.read().decode(errors="ignore")[-500:])
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    return out
