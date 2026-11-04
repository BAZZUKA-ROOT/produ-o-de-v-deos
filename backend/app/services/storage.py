"""Armazenamento local de arquivos + validação/sanitização de uploads.

Uploads nunca são servidos como foram enviados: imagens são re-encodadas pelo Pillow
e áudios são transcodificados pelo FFmpeg. Isso elimina polyglots/payloads embutidos.
"""

import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Asset, AssetKind, AssetSource

Image.MAX_IMAGE_PIXELS = 60_000_000

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".flac", ".opus", ".webm"}
ALLOWED_AUDIO_FORMATS = {"mp3", "wav", "mov,mp4,m4a,3gp,3g2,mj2", "aac", "ogg", "flac", "matroska,webm"}
MAX_IMAGE_SIDE = 4096


class UploadError(ValueError):
    pass


@dataclass
class StoredFile:
    rel_path: str
    abs_path: Path
    mime: str
    size: int
    width: int | None = None
    height: int | None = None
    duration: float | None = None


def root() -> Path:
    return get_settings().storage_dir


def abs_path(rel: str) -> Path:
    p = (root() / rel).resolve()
    if root().resolve() not in p.parents:
        raise UploadError("caminho inválido")
    return p


def new_rel_path(owner_id: uuid.UUID | None, ext: str, folder: str = "assets") -> str:
    owner = str(owner_id) if owner_id else "system"
    name = f"{uuid.uuid4().hex}{ext}"
    return f"{folder}/{owner}/{name[:2]}/{name}"


def _prepare(rel: str) -> Path:
    p = abs_path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        timeout=60,
    )
    if out.returncode != 0:
        raise UploadError("arquivo de mídia inválido ou corrompido")
    return json.loads(out.stdout or b"{}")


def media_duration(path: Path) -> float:
    info = ffprobe(path)
    return float(info.get("format", {}).get("duration") or 0.0)


def store_image_upload(tmp: Path, owner_id: uuid.UUID | None, original_name: str) -> StoredFile:
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise UploadError("formato de imagem não permitido (use JPG, PNG ou WEBP)")
    try:
        with Image.open(tmp) as probe:
            if probe.format not in ALLOWED_IMAGE_FORMATS:
                raise UploadError("conteúdo do arquivo não é uma imagem válida")
            probe.verify()
        with Image.open(tmp) as img:
            img = ImageOps.exif_transpose(img)
            img.load()
            has_alpha = img.mode in ("RGBA", "LA", "P") and (
                img.mode != "P" or "transparency" in img.info
            )
            img = img.convert("RGBA" if has_alpha else "RGB")
            img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
            out_ext, fmt, mime = (".png", "PNG", "image/png") if has_alpha else (".jpg", "JPEG", "image/jpeg")
            rel = new_rel_path(owner_id, out_ext)
            dest = _prepare(rel)
            # Re-encode sem metadados (EXIF/ICC removidos).
            save_kwargs = {"optimize": True} if fmt == "PNG" else {"quality": 92, "optimize": True}
            img.save(dest, fmt, **save_kwargs)
            w, h = img.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise UploadError(f"imagem inválida: {exc.__class__.__name__}") from exc
    os.chmod(dest, 0o640)
    return StoredFile(rel, dest, mime, dest.stat().st_size, w, h)


def store_audio_upload(tmp: Path, owner_id: uuid.UUID | None, original_name: str) -> StoredFile:
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXT:
        raise UploadError("formato de áudio não permitido (MP3, WAV, M4A, AAC, OGG, FLAC, OPUS)")
    info = ffprobe(tmp)
    fmt = info.get("format", {}).get("format_name", "")
    if fmt not in ALLOWED_AUDIO_FORMATS and not any(f in fmt.split(",") for f in ("mp3", "wav", "ogg", "flac", "aac")):
        raise UploadError("conteúdo do arquivo não é um áudio suportado")
    if not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        raise UploadError("o arquivo não contém trilha de áudio")
    duration = float(info.get("format", {}).get("duration") or 0)
    if duration <= 0 or duration > 1800:
        raise UploadError("duração de áudio inválida (máx. 30 minutos)")
    rel = new_rel_path(owner_id, ".m4a")
    dest = _prepare(rel)
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(tmp), "-vn", "-map_metadata", "-1", "-ac", "2", "-ar", "48000",
         "-c:a", "aac", "-b:a", "192k", str(dest)],
        capture_output=True,
        timeout=600,
    )
    if proc.returncode != 0:
        dest.unlink(missing_ok=True)
        raise UploadError("falha ao processar áudio")
    os.chmod(dest, 0o640)
    return StoredFile(rel, dest, "audio/mp4", dest.stat().st_size, duration=media_duration(dest))


def store_generated(src: Path, owner_id: uuid.UUID | None, ext: str, mime: str, move: bool = True) -> StoredFile:
    rel = new_rel_path(owner_id, ext)
    dest = _prepare(rel)
    (shutil.move if move else shutil.copyfile)(str(src), str(dest))
    os.chmod(dest, 0o640)
    sf = StoredFile(rel, dest, mime, dest.stat().st_size)
    if mime.startswith("image/"):
        with Image.open(dest) as im:
            sf.width, sf.height = im.size
    elif mime.startswith(("audio/", "video/")):
        sf.duration = media_duration(dest)
        if mime.startswith("video/"):
            v = next((s for s in ffprobe(dest)["streams"] if s.get("codec_type") == "video"), {})
            sf.width, sf.height = v.get("width"), v.get("height")
    return sf


def create_asset(
    db: Session,
    stored: StoredFile,
    *,
    owner_id: uuid.UUID | None,
    kind: AssetKind,
    source: AssetSource,
    name: str,
    project_id: uuid.UUID | None = None,
    in_library: bool = True,
    meta: dict | None = None,
) -> Asset:
    asset = Asset(
        owner_id=owner_id,
        project_id=project_id,
        kind=kind,
        source=source,
        name=name[:255],
        storage_path=stored.rel_path,
        mime=stored.mime,
        size_bytes=stored.size,
        width=stored.width,
        height=stored.height,
        duration=stored.duration,
        in_library=in_library,
        meta=meta or {},
    )
    db.add(asset)
    db.flush()
    return asset


def delete_asset_file(asset: Asset) -> None:
    try:
        abs_path(asset.storage_path).unlink(missing_ok=True)
    except UploadError:
        pass


def user_usage_bytes(db: Session, owner_id: uuid.UUID) -> int:
    return int(db.query(func.coalesce(func.sum(Asset.size_bytes), 0)).filter(Asset.owner_id == owner_id).scalar())


def dir_size(path: Path) -> int:
    total = 0
    if path.exists():
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total
