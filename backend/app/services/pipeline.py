"""Etapas de produção executadas pelo worker: roteiro, imagens, narração e renderização."""

import hashlib
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai import music as music_gen
from app.ai import tts
from app.ai.image import generate_scene_image
from app.ai.llm.script import generate_script
from app.core.catalog import STYLE_PRESETS, VOICES, default_project_settings, resolution
from app.core.config import get_settings
from app.models import Asset, AssetKind, AssetSource, Project, ProjectStatus, Scene
from app.services import runtime_settings, storage
from app.services.jobs import JobContext
from app.video import renderer
from app.video.motion import Cancelled


def project_settings(project: Project) -> dict:
    base = default_project_settings(project.settings.get("style", "moderno") if project.settings else "moderno")
    merged = {**base, **(project.settings or {})}
    for k in ("watermark", "end_card"):
        merged[k] = {**base[k], **((project.settings or {}).get(k) or {})}
    return merged


def apply_script(db: Session, project: Project, script: dict, cfg: dict | None) -> None:
    s = project_settings(project)
    tcfg = cfg or {}
    transition = tcfg.get("transition") or STYLE_PRESETS.get(s["style"], {}).get("transition", "fade")
    motion_default = tcfg.get("motion") or STYLE_PRESETS.get(s["style"], {}).get("motion", "zoom_in")
    anim = tcfg.get("text_animation") or STYLE_PRESETS.get(s["style"], {}).get("animation", "fade")
    motions = [motion_default, "zoom_out", "pan_left", "zoom_in", "pan_right", "zoom_in_left"]
    for sc in list(project.scenes):
        db.delete(sc)
    db.flush()
    project.scenes = []
    for i, sd in enumerate(script["scenes"]):
        project.scenes.append(Scene(
            position=i, role=sd["role"], title=sd["title"], subtitle=sd.get("subtitle", ""),
            narration=sd["narration"], image_prompt=sd["image_prompt"], duration=sd["duration"],
            transition=transition, motion=motions[i % len(motions)], text_animation=anim,
            text_position="center" if sd["role"] in ("hook", "cta", "offer") else "top",
        ))
    project.script = {k: v for k, v in script.items() if k != "scenes"}
    end = dict(s["end_card"])
    if not end.get("headline"):
        end["headline"] = script.get("cta", "")
    project.settings = {**(project.settings or {}), "end_card": end}


def run_script(db: Session, project: Project, ctx: JobContext) -> dict:
    ai = runtime_settings.get_section(db, "ai")
    s = project_settings(project)
    cfg = project.template.config if project.template else None
    ctx.progress(0.1, "Analisando informações da empresa", force=True)
    ctx.log(f"Gerando roteiro (provedor: {ai['llm_provider']}, modelo: {ai['ollama_model']})")
    script, notes = generate_script(project.company or {}, s, cfg, ai)
    for n in notes:
        ctx.log(n)
    ctx.progress(0.8, "Montando cenas", force=True)
    apply_script(db, project, script, cfg)
    project.status = ProjectStatus.ready
    db.commit()
    ctx.log(f"Roteiro com {len(script['scenes'])} cenas gerado por {script.get('engine')}")
    return {"engine": script.get("engine"), "scenes": len(script["scenes"]), "notes": notes}


def _image_size(s: dict) -> tuple[int, int]:
    return resolution(s["format"], "1080p")


def generate_images(db: Session, project: Project, ctx: JobContext, scene_ids: list[str] | None, force: bool,
                    p0: float = 0.0, p1: float = 1.0) -> list[str]:
    ai = runtime_settings.get_section(db, "ai")
    s = project_settings(project)
    w, h = _image_size(s)
    w, h = int(w * 1.25), int(h * 1.25)
    style_hint = (project.template.config.get("image_style") if project.template else "") or ""
    targets = [sc for sc in project.scenes
               if (scene_ids and str(sc.id) in scene_ids) or (not scene_ids and (force or sc.image_asset_id is None))]
    warnings: list[str] = []
    for i, sc in enumerate(targets):
        if ctx.is_cancelled():
            raise Cancelled()
        ctx.progress(p0 + (p1 - p0) * i / max(len(targets), 1), f"Gerando imagem {i + 1}/{len(targets)}", force=True)
        tmp = get_settings().temp_dir / f"img_{uuid.uuid4().hex}"
        prompt = sc.image_prompt or sc.title or project.name
        path, engine, warn = generate_scene_image(prompt, tmp, w, h, ai, s["palette"], style_hint, ctx.is_cancelled)
        if warn and warn not in warnings:
            warnings.append(warn)
            ctx.log(warn)
        mime = "image/png" if path.suffix == ".png" else "image/jpeg"
        stored = storage.store_generated(path, project.owner_id, path.suffix, mime)
        asset = storage.create_asset(
            db, stored, owner_id=project.owner_id, project_id=project.id,
            kind=AssetKind.image, source=AssetSource.ai if engine != "procedural" else AssetSource.generated,
            name=f"{project.name} · cena {sc.position + 1}", meta={"engine": engine, "prompt": prompt},
        )
        sc.image_asset_id = asset.id
        db.commit()
        ctx.log(f"Imagem da cena {sc.position + 1} gerada ({engine})")
    return warnings


def _narr_signature(text: str, provider: str, gender: str, speed: float) -> str:
    return hashlib.sha256(f"{text}|{provider}|{gender}|{speed:.2f}".encode()).hexdigest()


def generate_narration(db: Session, project: Project, ctx: JobContext, force: bool = False,
                       p0: float = 0.0, p1: float = 1.0) -> list[str]:
    ai = runtime_settings.get_section(db, "ai")
    s = project_settings(project)
    provider = s.get("tts_provider") or ai["tts_provider"]
    gender = s.get("voice_gender", "female")
    speed = float(s.get("voice_speed", 1.0))
    warnings: list[str] = []
    scenes = [sc for sc in project.scenes if sc.narration.strip()]
    for i, sc in enumerate(scenes):
        if ctx.is_cancelled():
            raise Cancelled()
        sig = _narr_signature(sc.narration, provider, gender, speed)
        if not force and sc.narration_asset_id and sc.narration_signature == sig:
            continue
        ctx.progress(p0 + (p1 - p0) * i / max(len(scenes), 1), f"Narrando cena {i + 1}/{len(scenes)}", force=True)
        tmp = get_settings().temp_dir / f"tts_{uuid.uuid4().hex}.wav"
        dur, used, warns = tts.synthesize(sc.narration, tmp, gender, speed, provider, ai)
        for w_ in warns:
            if w_ not in warnings:
                warnings.append(w_)
                ctx.log(w_)
        stored = storage.store_generated(tmp, project.owner_id, ".wav", "audio/wav")
        old = sc.narration_asset
        asset = storage.create_asset(
            db, stored, owner_id=project.owner_id, project_id=project.id, kind=AssetKind.audio,
            source=AssetSource.generated, name=f"Narração cena {sc.position + 1}", in_library=False,
            meta={"provider": used, "voice": VOICES.get(used, {}).get(gender), "speed": speed},
        )
        sc.narration_asset_id = asset.id
        sc.narration_duration = dur
        sc.narration_signature = sig
        if old is not None:
            storage.delete_asset_file(old)
            db.delete(old)
        db.commit()
        ctx.log(f"Narração da cena {sc.position + 1}: {dur:.1f}s ({used})")
    for sc in project.scenes:
        if not sc.narration.strip() and sc.narration_asset_id:
            sc.narration_asset_id, sc.narration_duration, sc.narration_signature = None, None, None
    db.commit()
    return warnings


def ensure_system_music(db: Session, mood: str) -> Asset | None:
    if mood not in music_gen.MOODS:
        return None
    for a in db.query(Asset).filter(Asset.source == AssetSource.system, Asset.kind == AssetKind.music).all():
        if (a.meta or {}).get("mood") == mood and storage.abs_path(a.storage_path).exists():
            return a
    tmp = get_settings().temp_dir / f"music_{mood}_{uuid.uuid4().hex}.wav"
    music_gen.generate(mood, tmp, seconds=64)
    stored = storage.store_generated(tmp, None, ".wav", "audio/wav")
    from app.core.catalog import MUSIC_MOODS

    asset = storage.create_asset(db, stored, owner_id=None, kind=AssetKind.music, source=AssetSource.system,
                                 name=f"Trilha {MUSIC_MOODS.get(mood, mood)}", meta={"mood": mood, "license": "CC0"})
    db.commit()
    return asset


def _asset_path(db: Session, asset_id, owner_id) -> Path | None:
    if not asset_id:
        return None
    try:
        a = db.get(Asset, uuid.UUID(str(asset_id)))
    except ValueError:
        return None
    if a is None or (a.owner_id is not None and a.owner_id != owner_id):
        return None
    p = storage.abs_path(a.storage_path)
    return p if p.exists() else None


def build_plan(db: Session, project: Project, quality: str) -> renderer.RenderPlan:
    s = project_settings(project)
    rcfg = runtime_settings.get_section(db, "render")
    company = project.company or {}
    scenes = []
    for sc in project.scenes:
        img = _asset_path(db, sc.image_asset_id, project.owner_id)
        if img is None:
            raise RuntimeError(f"cena {sc.position + 1} sem imagem")
        narr = _asset_path(db, sc.narration_asset_id, project.owner_id) if s["narration_enabled"] else None
        scenes.append(renderer.ScenePlan(
            id=str(sc.id), image=img, duration=sc.duration, transition=sc.transition, motion=sc.motion, fit=sc.fit,
            title=sc.title, subtitle=sc.subtitle, text_animation=sc.text_animation, text_position=sc.text_position,
            narration_text=sc.narration, caption_override=sc.caption_override,
            narration_audio=narr, narration_duration=sc.narration_duration if narr else None,
        ))
    music = None
    if s.get("music_asset_id"):
        music = _asset_path(db, s["music_asset_id"], project.owner_id)
    elif s.get("music_mood") and s["music_mood"] != "none":
        a = ensure_system_music(db, s["music_mood"])
        music = storage.abs_path(a.storage_path) if a else None
    narration_track = None
    if s["narration_enabled"] and s.get("narration_mode") == "upload":
        narration_track = _asset_path(db, s.get("narration_asset_id"), project.owner_id)
    end = s["end_card"]
    lines = []
    phone = company.get("whatsapp") or company.get("phone")
    if end.get("show_phone") and phone:
        lines.append(("WhatsApp " if company.get("whatsapp") else "Tel. ") + str(phone))
    if end.get("show_instagram") and company.get("instagram"):
        lines.append("@" + str(company["instagram"]).lstrip("@"))
    if end.get("show_address") and company.get("address"):
        lines.append(str(company["address"]))
    wm = s["watermark"]
    logo = _asset_path(db, s.get("logo_asset_id"), project.owner_id)
    return renderer.RenderPlan(
        scenes=scenes, format=s["format"], quality=quality, fps=int(rcfg["fps"]),
        target_duration=float(s["duration"]), fit_duration=bool(s.get("fit_duration", True)),
        font=s["font"], palette=s["palette"], subtitles=bool(s["subtitles_enabled"]),
        subtitle_style=s["subtitle_style"], narration_enabled=bool(s["narration_enabled"]),
        narration_track=narration_track, music=music, music_volume=float(s["music_volume"]),
        watermark_text=(wm.get("text") or company.get("name") or "") if wm.get("enabled") and wm.get("type") == "text" else "",
        watermark_image=_asset_path(db, wm.get("asset_id") or s.get("logo_asset_id"), project.owner_id)
        if wm.get("enabled") and wm.get("type") == "image" else None,
        watermark_position=wm.get("position", "top_right"), watermark_opacity=float(wm.get("opacity", 0.6)),
        end_card=renderer.EndCardPlan(
            enabled=bool(end.get("enabled", True)), duration=float(end.get("duration", 4.0)), logo=logo,
            headline=end.get("headline") or (project.script or {}).get("cta", ""),
            company=company.get("name") or project.name, lines=lines,
        ),
        x264_preset=rcfg["x264_preset"], crf=int(rcfg["crf"]), fonts_dir=get_settings().fonts_dir,
    )


def run_render(db: Session, project: Project, ctx: JobContext, preview: bool) -> dict:
    s = project_settings(project)
    rcfg = runtime_settings.get_section(db, "render")
    if not project.scenes:
        raise RuntimeError("o projeto não possui cenas; gere ou adicione um roteiro")
    project.status = ProjectStatus.processing
    db.commit()
    warnings: list[str] = []
    ctx.progress(0.01, "Preparando imagens", force=True)
    if any(sc.image_asset_id is None or _asset_path(db, sc.image_asset_id, project.owner_id) is None
           for sc in project.scenes):
        for sc in project.scenes:
            if sc.image_asset_id and _asset_path(db, sc.image_asset_id, project.owner_id) is None:
                sc.image_asset_id = None
        warnings += generate_images(db, project, ctx, None, False, 0.0, 0.3)
    if s["narration_enabled"] and s.get("narration_mode") != "upload":
        warnings += generate_narration(db, project, ctx, False, 0.3, 0.4)
    db.refresh(project)
    quality = rcfg["preview_quality"] if preview else s.get("quality") or rcfg["default_quality"]
    plan = build_plan(db, project, quality)
    work = get_settings().temp_dir / f"render_{ctx.job_id.hex}"

    def prog(p: float, stage: str) -> None:
        ctx.progress(0.4 + 0.6 * p, stage)

    ctx.log(f"Renderizando {len(plan.scenes)} cenas em {quality} ({plan.format})")
    try:
        result = renderer.render(plan, work / "out.mp4", work, prog, ctx.is_cancelled)
        warnings += [w for w in result.warnings if w not in warnings]
        for w_ in result.warnings:
            ctx.log(w_)
        stored = storage.store_generated(result.path, project.owner_id, ".mp4", "video/mp4")
        kind_label = "Prévia" if preview else "Vídeo final"
        video = storage.create_asset(
            db, stored, owner_id=project.owner_id, project_id=project.id, kind=AssetKind.video,
            source=AssetSource.render, name=f"{project.name} · {kind_label}", in_library=not preview,
            meta={"quality": quality, "format": plan.format, "preview": preview, "timeline": result.timeline},
        )
        old_id = project.preview_asset_id if preview else None
        if preview:
            project.preview_asset_id = video.id
        else:
            project.output_asset_id = video.id
            if result.thumbnail:
                ts = storage.store_generated(result.thumbnail, project.owner_id, ".jpg", "image/jpeg")
                thumb = storage.create_asset(db, ts, owner_id=project.owner_id, project_id=project.id,
                                             kind=AssetKind.image, source=AssetSource.render,
                                             name=f"{project.name} · miniatura", in_library=False)
                project.thumbnail_asset_id = thumb.id
            project.status = ProjectStatus.completed
        if preview and project.status == ProjectStatus.processing:
            project.status = ProjectStatus.completed if project.output_asset_id else ProjectStatus.ready
        db.commit()
        if old_id:
            old = db.get(Asset, old_id)
            if old:
                storage.delete_asset_file(old)
                db.delete(old)
                db.commit()
        ctx.log(f"{kind_label} pronto: {result.duration:.1f}s, {result.width}x{result.height}")
        return {"asset_id": str(video.id), "duration": result.duration, "warnings": warnings,
                "width": result.width, "height": result.height}
    finally:
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
