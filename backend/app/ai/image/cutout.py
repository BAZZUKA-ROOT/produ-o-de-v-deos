"""Remoção de fundo (recorte do produto) com IS-Net/DIS (Apache-2.0) via ONNX Runtime em CPU.

Modelo: isnet-general-use.onnx (mesmo arquivo distribuído pelo projeto rembg, MIT).
"""

import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.core.config import get_settings

_lock = threading.Lock()
_session = None
SIZE = 1024
MODEL_REL = "rembg/isnet-general-use.onnx"


class CutoutError(RuntimeError):
    pass


@dataclass
class CutoutResult:
    path: Path
    coverage: float
    confidence: float
    usable: bool
    bbox: tuple[int, int, int, int]


def model_path() -> Path:
    return get_settings().models_dir / MODEL_REL


def available() -> bool:
    return model_path().exists()


def _sess():
    global _session
    if _session is None:
        import onnxruntime as ort

        if not available():
            raise CutoutError("modelo de recorte ausente (execute scripts/download-models.sh)")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        _session = ort.InferenceSession(str(model_path()), opts, providers=["CPUExecutionProvider"])
    return _session


def _mask(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    x = cv2.resize(rgb, (SIZE, SIZE), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    x = (x - 0.5) / 1.0
    x = x.transpose(2, 0, 1)[None]
    with _lock:
        sess = _sess()
        out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0][0]
    out = (out - out.min()) / max(float(out.max() - out.min()), 1e-6)
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)


def remove_background(src: Path, out: Path) -> CutoutResult:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        rgb = np.asarray(im)
    m = _mask(rgb)
    alpha = np.clip((m - 0.15) / 0.7, 0, 1)
    # remove ilhas pequenas: mantém o maior componente e os que tenham >= 8% dele
    binm = (alpha > 0.5).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binm, 8)
    if n > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = np.zeros(n, bool)
        keep[1:] = areas >= areas.max() * 0.08
        alpha = alpha * cv2.dilate(keep[labels].astype(np.uint8), np.ones((9, 9), np.uint8))
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (3, 3), 0)
    alpha = np.clip((alpha - 0.12) / 0.88, 0, 1)
    # descontaminação de borda: substitui a cor dos pixels semitransparentes pela cor interna próxima
    solid = (alpha > 0.97).astype(np.float32)
    k = max(3, int(max(rgb.shape[:2]) * 0.004)) | 1
    num = cv2.GaussianBlur(rgb.astype(np.float32) * solid[..., None], (0, 0), k)
    den = cv2.GaussianBlur(solid, (0, 0), k)[..., None]
    fill = np.where(den > 1e-3, num / np.maximum(den, 1e-3), rgb.astype(np.float32))
    edge = ((alpha > 0.01) & (alpha < 0.97))[..., None]
    rgb = np.where(edge, fill, rgb.astype(np.float32)).clip(0, 255).astype(np.uint8)
    coverage = float((alpha > 0.5).mean())
    confidence = float(np.mean(np.abs(m - 0.5)) * 2)
    ys, xs = np.where(alpha > 0.5)
    if ys.size == 0:
        raise CutoutError("nenhum objeto detectado")
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    h, w = alpha.shape
    pad = int(max(w, h) * 0.02)
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
    rgba = np.dstack([rgb, (alpha * 255).astype(np.uint8)])[y0:y1, x0:x1]
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(out, "PNG", optimize=True)
    # Produto "recortável": ocupa parte da foto, não encosta em muitas bordas, máscara nítida.
    touches = sum([x0 <= pad, y0 <= pad, x1 >= w - pad, y1 >= h - pad])
    usable = 0.03 < coverage < 0.8 and confidence > 0.75 and touches <= 2
    return CutoutResult(out, coverage, confidence, usable, (x0, y0, x1, y1))
