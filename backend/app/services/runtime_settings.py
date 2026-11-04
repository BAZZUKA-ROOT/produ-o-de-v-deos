"""Configurações editáveis pelo painel admin (persistidas no banco, com defaults do .env)."""

import time
from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SystemSetting


def defaults() -> dict[str, dict[str, Any]]:
    s = get_settings()
    return {
        "ai": {
            "llm_provider": s.llm_provider,  # ollama | template
            "ollama_url": s.ollama_url,
            "ollama_model": s.ollama_model,
            "llm_temperature": 0.7,
            "llm_timeout_seconds": s.llm_timeout_seconds,
            "image_provider": s.image_provider,  # comfyui | procedural
            "comfyui_url": s.comfyui_url,
            "comfyui_checkpoint": s.comfyui_checkpoint,
            "comfyui_steps": 25,
            "comfyui_cfg": 6.5,
            "comfyui_sampler": "dpmpp_2m",
            "comfyui_scheduler": "karras",
            "comfyui_base_resolution": 1024,
            "comfyui_lora": "",
            "comfyui_lora_strength": 1.0,
            "comfyui_timeout_seconds": s.comfyui_timeout_seconds,
            "negative_prompt": "text, watermark, logo, letters, blurry, low quality, deformed, ugly, extra fingers",
            "tts_provider": s.tts_provider,  # kokoro | piper | espeak
            "kokoro_model_file": s.kokoro_model_file,
            "kokoro_voices_file": s.kokoro_voices_file,
            "piper_voice_male": s.piper_voice_male,
        },
        "storage": {
            "max_image_upload_mb": s.max_image_upload_mb,
            "max_audio_upload_mb": s.max_audio_upload_mb,
            "user_quota_mb": s.user_quota_mb,
            "temp_retention_hours": 24,
        },
        "render": {
            "default_quality": "1080p",
            "preview_quality": "360p",
            "x264_preset": "medium",
            "crf": 20,
            "fps": 30,
            "max_retries": s.render_max_retries,
        },
        "general": {
            "allow_registration": s.allow_registration,
        },
    }


_cache: dict[str, Any] = {"ts": 0.0, "data": None}
_TTL = 5.0


def get_all(db: Session, use_cache: bool = True) -> dict[str, dict[str, Any]]:
    if use_cache and _cache["data"] is not None and time.time() - _cache["ts"] < _TTL:
        return deepcopy(_cache["data"])
    data = defaults()
    for row in db.query(SystemSetting).all():
        if row.key in data and isinstance(row.value, dict):
            data[row.key].update({k: v for k, v in row.value.items() if k in data[row.key]})
    _cache.update(ts=time.time(), data=deepcopy(data))
    return data


def get_section(db: Session, section: str) -> dict[str, Any]:
    return get_all(db)[section]


def update_section(db: Session, section: str, values: dict[str, Any]) -> dict[str, Any]:
    base = defaults()
    if section not in base:
        raise KeyError(section)
    allowed = base[section]
    clean: dict[str, Any] = {}
    for k, v in values.items():
        if k not in allowed:
            continue
        default = allowed[k]
        if isinstance(default, bool):
            clean[k] = bool(v)
        elif isinstance(default, int) and not isinstance(default, bool):
            clean[k] = int(v)
        elif isinstance(default, float):
            clean[k] = float(v)
        else:
            clean[k] = str(v)
    row = db.get(SystemSetting, section)
    if row is None:
        row = SystemSetting(key=section, value={})
        db.add(row)
    row.value = {**(row.value or {}), **clean}
    db.commit()
    invalidate()
    return get_all(db, use_cache=False)[section]


def invalidate() -> None:
    _cache.update(ts=0.0, data=None)
