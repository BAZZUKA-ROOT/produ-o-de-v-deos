import logging
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from celery.exceptions import SoftTimeLimitExceeded

import redis
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import Job, JobKind, JobStatus, Project, ProjectStatus
from app.services import jobs as job_service
from app.services import pipeline, runtime_settings
from app.video.motion import Cancelled
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

# Falhas de infraestrutura que justificam nova tentativa automática.
TRANSIENT_ERRORS = (httpx.TransportError, redis.ConnectionError, OperationalError, ConnectionError)

LABELS = {
    JobKind.script: "Roteiro",
    JobKind.images: "Imagens",
    JobKind.narration: "Narração",
    JobKind.preview: "Prévia",
    JobKind.render: "Renderização",
    JobKind.model_pull: "Download de modelo",
}


def _finish(job_id: uuid.UUID, status: JobStatus, stage: str, *, error: str | None = None, result: dict | None = None,
            project_status: ProjectStatus | None = None, notify: tuple[str, str, str] | None = None) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = status
        job.stage = stage
        job.finished_at = datetime.now(timezone.utc)
        if status == JobStatus.completed:
            job.progress = 100.0
        if error:
            job.error = error[:5000]
        if result is not None:
            job.result = result
            if result.get("asset_id"):
                job.output_asset_id = uuid.UUID(result["asset_id"])
        if job.project_id and project_status:
            p = db.get(Project, job.project_id)
            if p:
                p.status = project_status
        if notify and job.user_id:
            title, msg, level = notify
            link = f"/projetos/{job.project_id}/editor" if job.project_id else None
            job_service.notify(db, job.user_id, title, msg, level, link)
        db.commit()
    finally:
        db.close()
    try:
        job_service.get_redis().delete(job_service._cancel_key(job_id))
    except Exception:  # noqa: BLE001
        pass


def _execute(db, job: Job, ctx: job_service.JobContext) -> dict:
    project = db.get(Project, job.project_id) if job.project_id else None
    if job.kind == JobKind.model_pull:
        return _pull_model(db, job, ctx)
    if project is None:
        raise RuntimeError("projeto não encontrado")
    if job.kind == JobKind.script:
        return pipeline.run_script(db, project, ctx)
    if job.kind == JobKind.images:
        w = pipeline.generate_images(db, project, ctx, job.params.get("scene_ids"), bool(job.params.get("force")))
        return {"warnings": w}
    if job.kind == JobKind.narration:
        return {"warnings": pipeline.generate_narration(db, project, ctx, bool(job.params.get("force")))}
    if job.kind in (JobKind.render, JobKind.preview):
        return pipeline.run_render(db, project, ctx, preview=job.kind == JobKind.preview)
    raise RuntimeError(f"tipo de tarefa desconhecido: {job.kind}")


def _pull_model(db, job: Job, ctx: job_service.JobContext) -> dict:
    ai = runtime_settings.get_section(db, "ai")
    model = job.params.get("model") or ai["ollama_model"]
    url = ai["ollama_url"].rstrip("/") + "/api/pull"
    ctx.log(f"Baixando modelo {model} no Ollama")
    import json

    with httpx.Client(timeout=None) as c, c.stream("POST", url, json={"model": model, "stream": True}) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if ctx.is_cancelled():
                raise Cancelled()
            if not line:
                continue
            data = json.loads(line)
            if data.get("error"):
                raise RuntimeError(data["error"])
            total, done = data.get("total"), data.get("completed")
            ctx.progress((done / total) if total and done else 0.0, data.get("status", "baixando")[:100])
    return {"model": model}


@celery_app.task(bind=True, name="app.workers.tasks.run_job", max_retries=5)
def run_job(self, job_id: str) -> dict | None:
    jid = uuid.UUID(job_id)
    db = SessionLocal()
    ctx = job_service.JobContext(job_id)
    try:
        job = db.get(Job, jid)
        if job is None or job.status in (JobStatus.cancelled, JobStatus.completed):
            return None
        if ctx.is_cancelled():
            _finish(jid, JobStatus.cancelled, "Cancelado")
            return None
        job.status = JobStatus.running
        job.attempts += 1
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.stage = "Iniciando"
        db.commit()
        ctx.log(f"Tarefa {LABELS.get(job.kind, job.kind)} iniciada (tentativa {job.attempts})")
        result = _execute(db, job, ctx)
        ctx.flush()
        label = LABELS.get(job.kind, "Tarefa")
        final_project = None
        if job.kind == JobKind.render:
            final_project = ProjectStatus.completed
        _finish(jid, JobStatus.completed, "Concluído", result=result, project_status=final_project,
                notify=(f"{label} concluída", _project_name(jid), "success")
                if job.kind in (JobKind.render, JobKind.preview, JobKind.script) else None)
        return result
    except (Cancelled, SoftTimeLimitExceeded) as exc:
        db.rollback()
        ctx.log("Tarefa cancelada" if isinstance(exc, Cancelled) else "Tempo limite excedido")
        ctx.flush()
        timeout = isinstance(exc, SoftTimeLimitExceeded)
        _finish(jid, JobStatus.failed if timeout else JobStatus.cancelled,
                "Tempo limite excedido" if timeout else "Cancelado",
                error="tempo limite excedido" if timeout else None, project_status=_restore_status(jid))
        return None
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job = db.get(Job, jid)
        max_retries = int(runtime_settings.get_section(db, "render")["max_retries"])
        transient = isinstance(exc, TRANSIENT_ERRORS)
        ctx.log(f"Erro: {exc}")
        ctx.flush()
        if transient and job and job.attempts <= max_retries:
            job.status = JobStatus.queued
            job.stage = f"Nova tentativa em breve ({job.attempts}/{max_retries})"
            db.commit()
            raise self.retry(exc=exc, countdown=min(60, 10 * 2 ** (job.attempts - 1)))
        job_service.log_error(f"worker.{job.kind.value if job else 'job'}", str(exc), exc,
                              {"job_id": job_id, "project_id": str(job.project_id) if job and job.project_id else None})
        _finish(jid, JobStatus.failed, "Falhou", error=str(exc), project_status=ProjectStatus.failed
                if job and job.kind in (JobKind.render,) else _restore_status(jid),
                notify=(f"{LABELS.get(job.kind, 'Tarefa') if job else 'Tarefa'} falhou", str(exc)[:300], "error"))
        return None
    finally:
        db.close()


def _project_name(job_id: uuid.UUID) -> str:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        p = db.get(Project, job.project_id) if job and job.project_id else None
        return p.name if p else ""
    finally:
        db.close()


def _restore_status(job_id: uuid.UUID) -> ProjectStatus | None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        p = db.get(Project, job.project_id) if job and job.project_id else None
        if p is None:
            return None
        if p.output_asset_id:
            return ProjectStatus.completed
        return ProjectStatus.ready if p.scenes else ProjectStatus.draft
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.cleanup_temp")
def cleanup_temp() -> int:
    db = SessionLocal()
    try:
        hours = int(runtime_settings.get_section(db, "storage")["temp_retention_hours"])
    finally:
        db.close()
    cutoff = time.time() - hours * 3600
    removed = 0
    for p in get_settings().temp_dir.iterdir():
        try:
            if p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
                removed += 1
        except OSError:
            pass
    return removed


@celery_app.task(name="app.workers.tasks.reap_stale_jobs")
def reap_stale_jobs() -> int:
    """Marca como falhas tarefas 'running' sem atividade (ex.: worker reiniciado)."""
    limit = get_settings().render_soft_time_limit + 900
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=limit)
    db = SessionLocal()
    try:
        stale = db.query(Job).filter(Job.status.in_((JobStatus.running, JobStatus.cancelling)),
                                     Job.started_at < cutoff).all()
        for j in stale:
            j.status = JobStatus.failed
            j.error = "tarefa interrompida (worker reiniciado ou travado)"
            j.finished_at = datetime.now(timezone.utc)
        db.commit()
        return len(stale)
    finally:
        db.close()
