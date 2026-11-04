import mimetypes
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_asset, get_current_user
from app.api.serializers import asset_out
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import verify_media
from app.models import Asset, AssetKind, AssetSource, Project, Scene, User
from app.schemas import AssetUpdateIn
from app.services import runtime_settings, storage

router = APIRouter(tags=["assets"])

UPLOAD_KINDS = {"image": AssetKind.image, "logo": AssetKind.logo, "music": AssetKind.music, "audio": AssetKind.audio}


def copy_upload_limited(upload: UploadFile, dest: Path, max_bytes: int) -> int:
    size = 0
    with dest.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(413, f"arquivo excede o limite de {max_bytes // (1024 * 1024)} MB")
            out.write(chunk)
    if size == 0:
        raise HTTPException(422, "arquivo vazio")
    return size


@router.get("/assets")
def list_assets(kind: str | None = None, q: str | None = None, include_system: bool = True,
                project_id: uuid.UUID | None = None, page: int = Query(1, ge=1),
                page_size: int = Query(60, ge=1, le=200),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cond = Asset.owner_id == user.id
    if include_system:
        cond = or_(cond, Asset.owner_id.is_(None))
    query = db.query(Asset).filter(cond)
    if project_id:
        query = query.filter(Asset.project_id == project_id)
    else:
        query = query.filter(Asset.in_library.is_(True))
    if kind:
        kinds = [k for k in kind.split(",") if k in AssetKind._value2member_map_]
        query = query.filter(Asset.kind.in_([AssetKind(k) for k in kinds]))
    if q:
        query = query.filter(Asset.name.ilike(f"%{q.strip()[:100]}%"))
    total = query.count()
    items = query.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    usage = storage.user_usage_bytes(db, user.id)
    quota = (user.quota_mb if user.quota_mb is not None else runtime_settings.get_section(db, "storage")["user_quota_mb"])
    return {"items": [asset_out(a) for a in items], "total": total, "usage_bytes": usage,
            "quota_bytes": quota * 1024 * 1024}


@router.post("/assets", status_code=201)
def upload_asset(file: UploadFile = File(...), kind: str = Form("image"), project_id: uuid.UUID | None = Form(None),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if kind not in UPLOAD_KINDS:
        raise HTTPException(422, "tipo de arquivo inválido")
    akind = UPLOAD_KINDS[kind]
    if project_id:
        p = db.get(Project, project_id)
        if p is None or p.owner_id != user.id:
            raise HTTPException(404, "Projeto não encontrado")
    cfg = runtime_settings.get_section(db, "storage")
    is_image = akind in (AssetKind.image, AssetKind.logo)
    max_mb = cfg["max_image_upload_mb"] if is_image else cfg["max_audio_upload_mb"]
    quota_mb = user.quota_mb if user.quota_mb is not None else cfg["user_quota_mb"]
    if storage.user_usage_bytes(db, user.id) >= quota_mb * 1024 * 1024:
        raise HTTPException(413, "cota de armazenamento esgotada")
    original = Path(file.filename or "arquivo").name[:200]
    tmpdir = Path(tempfile.mkdtemp(prefix="up_", dir=get_settings().temp_dir))
    try:
        tmp = tmpdir / f"upload{Path(original).suffix.lower()}"
        copy_upload_limited(file, tmp, max_mb * 1024 * 1024)
        try:
            stored = (storage.store_image_upload if is_image else storage.store_audio_upload)(tmp, user.id, original)
        except storage.UploadError as exc:
            raise HTTPException(422, str(exc)) from None
        asset = storage.create_asset(db, stored, owner_id=user.id, project_id=project_id, kind=akind,
                                     source=AssetSource.upload, name=Path(original).stem or "arquivo",
                                     in_library=akind != AssetKind.audio or project_id is None)
        db.commit()
        return asset_out(asset)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.patch("/assets/{asset_id}")
def update_asset(asset_id: uuid.UUID, data: AssetUpdateIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    a = get_accessible_asset(db, asset_id, user, allow_system=False)
    if data.name is not None:
        a.name = data.name
    if data.in_library is not None:
        a.in_library = data.in_library
    db.commit()
    return asset_out(a)


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(asset_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_accessible_asset(db, asset_id, user, allow_system=False)
    in_use = db.query(Scene.id).filter(or_(Scene.image_asset_id == a.id, Scene.narration_asset_id == a.id)).first()
    used_as_output = db.query(Project.id).filter(
        or_(Project.output_asset_id == a.id, Project.preview_asset_id == a.id)).first()
    if in_use or used_as_output:
        raise HTTPException(409, "arquivo em uso por um projeto; remova-o das cenas antes de excluir")
    sid = str(a.id)
    for p in db.query(Project).filter(Project.owner_id == a.owner_id).all():
        s = p.settings or {}
        if sid in (s.get("music_asset_id"), s.get("logo_asset_id"), s.get("narration_asset_id"),
                   (s.get("watermark") or {}).get("asset_id")):
            raise HTTPException(409, f"arquivo em uso pelo projeto '{p.name}'")
    storage.delete_asset_file(a)
    db.delete(a)
    db.commit()


@router.get("/media/{asset_id}", include_in_schema=False)
def media(asset_id: uuid.UUID, exp: int, sig: str, dl: int = 0, db: Session = Depends(get_db)):
    if not verify_media(str(asset_id), exp, dl, sig):
        raise HTTPException(403, "link expirado ou inválido")
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(404, "arquivo não encontrado")
    path = storage.abs_path(a.storage_path)
    if not path.exists():
        raise HTTPException(404, "arquivo não encontrado")
    ext = path.suffix or mimetypes.guess_extension(a.mime) or ""
    filename = "".join(c for c in a.name if c.isalnum() or c in " -_.")[:80].strip() or "arquivo"
    disp = "attachment" if dl else "inline"
    headers = {
        "Content-Disposition": f"{disp}; filename*=UTF-8''{quote(filename + ext)}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=3600",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }
    s = get_settings()
    if s.use_x_accel:
        headers["X-Accel-Redirect"] = f"{s.x_accel_prefix}/{a.storage_path}"
        return Response(status_code=200, headers=headers, media_type=a.mime)
    return FileResponse(path, media_type=a.mime, headers=headers)
