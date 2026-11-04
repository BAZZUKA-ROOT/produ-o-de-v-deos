from app.core.security import sign_media
from app.models import Asset, Job, Notification, Project, Scene, Template, User


def iso(dt):
    return dt.isoformat() if dt else None


def user_out(u: User) -> dict:
    return {"id": str(u.id), "name": u.name, "email": u.email, "role": u.role.value, "is_active": u.is_active,
            "quota_mb": u.quota_mb, "created_at": iso(u.created_at), "last_login_at": iso(u.last_login_at)}


def asset_out(a: Asset | None) -> dict | None:
    if a is None:
        return None
    return {
        "id": str(a.id), "kind": a.kind.value, "source": a.source.value, "name": a.name, "mime": a.mime,
        "size_bytes": a.size_bytes, "width": a.width, "height": a.height, "duration": a.duration,
        "project_id": str(a.project_id) if a.project_id else None, "in_library": a.in_library,
        "is_system": a.owner_id is None, "meta": {k: v for k, v in (a.meta or {}).items() if k != "timeline"},
        "url": sign_media(a.id), "download_url": sign_media(a.id, download=True), "created_at": iso(a.created_at),
    }


def scene_out(s: Scene) -> dict:
    return {
        "id": str(s.id), "position": s.position, "role": s.role, "title": s.title, "subtitle": s.subtitle,
        "narration": s.narration, "caption_override": s.caption_override, "image_prompt": s.image_prompt,
        "duration": s.duration, "transition": s.transition, "motion": s.motion, "text_animation": s.text_animation,
        "text_position": s.text_position, "fit": s.fit, "layout": s.layout, "bullets": s.bullets,
        "cutout_url": sign_media((s.image_asset.meta or {})["cutout_asset_id"])
        if s.image_asset and (s.image_asset.meta or {}).get("cutout_asset_id") else None,
        "cutout_usable": bool((s.image_asset.meta or {}).get("cutout_usable")) if s.image_asset else False,
        "image": asset_out(s.image_asset), "narration_audio": asset_out(s.narration_asset),
        "narration_duration": s.narration_duration,
    }


def job_out(j: Job | None) -> dict | None:
    if j is None:
        return None
    return {
        "id": str(j.id), "kind": j.kind.value, "status": j.status.value, "progress": j.progress, "stage": j.stage,
        "error": j.error, "result": j.result, "attempts": j.attempts, "project_id": str(j.project_id) if j.project_id else None,
        "created_at": iso(j.created_at), "started_at": iso(j.started_at), "finished_at": iso(j.finished_at),
    }


def project_summary(p: Project, db=None) -> dict:
    from app.models import Asset as A

    thumb = db.get(A, p.thumbnail_asset_id) if db and p.thumbnail_asset_id else None
    first_img = None
    if thumb is None and p.scenes:
        first_img = p.scenes[0].image_asset
    return {
        "id": str(p.id), "name": p.name, "status": p.status.value, "company_name": (p.company or {}).get("name"),
        "format": (p.settings or {}).get("format"), "duration": (p.settings or {}).get("duration"),
        "style": (p.settings or {}).get("style"), "video_type": (p.settings or {}).get("video_type"),
        "scene_count": len(p.scenes), "has_video": p.output_asset_id is not None,
        "thumbnail_url": sign_media(thumb.id) if thumb else (sign_media(first_img.id) if first_img else None),
        "template_id": str(p.template_id) if p.template_id else None,
        "owner_id": str(p.owner_id), "created_at": iso(p.created_at), "updated_at": iso(p.updated_at),
    }


def template_out(t: Template, full: bool = False) -> dict:
    cfg = t.config or {}
    out = {"id": str(t.id), "slug": t.slug, "category": t.category, "category_label": cfg.get("category_label", t.category),
           "name": t.name, "description": t.description, "style": t.style, "video_type": t.video_type,
           "palette": cfg.get("palette"), "font": cfg.get("font"), "scene_count": len(cfg.get("blueprint", [])),
           "is_active": t.is_active}
    if full:
        out["config"] = cfg
    return out


def notification_out(n: Notification) -> dict:
    return {"id": str(n.id), "title": n.title, "message": n.message, "level": n.level, "link": n.link, "read": n.read,
            "created_at": iso(n.created_at)}
