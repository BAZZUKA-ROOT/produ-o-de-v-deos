"""Trilhas sonoras procedurais (síntese própria, livres de direitos autorais).

Modelos generativos de música open source com pesos liberados para uso comercial ainda são raros
(ex.: MusicGen tem pesos CC-BY-NC), por isso a plataforma sintetiza loops originais e aceita upload.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100

MOODS = {
    #           bpm  key  minor  progression (graus)            drums  arp
    "upbeat":    (112, 0,  False, [0, 7, 9, 5],                 "pop",  True),
    "corporate": (100, 2,  False, [0, 9, 5, 7],                 "soft", True),
    "elegant":   (72,  5,  False, [2, 7, 0, 9],                 "none", True),
    "tech":      (120, 9,  True,  [0, 8, 3, 10],                "four", True),
    "chill":     (84,  4,  False, [0, 5, 9, 5],                 "soft", False),
    "energetic": (128, 7,  True,  [0, 8, 10, 0],                "four", True),
}


def _midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def _chord(root: int, minor_key: bool, degree: int) -> list[int]:
    major_scale = [0, 2, 4, 5, 7, 9, 11]
    minor_scale = [0, 2, 3, 5, 7, 8, 10]
    scale = minor_scale if minor_key else major_scale
    # aproxima o grau ao índice da escala para montar tríade + sétima diatônicas
    idx = min(range(7), key=lambda i: abs(scale[i] - degree))
    notes = [scale[(idx + k) % 7] + 12 * ((idx + k) // 7) for k in (0, 2, 4, 6)]
    return [root + n for n in notes]


def _env(n: int, a: float, r: float) -> np.ndarray:
    t = np.arange(n) / SR
    env = np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
    return env.astype(np.float32)


def _smooth(x: np.ndarray, k: int) -> np.ndarray:
    kernel = np.ones(k, np.float32) / k
    return np.convolve(x, kernel, mode="same").astype(np.float32)


def generate(mood: str, out: Path, seconds: float = 64.0, seed: int = 7) -> Path:
    bpm, key, minor, prog, drums, arp = MOODS.get(mood, MOODS["corporate"])
    rng = np.random.default_rng(seed + hash(mood) % 1000)
    beat = 60.0 / bpm
    bar = beat * 4
    n = int(seconds * SR)
    L = np.zeros(n, np.float32)
    R = np.zeros(n, np.float32)
    root = 48 + key
    t_all = np.arange(int(bar * SR)) / SR

    def add(sig: np.ndarray, start: float, pan: float = 0.0, gain: float = 1.0):
        s = int(start * SR)
        if s >= n:
            return
        e = min(n, s + len(sig))
        seg = sig[: e - s] * gain
        L[s:e] += seg * (1 - max(pan, 0))
        R[s:e] += seg * (1 + min(pan, 0))

    bars = int(seconds / bar) + 1
    for b in range(bars):
        start = b * bar
        chord = _chord(root, minor, prog[b % len(prog)])
        # pad: saws desafinadas suavizadas
        pad = np.zeros_like(t_all, dtype=np.float32)
        for note in chord:
            for det in (-0.08, 0.08):
                f = _midi(note + 12 + det)
                ph = (t_all * f) % 1.0
                pad += (2 * ph - 1).astype(np.float32)
        pad = _smooth(pad, 24) * 0.035
        fade = np.minimum(1, np.minimum(t_all / 0.25, (bar - t_all) / 0.25)).astype(np.float32)
        add(pad * fade, start, pan=0.0)
        # baixo
        for k in range(4 if drums != "none" else 2):
            ln = beat if drums != "none" else beat * 2
            tt = np.arange(int(ln * SR)) / SR
            f = _midi(chord[0] - 12)
            bass = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)).astype(np.float32)
            add(np.tanh(bass * 1.5) * _env(len(tt), 0.01, ln * 0.7) * 0.22, start + k * ln)
        # arpejo (pluck)
        if arp:
            steps = 8
            pattern = [0, 1, 2, 3, 2, 1, 2, 3]
            for k in range(steps):
                note = chord[pattern[k] % len(chord)] + 24
                ln = bar / steps
                tt = np.arange(int(ln * SR * 1.6)) / SR
                f = _midi(note)
                tone = (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(4 * np.pi * f * tt) + 0.15 * np.sin(6 * np.pi * f * tt))
                sig = tone.astype(np.float32) * _env(len(tt), 0.003, 0.18)
                add(sig * 0.07, start + k * ln, pan=0.35 if k % 2 else -0.35)
        # bateria
        if drums != "none":
            for k in range(8):
                pos = start + k * beat / 2
                if drums == "four" and k % 2 == 0 or drums in ("pop", "soft") and k in (0, 3, 4):
                    tt = np.arange(int(0.35 * SR)) / SR
                    freq = 50 + 90 * np.exp(-tt * 30)
                    kick = np.sin(2 * np.pi * np.cumsum(freq) / SR).astype(np.float32) * _env(len(tt), 0.001, 0.12)
                    add(kick * (0.5 if drums != "soft" else 0.3), pos)
                if k in (2, 6) and drums != "soft":
                    tt = int(0.2 * SR)
                    noise = rng.normal(0, 1, tt).astype(np.float32)
                    sn = (noise - _smooth(noise, 6)) * _env(tt, 0.001, 0.06)
                    add(sn * 0.16, pos)
                hh = int(0.06 * SR)
                noise = rng.normal(0, 1, hh).astype(np.float32)
                hat = (noise - _smooth(noise, 3)) * _env(hh, 0.0005, 0.015)
                add(hat * (0.06 if drums == "soft" else 0.09), pos, pan=0.2)

    mix = np.stack([L, R], axis=1)
    fade_in = int(1.0 * SR)
    mix[:fade_in] *= np.linspace(0, 1, fade_in, dtype=np.float32)[:, None]
    peak = float(np.abs(mix).max()) or 1.0
    mix = np.tanh(mix / peak * 1.2) * 0.8
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), mix, SR)
    return out
