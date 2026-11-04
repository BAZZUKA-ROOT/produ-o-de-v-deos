"""Rotas de templates, tarefas, notificações, dashboard e catálogo de opções."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.ai.music import MOODS
from app.api.deps import get_current_user
from app.api.serializers import asset_out, job_out, notification_out, project_summary, template_out
from app.core import catalog
from app.core.db import get_db
from app.models import (
    ACTIVE_JOB_STATUSES,
    Asset,
    AssetKind,
    Job,
    Notification,
    Project,
    ProjectStatus,
    Role,
    Template,
    User,
)
from app.services import jobs as job_service

router = APIRouter(tags=["general"])


@router.get("/meta/options")
def options(_: User = Depends(get_current_user)):
    return {
        "formats": list(catalog.FORMATS), "durations": list(catalog.DURATIONS), "qualities": list(catalog.QUALITIES),
        "styles": catalog.STYLES, "video_types": catalog.VIDEO_TYPES, "transitions": catalog.TRANSITIONS,
        "motions": catalog.MOTIONS, "text_animations": catalog.TEXT_ANIMATIONS,
        "text_positions": catalog.TEXT_POSITIONS, "fits": catalog.FITS, "voices": catalog.VOICES,
        "music_moods": {k: v for k, v in catalog.MUSIC_MOODS.items() if k in MOODS},
        "subtitle_styles": catalog.SUBTITLE_STYLES, "fonts": list(catalog.FONT_FILES),
        "style_presets": catalog.STYLE_PRESETS,
    }


@router.get("/templates")
def list_templates(category: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(Template).filter(Template.is_active.is_(True))
    if category:
        q = q.filter(Template.category == category)
    items = q.order_by(Template.category, Template.name).all()
    cats: dict[str, dict] = {}
    for t in items:
        c = cats.setdefault(t.category, {"slug": t.category, "label": (t.config or {}).get("category_label", t.category),
                                         "count": 0})
        c["count"] += 1
    return {"items": [template_out(t) for t in items], "categories": list(cats.values())}


@router.get("/templates/{template_id}")
def get_template(template_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = db.get(Template, template_id)
    if t is None or not t.is_active:
        raise HTTPException(404, "Template não encontrado")
    return template_out(t, full=True)


def _owned_job(db: Session, job_id: uuid.UUID, user: User) -> Job:
    job = db.get(Job, job_id)
    if job is None or (job.user_id != user.id and user.role != Role.admin):
        raise HTTPException(404, "Tarefa não encontrada")
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = _owned_job(db, job_id, user)
    out = job_out(j)
    out["logs"] = j.logs
    return out


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = _owned_job(db, job_id, user)
    job_service.cancel(db, j)
    if j.status.value == "cancelled" and j.project_id:
        p = db.get(Project, j.project_id)
        if p and p.status in (ProjectStatus.processing, ProjectStatus.scripting):
            p.status = ProjectStatus.completed if p.output_asset_id else (
                ProjectStatus.ready if p.scenes else ProjectStatus.draft)
            db.commit()
    return job_out(j)


@router.get("/notifications")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (db.query(Notification).filter(Notification.user_id == user.id)
             .order_by(Notification.created_at.desc()).limit(30).all())
    unread = db.query(Notification).filter(Notification.user_id == user.id, Notification.read.is_(False)).count()
    return {"items": [notification_out(n) for n in items], "unread": unread}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.read.is_(False)).update({"read": True})
    db.commit()
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
def read_one(notification_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "Notificação não encontrada")
    n.read = True
    db.commit()
    return notification_out(n)


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    counts = dict(db.query(Project.status, func.count()).filter(Project.owner_id == user.id)
                  .group_by(Project.status).all())
    total_projects = sum(counts.values())
    videos = db.query(func.count(Job.id)).filter(Job.user_id == user.id, Job.kind == "render",
                                                 Job.status == "completed").scalar()
    in_progress = sum(counts.get(s, 0) for s in (ProjectStatus.draft, ProjectStatus.scripting, ProjectStatus.ready,
                                                 ProjectStatus.processing))
    recent = (db.query(Project).filter(Project.owner_id == user.id).options(selectinload(Project.scenes))
              .order_by(Project.updated_at.desc()).limit(6).all())
    active_jobs = (db.query(Job).filter(Job.user_id == user.id, Job.status.in_(ACTIVE_JOB_STATUSES))
                   .order_by(Job.created_at.desc()).limit(10).all())
    templates = db.query(func.count(Template.id)).filter(Template.is_active.is_(True)).scalar()
    lib_count = db.query(func.count(Asset.id)).filter(Asset.owner_id == user.id, Asset.in_library.is_(True)).scalar()
    recent_videos = (db.query(Asset).filter(Asset.owner_id == user.id, Asset.kind == AssetKind.video,
                                            Asset.in_library.is_(True))
                     .order_by(Asset.created_at.desc()).limit(4).all())
    return {
        "videos_produced": videos,
        "projects_total": total_projects,
        "projects_in_progress": in_progress,
        "projects_completed": counts.get(ProjectStatus.completed, 0),
        "projects_failed": counts.get(ProjectStatus.failed, 0),
        "templates_available": templates,
        "library_items": lib_count,
        "recent_projects": [project_summary(p, db) for p in recent],
        "active_jobs": [job_out(j) for j in active_jobs],
        "recent_videos": [asset_out(a) for a in recent_videos],
    }
