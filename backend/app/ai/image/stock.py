"""Banco de fotos gratuito (Pexels): fotos reais com licença livre para uso comercial, sem atribuição obrigatória.

Requer chave gratuita (https://www.pexels.com/api/). Útil em servidores sem GPU.
"""

import hashlib
import re
from pathlib import Path

import httpx

STOP = {"a", "an", "the", "of", "with", "and", "in", "on", "for", "at", "to", "high", "quality", "detailed",
        "professional", "photo", "photography", "commercial", "cinematic", "light", "lighting", "shallow", "depth",
        "field", "realistic", "4k", "8k", "warm", "tones", "dramatic"}


class StockError(RuntimeError):
    pass


def keywords(prompt: str, limit: int = 4) -> str:
    first = prompt.split(",")[0]
    words = [w for w in re.findall(r"[a-zA-Z]+", first.lower()) if w not in STOP and len(w) > 2]
    if len(words) < 2:
        words += [w for w in re.findall(r"[a-zA-Z]+", prompt.lower()) if w not in STOP and len(w) > 2 and w not in words]
    return " ".join(words[:limit])


def generate(prompt: str, out_path: Path, api_key: str, width: int, height: int, seed_text: str = "") -> Path:
    if not api_key:
        raise StockError("chave do Pexels não configurada")
    orientation = "portrait" if height > width * 1.1 else "landscape" if width > height * 1.1 else "square"
    query = keywords(prompt) or "business"
    try:
        with httpx.Client(timeout=20, headers={"Authorization": api_key}) as c:
            r = c.get("https://api.pexels.com/v1/search", params={"query": query, "orientation": orientation, "per_page": 15})
            if r.status_code == 401:
                raise StockError("chave do Pexels inválida")
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos and " " in query:
                r = c.get("https://api.pexels.com/v1/search", params={"query": query.split()[0], "orientation": orientation, "per_page": 15})
                photos = r.json().get("photos", [])
            if not photos:
                raise StockError(f"nenhuma foto para '{query}'")
            idx = int(hashlib.sha256((seed_text or prompt).encode()).hexdigest()[:6], 16) % min(len(photos), 8)
            src = photos[idx]["src"].get("large2x") or photos[idx]["src"]["original"]
            img = c.get(src, timeout=60)
            img.raise_for_status()
    except httpx.HTTPError as exc:
        raise StockError(f"Pexels indisponível: {exc}") from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img.content)
    return out_path
