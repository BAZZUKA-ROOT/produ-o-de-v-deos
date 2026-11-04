import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone

import psutil
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session, selectinload

from app.ai import tts
from app.ai.image import comfyui
from app.ai.llm.script import ollama_status
from app.api.deps import require_admin
from app.api.projects import delete_project_files
from app.api.serializers import iso, job_out, project_summary, template_out, user_out
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import hash_password
from app.models import (
    ACTIVE_JOB_STATUSES,
    Asset,
    AssetKind,
    ErrorLog,
    Job,
    JobKind,
    JobStatus,
    Project,
    Role,
    Template,
    User,
)
from app.schemas import AdminUserCreateIn, AdminUserUpdateIn, ModelPullIn, SettingsUpdateIn, TemplateIn
from app.seed.templates import seed_templates
from app.services import jobs as job_service
from app.services import runtime_settings, storage

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
_STARTED = time.time()


# ---------- Visão geral / recursos / serviços ----------

def _resources() -> dict:
    s = get_settings()
    disk = shutil.disk_usage(s.storage_dir)
    vm = psutil.virtual_memory()
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2), "cpu_count": psutil.cpu_count(),
        "load_avg": [round(x, 2) for x in load],
        "ram_total": vm.total, "ram_used": vm.total - vm.available, "ram_percent": vm.percent,
        "disk_total": disk.total, "disk_used": disk.used, "disk_free": disk.free,
        "disk_percent": round(disk.used / disk.total * 100, 1) if disk.total else 0,
        "api_uptime_seconds": int(time.time() - _STARTED), "timestamp": iso(datetime.now(timezone.utc)),
    }


def _services(db: Session) -> dict:
    ai = runtime_settings.get_section(db, "ai")
    out: dict = {}
    t = time.time()
    try:
        db.execute(text("SELECT 1"))
        out["database"] = {"online": True, "latency_ms": round((time.time() - t) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        out["database"] = {"online": False, "error": str(exc)}
    try:
        t = time.time()
        job_service.get_redis().ping()
        out["redis"] = {"online": True, "latency_ms": round((time.time() - t) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        out["redis"] = {"online": False, "error": str(exc)}
    try:
        from app.workers.celery_app import celery_app

        replies = celery_app.control.inspect(timeout=1.5).ping() or {}
        out["workers"] = {"online": bool(replies), "count": len(replies), "names": list(replies)}
    except Exception as exc:  # noqa: BLE001
        out["workers"] = {"online": False, "error": str(exc), "count": 0}
    out["ollama"] = {**ollama_status(ai), "url": ai["ollama_url"], "model": ai["ollama_model"],
                     "active": ai["llm_provider"] == "ollama"}
    out["comfyui"] = {**comfyui.status(ai), "url": ai["comfyui_url"], "active": ai["image_provider"] == "comfyui"}
    out["tts"] = {"providers": tts.status(ai), "active": ai["tts_provider"]}
    try:
        v = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5).stdout.split("\n")[0]
        out["ffmpeg"] = {"online": True, "version": v}
    except Exception as exc:  # noqa: BLE001
        out["ffmpeg"] = {"online": False, "error": str(exc)}
    return out


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    day = datetime.now(timezone.utc) - timedelta(days=1)
    jobs_by_status = dict(db.query(Job.status, func.count()).group_by(Job.status).all())
    return {
        "users": db.query(func.count(User.id)).scalar(),
        "projects": db.query(func.count(Project.id)).scalar(),
        "videos": db.query(func.count(Asset.id)).filter(Asset.kind == AssetKind.video, Asset.in_library.is_(True)).scalar(),
        "renders_24h": db.query(func.count(Job.id)).filter(Job.kind == JobKind.render, Job.created_at >= day).scalar(),
        "failures_24h": db.query(func.count(Job.id)).filter(Job.status == JobStatus.failed, Job.created_at >= day).scalar(),
        "errors_24h": db.query(func.count(ErrorLog.id)).filter(ErrorLog.created_at >= day).scalar(),
        "jobs_by_status": {k.value: v for k, v in jobs_by_status.items()},
        "active_jobs": [job_out(j) for j in db.query(Job).filter(Job.status.in_(ACTIVE_JOB_STATUSES))
                        .order_by(Job.created_at).limit(20).all()],
        "resources": _resources(),
    }


@router.get("/resources")
def resources():
    return _resources()


@router.get("/services")
def services(db: Session = Depends(get_db)):
    return _services(db)


@router.get("/workers")
def workers():
    from app.workers.celery_app import celery_app

    insp = celery_app.control.inspect(timeout=2)
    try:
        return {"active": insp.active() or {}, "reserved": insp.reserved() or {}, "stats": insp.stats() or {}}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"broker indisponível: {exc}") from None


# ---------- Usuários ----------

@router.get("/users")
def list_users(q: str | None = None, db: Session = Depends(get_db)):
    query = db.query(User)
    if q:
        like = f"%{q[:100]}%"
        query = query.filter((User.email.ilike(like)) | (User.name.ilike(like)))
    users = query.order_by(User.created_at.desc()).limit(500).all()
    pc = dict(db.query(Project.owner_id, func.count()).group_by(Project.owner_id).all())
    usage = dict(db.query(Asset.owner_id, func.sum(Asset.size_bytes)).group_by(Asset.owner_id).all())
    return [{**user_out(u), "projects": pc.get(u.id, 0), "usage_bytes": int(usage.get(u.id) or 0)} for u in users]


@router.post("/users", status_code=201)
def create_user(data: AdminUserCreateIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(409, "E-mail já cadastrado")
    u = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password),
             role=Role(data.role), quota_mb=data.quota_mb)
    db.add(u)
    db.commit()
    return user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: uuid.UUID, data: AdminUserUpdateIn, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Usuário não encontrado")
    if u.id == admin.id and (data.role == "user" or data.is_active is False):
        raise HTTPException(422, "você não pode remover seu próprio acesso de administrador")
    patch = data.model_dump(exclude_unset=True)
    if "password" in patch and patch["password"]:
        u.password_hash = hash_password(patch.pop("password"))
        u.token_version += 1
    patch.pop("password", None)
    if "role" in patch:
        u.role = Role(patch.pop("role"))
        u.token_version += 1
    if patch.get("is_active") is False:
        u.token_version += 1
    for k, v in patch.items():
        setattr(u, k, v)
    db.commit()
    return user_out(u)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Usuário não encontrado")
    if u.id == admin.id:
        raise HTTPException(422, "não é possível excluir a própria conta")
    for a in db.query(Asset).filter(Asset.owner_id == u.id).all():
        storage.delete_asset_file(a)
    db.delete(u)
    db.commit()


# ---------- Projetos ----------

@router.get("/projects")
def list_all_projects(q: str | None = None, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    query = db.query(Project).options(selectinload(Project.scenes), selectinload(Project.owner))
    if q:
        query = query.filter(Project.name.ilike(f"%{q[:100]}%"))
    total = query.count()
    items = query.order_by(Project.updated_at.desc()).offset((page - 1) * 50).limit(50).all()
    return {"total": total, "items": [{**project_summary(p, db), "owner_email": p.owner.email} for p in items]}


@router.delete("/projects/{project_id}", status_code=204)
def admin_delete_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "Projeto não encontrado")
    for j in db.query(Job).filter(Job.project_id == p.id, Job.status.in_(ACTIVE_JOB_STATUSES)).all():
        job_service.cancel(db, j)
    p.output_asset_id = p.preview_asset_id = p.thumbnail_asset_id = None
    db.flush()
    delete_project_files(db, p)
    db.delete(p)
    db.commit()


# ---------- Tarefas / renderizações ----------

@router.get("/jobs")
def list_jobs(kind: str | None = None, status: str | None = None, page: int = Query(1, ge=1),
              db: Session = Depends(get_db)):
    query = db.query(Job).options(selectinload(Job.user), selectinload(Job.project))
    if kind:
        query = query.filter(Job.kind == kind)
    if status:
        query = query.filter(Job.status == status)
    total = query.count()
    items = query.order_by(Job.created_at.desc()).offset((page - 1) * 50).limit(50).all()
    out = []
    for j in items:
        d = job_out(j)
        d["user_email"] = j.user.email if j.user else None
        d["project_name"] = j.project.name if j.project else None
        if j.started_at and j.finished_at:
            d["duration_seconds"] = round((j.finished_at - j.started_at).total_seconds(), 1)
        out.append(d)
    return {"total": total, "items": out}


@router.get("/jobs/{job_id}")
def job_detail(job_id: uuid.UUID, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "Tarefa não encontrada")
    return {**job_out(j), "logs": j.logs, "params": j.params, "celery_task_id": j.celery_task_id}


@router.post("/jobs/{job_id}/cancel")
def admin_cancel(job_id: uuid.UUID, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "Tarefa não encontrada")
    return job_out(job_service.cancel(db, j))


@router.post("/jobs/{job_id}/retry", status_code=202)
def admin_retry(job_id: uuid.UUID, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "Tarefa não encontrada")
    if j.status in ACTIVE_JOB_STATUSES:
        raise HTTPException(409, "tarefa ainda ativa")
    project = db.get(Project, j.project_id) if j.project_id else None
    if j.project_id and project is None:
        raise HTTPException(422, "projeto da tarefa não existe mais")
    if project and job_service.active_job(db, project.id):
        raise HTTPException(409, "o projeto já possui tarefa ativa")
    return job_out(job_service.enqueue(db, j.kind, user_id=j.user_id, project=project, params=j.params))


# ---------- Logs ----------

@router.get("/logs")
def list_logs(source: str | None = None, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    query = db.query(ErrorLog)
    if source:
        query = query.filter(ErrorLog.source.ilike(f"{source[:60]}%"))
    total = query.count()
    items = query.order_by(ErrorLog.created_at.desc()).offset((page - 1) * 50).limit(50).all()
    return {"total": total, "items": [{"id": str(e.id), "source": e.source, "level": e.level, "message": e.message,
                                       "traceback": e.traceback, "context": e.context, "created_at": iso(e.created_at)}
                                      for e in items]}


@router.delete("/logs", status_code=204)
def clear_logs(older_than_days: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = db.query(ErrorLog)
    if older_than_days:
        q = q.filter(ErrorLog.created_at < datetime.now(timezone.utc) - timedelta(days=older_than_days))
    q.delete(synchronize_session=False)
    db.commit()


# ---------- Configurações ----------

@router.get("/settings")
def get_settings_all(db: Session = Depends(get_db)):
    return {"values": runtime_settings.get_all(db, use_cache=False), "defaults": runtime_settings.defaults(),
            "env": {"storage_dir": str(get_settings().storage_dir), "models_dir": str(get_settings().models_dir),
                    "temp_dir": str(get_settings().temp_dir)}}


@router.put("/settings/{section}")
def put_settings(section: str, data: SettingsUpdateIn, db: Session = Depends(get_db)):
    try:
        return runtime_settings.update_section(db, section, data.values)
    except KeyError:
        raise HTTPException(404, "seção inexistente") from None
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, f"valor inválido: {exc}") from None


@router.post("/ai/pull", status_code=202)
def pull_model(data: ModelPullIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Job).filter(Job.kind == JobKind.model_pull, Job.status.in_(ACTIVE_JOB_STATUSES)).first():
        raise HTTPException(409, "já existe um download de modelo em andamento")
    return job_out(job_service.enqueue(db, JobKind.model_pull, user_id=admin.id, params={"model": data.model}))


@router.post("/ai/test-llm")
def test_llm(db: Session = Depends(get_db)):
    from app.ai.llm.script import generate_script

    ai = runtime_settings.get_section(db, "ai")
    t = time.time()
    script, notes = generate_script(
        {"name": "Padaria Teste", "segment": "Padaria", "product": "Pão francês", "offer": "10% de desconto",
         "whatsapp": "(11) 90000-0000"},
        {"duration": 15, "format": "9:16", "style": "moderno", "video_type": "promocao",
         "end_card": {"enabled": True, "duration": 3}}, None, ai)
    return {"seconds": round(time.time() - t, 1), "engine": script.get("engine"), "notes": notes, "script": script}


# ---------- Armazenamento ----------

@router.get("/storage")
def storage_info(db: Session = Depends(get_db)):
    s = get_settings()
    by_kind = db.query(Asset.kind, func.count(), func.coalesce(func.sum(Asset.size_bytes), 0)).group_by(Asset.kind).all()
    disk = shutil.disk_usage(s.storage_dir)
    return {
        "storage_dir": str(s.storage_dir), "temp_dir": str(s.temp_dir), "models_dir": str(s.models_dir),
        "storage_bytes": storage.dir_size(s.storage_dir), "temp_bytes": storage.dir_size(s.temp_dir),
        "models_bytes": storage.dir_size(s.models_dir),
        "disk_total": disk.total, "disk_free": disk.free,
        "by_kind": [{"kind": k.value, "count": c, "bytes": int(b)} for k, c, b in by_kind],
        "settings": runtime_settings.get_section(db, "storage"),
    }


@router.post("/storage/cleanup-temp")
def cleanup_temp():
    from app.workers.tasks import cleanup_temp as task

    return {"removed": task.run()}


@router.post("/storage/scan-orphans")
def scan_orphans(delete: bool = False, db: Session = Depends(get_db)):
    root = storage.root()
    known = {a.storage_path for a in db.query(Asset.storage_path).all()}
    orphans, size = [], 0
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel not in known:
                orphans.append(rel)
                size += p.stat().st_size
                if delete:
                    p.unlink(missing_ok=True)
    missing = [str(a.id) for a in db.query(Asset).all() if not (root / a.storage_path).exists()]
    return {"orphans": len(orphans), "orphan_bytes": size, "deleted": delete, "missing_files": missing[:100]}


# ---------- Templates ----------

@router.get("/templates")
def admin_templates(db: Session = Depends(get_db)):
    return [template_out(t, full=True) for t in db.query(Template).order_by(Template.category, Template.name).all()]


@router.post("/templates", status_code=201)
def create_template(data: TemplateIn, db: Session = Depends(get_db)):
    if db.query(Template).filter(Template.slug == data.slug).first():
        raise HTTPException(409, "slug já existe")
    _validate_template_cfg(data.config)
    t = Template(**data.model_dump())
    db.add(t)
    db.commit()
    return template_out(t, full=True)


@router.put("/templates/{template_id}")
def update_template(template_id: uuid.UUID, data: TemplateIn, db: Session = Depends(get_db)):
    t = db.get(Template, template_id)
    if t is None:
        raise HTTPException(404, "Template não encontrado")
    _validate_template_cfg(data.config)
    for k, v in data.model_dump().items():
        setattr(t, k, v)
    db.commit()
    return template_out(t, full=True)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: uuid.UUID, db: Session = Depends(get_db)):
    t = db.get(Template, template_id)
    if t is None:
        raise HTTPException(404, "Template não encontrado")
    db.delete(t)
    db.commit()


@router.post("/templates/reseed")
def reseed(db: Session = Depends(get_db)):
    return {"created": seed_templates(db)}


def _validate_template_cfg(cfg: dict) -> None:
    bp = cfg.get("blueprint")
    if not isinstance(bp, list) or not 1 <= len(bp) <= 10:
        raise HTTPException(422, "config.blueprint deve ser uma lista de 1 a 10 cenas")
    for b in bp:
        if not isinstance(b, dict) or not all(isinstance(b.get(k), str) for k in ("role", "title", "narration", "image")):
            raise HTTPException(422, "cada cena do blueprint precisa de role, title, narration e image (texto)")
    pal = cfg.get("palette")
    if pal is not None and (not isinstance(pal, list) or len(pal) != 4):
        raise HTTPException(422, "config.palette deve ter 4 cores")
