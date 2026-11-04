import io
import json
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_accessible_asset, get_current_user, get_owned_project
from app.api.serializers import asset_out, job_out, project_summary, scene_out
from app.core.catalog import STYLE_PRESETS, default_project_settings
from app.core.db import get_db
from app.models import (
    ACTIVE_JOB_STATUSES,
    Asset,
    AssetKind,
    AssetSource,
    Job,
    JobKind,
    Project,
    ProjectStatus,
    Scene,
    Template,
    User,
)
from app.schemas import (
    ImagesJobIn,
    NarrationJobIn,
    ProjectCreateIn,
    ProjectSettingsIn,
    ProjectUpdateIn,
    ReorderIn,
    SceneCreateIn,
    SceneIn,
)
from app.services import jobs as job_service
from app.services import pipeline, runtime_settings, storage
from app.video import timeline as tl

router = APIRouter(prefix="/projects", tags=["projects"])
HEAVY = (JobKind.render, JobKind.preview, JobKind.images, JobKind.narration, JobKind.script)


def _merge_settings(project: Project, data: ProjectSettingsIn, db: Session, user: User) -> None:
    current = pipeline.project_settings(project)
    patch = data.model_dump(exclude_unset=True, mode="json")
    for key in ("music_asset_id", "narration_asset_id", "logo_asset_id"):
        if patch.get(key):
            get_accessible_asset(db, uuid.UUID(patch[key]), user)
    for aid in patch.get("photo_asset_ids") or []:
        if get_accessible_asset(db, uuid.UUID(aid), user).kind not in (AssetKind.image, AssetKind.logo):
            raise HTTPException(422, "as fotos devem ser imagens")
    if patch.get("watermark", {}).get("asset_id"):
        get_accessible_asset(db, uuid.UUID(patch["watermark"]["asset_id"]), user)
    if "style" in patch and patch["style"] != current.get("style"):
        preset = STYLE_PRESETS[patch["style"]]
        patch.setdefault("font", preset["font"])
        patch.setdefault("palette", preset["palette"])
        patch.setdefault("music_mood", preset["music"])
    if patch.get("music_mood") and patch["music_mood"] != "none":
        from app.ai.music import MOODS

        if patch["music_mood"] not in MOODS:
            raise HTTPException(422, "trilha inválida")
    if patch.get("font"):
        from app.core.catalog import FONT_FILES

        if patch["font"] not in FONT_FILES:
            raise HTTPException(422, "fonte inválida")
    for k in ("watermark", "end_card"):
        if k in patch:
            patch[k] = {**current[k], **patch[k]}
    project.settings = {**current, **patch}


def _system_music(db: Session, s: dict) -> dict | None:
    mood = s.get("music_mood")
    if not mood or mood == "none":
        return None
    for a in db.query(Asset).filter(Asset.source == AssetSource.system, Asset.kind == AssetKind.music).all():
        if (a.meta or {}).get("mood") == mood:
            return asset_out(a)
    return None


def _detail(project: Project, db: Session) -> dict:
    s = pipeline.project_settings(project)
    ai = runtime_settings.get_section(db, "ai")
    provider = s.get("tts_provider") or ai["tts_provider"]
    scenes = []
    for sc in project.scenes:
        d = scene_out(sc)
        d["narration_stale"] = bool(sc.narration.strip()) and (
            sc.narration_asset_id is None
            or sc.narration_signature != pipeline._narr_signature(sc.narration, provider, s["voice_gender"],
                                                                  float(s["voice_speed"])))
        scenes.append(d)
    jobs = db.query(Job).filter(Job.project_id == project.id).order_by(Job.created_at.desc()).limit(10).all()
    active = next((j for j in jobs if j.status in ACTIVE_JOB_STATUSES), None)

    def a(aid):
        return asset_out(db.get(Asset, aid)) if aid else None

    return {
        **project_summary(project, db),
        "company": project.company, "settings": s, "script": project.script,
        "scenes": scenes, "output": a(project.output_asset_id), "preview": a(project.preview_asset_id),
        "thumbnail": a(project.thumbnail_asset_id), "music": a(s.get("music_asset_id")) or _system_music(db, s),
        "logo": a(s.get("logo_asset_id")), "narration_track": a(s.get("narration_asset_id")),
        "active_job": job_out(active), "jobs": [job_out(j) for j in jobs],
        "template": {"id": str(project.template.id), "name": project.template.name} if project.template else None,
    }


@router.get("")
def list_projects(
    q: str | None = None, status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    query = db.query(Project).filter(Project.owner_id == user.id).options(selectinload(Project.scenes))
    if q:
        like = f"%{q.strip()[:100]}%"
        query = query.filter(or_(Project.name.ilike(like)))
    if status_filter:
        try:
            query = query.filter(Project.status == ProjectStatus(status_filter))
        except ValueError:
            raise HTTPException(422, "status inválido") from None
    total = query.count()
    items = query.order_by(Project.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [project_summary(p, db) for p in items], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create_project(data: ProjectCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    template = None
    base_style = data.settings.style or "moderno"
    if data.template_id:
        template = db.get(Template, data.template_id)
        if template is None or not template.is_active:
            raise HTTPException(404, "Template não encontrado")
        base_style = data.settings.style or template.style
    settings = default_project_settings(base_style)
    if template:
        cfg = template.config or {}
        settings.update({
            "video_type": template.video_type, "style": template.style,
            "format": cfg.get("format", settings["format"]), "duration": cfg.get("duration", settings["duration"]),
            "palette": cfg.get("palette", settings["palette"]), "font": cfg.get("font", settings["font"]),
            "music_mood": cfg.get("music_mood", settings["music_mood"]),
        })
    project = Project(owner_id=user.id, template_id=template.id if template else None,
                      name=data.name or f"{data.company.name} — vídeo", company=data.company.model_dump(),
                      settings=settings)
    _merge_settings(project, data.settings, db, user)
    db.add(project)
    db.commit()
    return _detail(project, db)


@router.get("/{project_id}")
def get_project(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    return _detail(project, db)


@router.patch("/{project_id}")
def update_project(data: ProjectUpdateIn, project: Project = Depends(get_owned_project),
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.name is not None:
        project.name = data.name
    if data.company is not None:
        project.company = data.company.model_dump()
    if data.settings is not None:
        _merge_settings(project, data.settings, db, user)
    if data.script is not None:
        allowed = {"title", "hook", "cta", "caption", "hashtags", "analysis"}
        project.script = {**(project.script or {}), **{k: v for k, v in data.script.items() if k in allowed}}
    db.commit()
    db.refresh(project)
    return _detail(project, db)


def _referenced_elsewhere(db: Session, asset_id, project_id) -> bool:
    used_scene = db.query(Scene.id).filter(
        or_(Scene.image_asset_id == asset_id, Scene.narration_asset_id == asset_id), Scene.project_id != project_id
    ).first()
    return used_scene is not None


def delete_project_files(db: Session, project: Project) -> None:
    assets = db.query(Asset).filter(Asset.project_id == project.id).all()
    for a in assets:
        if a.source == AssetSource.upload or (a.in_library and a.kind in (AssetKind.image, AssetKind.music)):
            a.project_id = None  # mantém na biblioteca do usuário
            continue
        if _referenced_elsewhere(db, a.id, project.id):
            a.project_id = None
            continue
        storage.delete_asset_file(a)
        db.delete(a)


@router.delete("/{project_id}", status_code=204)
def delete_project(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    for j in db.query(Job).filter(Job.project_id == project.id, Job.status.in_(ACTIVE_JOB_STATUSES)).all():
        job_service.cancel(db, j)
    project.output_asset_id = project.preview_asset_id = project.thumbnail_asset_id = None
    db.flush()
    delete_project_files(db, project)
    db.delete(project)
    db.commit()


@router.post("/{project_id}/duplicate", status_code=201)
def duplicate_project(project: Project = Depends(get_owned_project), user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    copy = Project(owner_id=user.id, template_id=project.template_id, name=f"{project.name} (cópia)"[:200],
                   company=dict(project.company or {}), settings=json.loads(json.dumps(project.settings or {})),
                   script=dict(project.script or {}),
                   status=ProjectStatus.ready if project.scenes else ProjectStatus.draft)
    for sc in project.scenes:
        copy.scenes.append(Scene(
            position=sc.position, role=sc.role, title=sc.title, subtitle=sc.subtitle, narration=sc.narration,
            caption_override=sc.caption_override, image_prompt=sc.image_prompt, duration=sc.duration,
            transition=sc.transition, motion=sc.motion, text_animation=sc.text_animation,
            text_position=sc.text_position, fit=sc.fit, image_asset_id=sc.image_asset_id,
            narration_asset_id=sc.narration_asset_id, narration_duration=sc.narration_duration,
            narration_signature=sc.narration_signature,
        ))
    db.add(copy)
    db.commit()
    return _detail(copy, db)


# ---------- Cenas ----------

def _scene(project: Project, scene_id: uuid.UUID) -> Scene:
    for sc in project.scenes:
        if sc.id == scene_id:
            return sc
    raise HTTPException(404, "Cena não encontrada")


def _apply_scene(sc: Scene, data: SceneIn, db: Session, user: User) -> None:
    patch = data.model_dump(exclude_unset=True)
    if patch.pop("clear_image", False):
        sc.image_asset_id = None
    if "image_asset_id" in patch:
        aid = patch.pop("image_asset_id")
        if aid:
            asset = get_accessible_asset(db, aid, user)
            if asset.kind not in (AssetKind.image, AssetKind.logo):
                raise HTTPException(422, "o arquivo selecionado não é uma imagem")
        sc.image_asset_id = aid
    for k, v in patch.items():
        if v is not None:
            setattr(sc, k, v)


def _touch(project: Project) -> None:
    if project.status in (ProjectStatus.draft, ProjectStatus.failed, ProjectStatus.cancelled) and project.scenes:
        project.status = ProjectStatus.ready


@router.post("/{project_id}/scenes", status_code=201)
def add_scene(data: SceneCreateIn, project: Project = Depends(get_owned_project),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(project.scenes) >= 20:
        raise HTTPException(422, "limite de 20 cenas por projeto")
    s = pipeline.project_settings(project)
    preset = STYLE_PRESETS.get(s["style"], STYLE_PRESETS["moderno"])
    sc = Scene(title="Nova cena", duration=4.0, transition=preset["transition"], motion=preset["motion"],
               text_animation=preset["animation"])
    _apply_scene(sc, data, db, user)
    pos = data.position if data.position is not None else len(project.scenes)
    scenes = list(project.scenes)
    scenes.insert(min(pos, len(scenes)), sc)
    project.scenes = scenes
    for i, x in enumerate(project.scenes):
        x.position = i
    _touch(project)
    db.commit()
    return _detail(project, db)


@router.patch("/{project_id}/scenes/{scene_id}")
def update_scene(scene_id: uuid.UUID, data: SceneIn, project: Project = Depends(get_owned_project),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sc = _scene(project, scene_id)
    _apply_scene(sc, data, db, user)
    db.commit()
    return scene_out(sc)


@router.delete("/{project_id}/scenes/{scene_id}")
def delete_scene(scene_id: uuid.UUID, project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    sc = _scene(project, scene_id)
    project.scenes.remove(sc)
    db.delete(sc)
    for i, x in enumerate(project.scenes):
        x.position = i
    db.commit()
    return _detail(project, db)


@router.post("/{project_id}/scenes/reorder")
def reorder_scenes(data: ReorderIn, project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    by_id = {sc.id: sc for sc in project.scenes}
    if set(data.scene_ids) != set(by_id) or len(data.scene_ids) != len(by_id):
        raise HTTPException(422, "a lista deve conter todas as cenas do projeto")
    for i, sid in enumerate(data.scene_ids):
        by_id[sid].position = i
    db.commit()
    db.refresh(project)
    return _detail(project, db)


@router.get("/{project_id}/timeline")
def get_timeline(project: Project = Depends(get_owned_project)):
    s = pipeline.project_settings(project)
    if not project.scenes:
        return {"total": 0, "tempo": 1, "scenes": [], "end_card_start": None, "end_card_duration": 0, "warnings": []}
    upload_mode = s["narration_enabled"] and s.get("narration_mode") == "upload"
    end = s["end_card"]
    t = tl.compute(
        [tl.SceneIn(str(sc.id), sc.duration, sc.transition, sc.narration, sc.caption_override, sc.narration_duration)
         for sc in project.scenes],
        target=float(s["duration"]), fit=bool(s.get("fit_duration", True)),
        narration_enabled=bool(s["narration_enabled"]) and not upload_mode,
        subtitles_enabled=bool(s["subtitles_enabled"]),
        end_card_duration=float(end["duration"]) if end.get("enabled") else 0.0,
    )
    return t.to_dict()


# ---------- Tarefas ----------

def _ensure_idle(db: Session, project: Project) -> None:
    if job_service.active_job(db, project.id, HEAVY):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma tarefa em andamento neste projeto")


@router.post("/{project_id}/script", status_code=202)
def generate_script(project: Project = Depends(get_owned_project), user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    _ensure_idle(db, project)
    project.status = ProjectStatus.scripting
    db.commit()
    job = job_service.enqueue(db, JobKind.script, user_id=user.id, project=project)
    return job_out(job)


@router.post("/{project_id}/images", status_code=202)
def generate_images(data: ImagesJobIn, project: Project = Depends(get_owned_project),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_idle(db, project)
    if not project.scenes:
        raise HTTPException(422, "o projeto não possui cenas")
    params = {"force": data.force, "scene_ids": [str(s) for s in data.scene_ids] if data.scene_ids else None}
    return job_out(job_service.enqueue(db, JobKind.images, user_id=user.id, project=project, params=params))


@router.post("/{project_id}/narration", status_code=202)
def generate_narration(data: NarrationJobIn, project: Project = Depends(get_owned_project),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_idle(db, project)
    if not any(sc.narration.strip() for sc in project.scenes):
        raise HTTPException(422, "nenhuma cena possui texto de narração")
    return job_out(job_service.enqueue(db, JobKind.narration, user_id=user.id, project=project,
                                       params={"force": data.force}))


@router.post("/{project_id}/render", status_code=202)
def render(project: Project = Depends(get_owned_project), user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    _ensure_idle(db, project)
    if not project.scenes:
        raise HTTPException(422, "o projeto não possui cenas")
    return job_out(job_service.enqueue(db, JobKind.render, user_id=user.id, project=project))


@router.post("/{project_id}/preview", status_code=202)
def preview(project: Project = Depends(get_owned_project), user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    _ensure_idle(db, project)
    if not project.scenes:
        raise HTTPException(422, "o projeto não possui cenas")
    return job_out(job_service.enqueue(db, JobKind.preview, user_id=user.id, project=project))


@router.get("/{project_id}/jobs")
def project_jobs(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.project_id == project.id).order_by(Job.created_at.desc()).limit(50).all()
    return [job_out(j) for j in jobs]


# ---------- Exportação / Importação ----------

EXPORT_VERSION = 1


@router.get("/{project_id}/export")
def export_project(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    buf = io.BytesIO()
    files: dict[str, str] = {}

    def add_asset(zf: zipfile.ZipFile, aid) -> str | None:
        if not aid:
            return None
        a = db.get(Asset, aid)
        if a is None:
            return None
        p = storage.abs_path(a.storage_path)
        if not p.exists():
            return None
        key = str(a.id)
        if key not in files:
            arc = f"assets/{a.kind.value}/{a.id}{p.suffix}"
            zf.write(p, arc)
            files[key] = arc
        return files[key]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        s = dict(project.settings or {})
        data = {
            "version": EXPORT_VERSION, "name": project.name, "company": project.company, "script": project.script,
            "settings": s,
            "files": {
                "music": add_asset(zf, s.get("music_asset_id")) if s.get("music_asset_id") else None,
                "logo": add_asset(zf, s.get("logo_asset_id")),
                "narration_track": add_asset(zf, s.get("narration_asset_id")),
                "output": add_asset(zf, project.output_asset_id),
            },
            "scenes": [{
                **{k: v for k, v in scene_out(sc).items() if k not in ("id", "image", "narration_audio")},
                "image_file": add_asset(zf, sc.image_asset_id),
            } for sc in project.scenes],
        }
        zf.writestr("project.json", json.dumps(data, ensure_ascii=False, indent=2, default=str))
    buf.seek(0)
    safe = "".join(c for c in project.name if c.isalnum() or c in " -_")[:60].strip() or "projeto"
    ascii_name = safe.encode("ascii", "ignore").decode() or "projeto"
    disp = f'attachment; filename="{ascii_name}.forja.zip"; filename*=UTF-8\'\'{quote(safe)}.forja.zip'
    return StreamingResponse(buf, media_type="application/zip", headers={"Content-Disposition": disp})


MAX_IMPORT_BYTES = 300 * 1024 * 1024


@router.post("/import", status_code=201)
def import_project(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.api.assets import copy_upload_limited

    tmpdir = Path(tempfile.mkdtemp(prefix="import_", dir=storage.get_settings().temp_dir))
    try:
        zpath = tmpdir / "in.zip"
        copy_upload_limited(file, zpath, MAX_IMPORT_BYTES)
        if not zipfile.is_zipfile(zpath):
            raise HTTPException(422, "arquivo não é um ZIP válido")
        with zipfile.ZipFile(zpath) as zf:
            infos = {i.filename: i for i in zf.infolist()}
            if sum(i.file_size for i in infos.values()) > MAX_IMPORT_BYTES * 2:
                raise HTTPException(422, "conteúdo do ZIP excede o limite")
            if "project.json" not in infos:
                raise HTTPException(422, "project.json ausente")
            data = json.loads(zf.read("project.json").decode("utf-8"))
            if data.get("version") != EXPORT_VERSION:
                raise HTTPException(422, "versão de exportação incompatível")

            def ingest(arc: str | None, kind: AssetKind) -> uuid.UUID | None:
                if not arc or arc not in infos or not arc.startswith("assets/") or ".." in arc:
                    return None
                target = tmpdir / f"x_{uuid.uuid4().hex}{Path(arc).suffix.lower()}"
                with zf.open(arc) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                try:
                    if kind in (AssetKind.image, AssetKind.logo):
                        st = storage.store_image_upload(target, user.id, target.name)
                    else:
                        st = storage.store_audio_upload(target, user.id, target.name)
                except storage.UploadError:
                    return None
                a = storage.create_asset(db, st, owner_id=user.id, kind=kind, source=AssetSource.upload,
                                         name=f"Importado · {Path(arc).name}")
                return a.id

            company = data.get("company") or {}
            body = ProjectCreateIn(name=str(data.get("name", "Projeto importado"))[:200],
                                   company={k: str(v)[:300] for k, v in company.items()
                                            if k in ProjectCreateIn.model_fields["company"].annotation.model_fields}
                                   or {"name": "Empresa"})
            settings = default_project_settings((data.get("settings") or {}).get("style", "moderno"))
            project = Project(owner_id=user.id, name=body.name or "Projeto importado", company=body.company.model_dump(),
                              settings=settings, script=data.get("script") or {})
            raw = dict(data.get("settings") or {})
            for k in ("music_asset_id", "logo_asset_id", "narration_asset_id"):
                raw.pop(k, None)
            if isinstance(raw.get("watermark"), dict):
                raw["watermark"].pop("asset_id", None)
            try:
                _merge_settings(project, ProjectSettingsIn(**{k: v for k, v in raw.items()
                                                              if k in ProjectSettingsIn.model_fields}), db, user)
            except ValueError:
                pass
            files = data.get("files") or {}
            extra = {}
            if (mid := ingest(files.get("music"), AssetKind.music)):
                extra["music_asset_id"] = str(mid)
            if (lid := ingest(files.get("logo"), AssetKind.logo)):
                extra["logo_asset_id"] = str(lid)
            if (nid := ingest(files.get("narration_track"), AssetKind.audio)):
                extra["narration_asset_id"] = str(nid)
            project.settings = {**project.settings, **extra}
            for i, sd in enumerate((data.get("scenes") or [])[:20]):
                try:
                    clean = SceneIn(**{k: v for k, v in sd.items() if k in SceneIn.model_fields and k != "image_asset_id"})
                except ValueError:
                    continue
                sc = Scene(position=i)
                _apply_scene(sc, clean, db, user)
                sc.image_asset_id = ingest(sd.get("image_file"), AssetKind.image)
                project.scenes.append(sc)
            project.status = ProjectStatus.ready if project.scenes else ProjectStatus.draft
            db.add(project)
            db.commit()
            return _detail(project, db)
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(422, f"arquivo de projeto inválido: {exc}") from None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

