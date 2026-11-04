"""Efeitos sonoros sintetizados (originais, sem direitos autorais): whoosh, impacto e brilho."""

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return (np.minimum(1, t / attack) * np.exp(-np.maximum(t - attack, 0) / decay)).astype(np.float32)


def _onepole_lp(x: np.ndarray, cutoff: np.ndarray) -> np.ndarray:
    """Passa-baixa de 1 polo com corte variável no tempo (vetorizado em blocos curtos)."""
    y = np.empty_like(x)
    acc = 0.0
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def whoosh(dur: float = 0.65, seed: int = 0) -> np.ndarray:
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, n).astype(np.float32)
    t = np.linspace(0, 1, n, dtype=np.float32)
    sweep = 300 + 5200 * np.sin(np.pi * t) ** 2
    y = _onepole_lp(noise, sweep)
    y = y - _onepole_lp(y, np.full(n, 180.0, np.float32))
    env = np.abs(np.sin(np.pi * t)) ** 1.6
    out = y * env
    pan = np.linspace(-0.7, 0.7, n, dtype=np.float32)
    return np.stack([out * (1 - pan) / 2, out * (1 + pan) / 2], 1) / (np.abs(out).max() + 1e-6) * 0.9


def hit(dur: float = 1.1) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = 45 + 70 * np.exp(-t * 18)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * _env(n, 0.003, 0.32)
    rng = np.random.default_rng(1)
    click = _onepole_lp(rng.normal(0, 1, n).astype(np.float32), np.full(n, 2500.0, np.float32)) * _env(n, 0.001, 0.03)
    out = np.tanh((body * 1.4 + click * 0.5) * 1.2).astype(np.float32)
    return np.stack([out, out], 1) * 0.85


def shimmer(dur: float = 0.9) -> np.ndarray:
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    for k, f in enumerate([1568, 2093, 2637, 3136, 4186]):
        st = int(k * 0.055 * SR)
        m = n - st
        t = np.arange(m) / SR
        out[st:] += (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * _env(m, 0.002, 0.22) * 0.22
    left = out
    right = np.roll(out, int(0.012 * SR))
    return np.stack([left, right], 1)


def build_track(events: list[tuple[float, str]], total: float, out: Path, gain: float = 0.5) -> Path:
    n = int((total + 1.5) * SR)
    track = np.zeros((n, 2), np.float32)
    cache: dict[str, np.ndarray] = {}
    for i, (t, kind) in enumerate(sorted(events)):
        key = f"{kind}{i % 3 if kind == 'whoosh' else ''}"
        if key not in cache:
            cache[key] = {"whoosh": lambda: whoosh(seed=i % 3), "hit": hit, "shimmer": shimmer}[kind]()
        snd = cache[key]
        s = max(0, int(t * SR))
        e = min(n, s + len(snd))
        if e > s:
            track[s:e] += snd[: e - s]
    track = np.tanh(track * gain).astype(np.float32)
    sf.write(str(out), track[: int(total * SR)], SR)
    return out
