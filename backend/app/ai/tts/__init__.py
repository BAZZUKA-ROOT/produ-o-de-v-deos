"""Síntese de voz em pt-BR: Kokoro (Apache-2.0), Piper (pt_BR faber) e eSpeak NG como fallback universal."""

import logging
import re
import shutil
import subprocess
import threading
import wave
from pathlib import Path

import numpy as np
import soundfile as sf

from app.core.catalog import VOICES
from app.core.config import get_settings

log = logging.getLogger(__name__)
_lock = threading.Lock()
_kokoro = None
_piper: dict[str, object] = {}


class TTSError(RuntimeError):
    pass


def _model_path(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else get_settings().models_dir / p


def _money(m: re.Match) -> str:
    reais, cents = m.group(1).replace(".", ""), m.group(2)
    s = f"{int(reais)} reais" if reais else ""
    if cents and int(cents):
        s += f" e {int(cents)} centavos"
    return s


def normalize_text(text: str) -> str:
    t = text.replace("\n", " ")
    t = re.sub(r"R\$\s?(\d[\d.]*)(?:,(\d{2}))?", _money, t)
    t = re.sub(r"(\d+)\s?%", r"\1 por cento", t)
    t = re.sub(r"@(\w[\w.]*)", lambda m: "arroba " + m.group(1).replace(".", " ponto ").replace("_", " "), t)
    t = re.sub(r"\(?\b(\d{2})\)?\s?(9?\d{4})[-\s]?(\d{4})\b",
               lambda m: " ".join(m.group(1)) + ", " + " ".join(m.group(2)) + ", " + " ".join(m.group(3)), t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[#*_~`|<>]", " ", t)
    t = re.sub(r"[\U0001F000-\U0001FFFF☀-➿]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _kokoro_engine(ai_cfg: dict):
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro

        model = _model_path(ai_cfg["kokoro_model_file"])
        voices = _model_path(ai_cfg["kokoro_voices_file"])
        if not model.exists() or not voices.exists():
            raise TTSError(f"modelo Kokoro não encontrado em {model.parent} (execute scripts/download-models.sh)")
        _kokoro = Kokoro(str(model), str(voices))
    return _kokoro


def _synth_kokoro(text: str, out: Path, gender: str, speed: float, ai_cfg: dict) -> None:
    voice = VOICES["kokoro"].get(gender, VOICES["kokoro"]["female"])
    with _lock:
        engine = _kokoro_engine(ai_cfg)
        samples, sr = engine.create(text, voice=voice, speed=float(np.clip(speed, 0.5, 2.0)), lang="pt-br")
    sf.write(str(out), samples, sr)


def _synth_piper(text: str, out: Path, gender: str, speed: float, ai_cfg: dict) -> None:
    if gender != "male":
        raise TTSError("Piper pt_BR possui apenas vozes masculinas")
    from piper import PiperVoice, SynthesisConfig

    path = _model_path(ai_cfg["piper_voice_male"])
    if not path.exists():
        raise TTSError(f"voz Piper não encontrada: {path}")
    with _lock:
        voice = _piper.get(str(path))
        if voice is None:
            voice = PiperVoice.load(str(path))
            _piper[str(path)] = voice
        with wave.open(str(out), "wb") as w:
            voice.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=1.0 / max(speed, 0.3)))


def _synth_espeak(text: str, out: Path, gender: str, speed: float, ai_cfg: dict) -> None:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise TTSError("espeak-ng não instalado")
    voice = VOICES["espeak"].get(gender, VOICES["espeak"]["female"])
    wpm = int(165 * speed)
    r = subprocess.run([exe, "-v", voice, "-s", str(wpm), "-w", str(out), text], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise TTSError(r.stderr.decode(errors="ignore")[:200])


PROVIDERS = {"kokoro": _synth_kokoro, "piper": _synth_piper, "espeak": _synth_espeak}


def _trim_and_pad(path: Path) -> float:
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = np.abs(data).max(axis=1)
    idx = np.where(mono > 0.01)[0]
    if idx.size:
        start = max(int(idx[0]) - int(0.03 * sr), 0)
        end = min(int(idx[-1]) + int(0.12 * sr), len(data))
        data = data[start:end]
    sf.write(str(path), data, sr)
    return len(data) / sr


def synthesize(text: str, out: Path, gender: str = "female", speed: float = 1.0, provider: str | None = None,
               ai_cfg: dict | None = None) -> tuple[float, str, list[str]]:
    """Gera WAV. Retorna (duração, provedor usado, avisos)."""
    ai_cfg = ai_cfg or {}
    text = normalize_text(text)
    if not text:
        raise TTSError("texto vazio")
    order = [provider or ai_cfg.get("tts_provider") or "kokoro", "kokoro", "piper", "espeak"]
    tried: list[str] = []
    warnings: list[str] = []
    for name in dict.fromkeys(order):
        fn = PROVIDERS.get(name)
        if not fn:
            continue
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            fn(text, out, gender, speed, ai_cfg)
            if tried:
                warnings.append(f"TTS '{tried[0]}' indisponível; usado '{name}'.")
            return _trim_and_pad(out), name, warnings
        except Exception as exc:  # noqa: BLE001 - qualquer falha de provedor aciona o próximo
            log.warning("TTS %s falhou: %s", name, exc)
            tried.append(name)
            warnings.append(f"{name}: {exc}")
    raise TTSError("nenhum provedor de TTS disponível: " + "; ".join(warnings))


def status(ai_cfg: dict) -> dict:
    return {
        "kokoro": _model_path(ai_cfg["kokoro_model_file"]).exists() and _model_path(ai_cfg["kokoro_voices_file"]).exists(),
        "piper": _model_path(ai_cfg["piper_voice_male"]).exists(),
        "espeak": bool(shutil.which("espeak-ng") or shutil.which("espeak")),
    }
