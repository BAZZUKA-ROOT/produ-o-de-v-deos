"""Criação, acompanhamento, cancelamento de tarefas + notificações e log de erros."""

import logging
import time
import traceback
import uuid
from datetime import datetime, timezone

import redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import ACTIVE_JOB_STATUSES, ErrorLog, Job, JobKind, JobStatus, Notification, Project

log = logging.getLogger(__name__)
_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(get_settings().redis_url, decode_responses=True, socket_timeout=5)
    return _redis


def _cancel_key(job_id) -> str:
    return f"forja:job:{job_id}:cancel"


def notify(db: Session, user_id, title: str, message: str = "", level: str = "info", link: str | None = None) -> None:
    if user_id is None:
        return
    db.add(Notification(user_id=user_id, title=title[:200], message=message, level=level, link=link))


def log_error(source: str, message: str, exc: BaseException | None = None, context: dict | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(ErrorLog(
            source=source[:60], message=message[:5000],
            traceback="".join(traceback.format_exception(exc)) if exc else None,
            context=context or {},
        ))
        db.commit()
    except Exception:  # noqa: BLE001
        log.exception("falha ao gravar error_log")
        db.rollback()
    finally:
        db.close()


def active_job(db: Session, project_id, kinds: tuple[JobKind, ...] | None = None) -> Job | None:
    q = db.query(Job).filter(Job.project_id == project_id, Job.status.in_(ACTIVE_JOB_STATUSES))
    if kinds:
        q = q.filter(Job.kind.in_(kinds))
    return q.order_by(Job.created_at.desc()).first()


def enqueue(db: Session, kind: JobKind, *, user_id=None, project: Project | None = None, params: dict | None = None) -> Job:
    from app.workers.celery_app import celery_app

    job = Job(kind=kind, user_id=user_id, project_id=project.id if project else None, params=params or {})
    db.add(job)
    db.commit()
    queue = "render" if kind in (JobKind.render, JobKind.preview, JobKind.images) else "default"
    settings = get_settings()
    if settings.celery_task_always_eager:
        from app.workers.tasks import run_job

        run_job.apply(args=[str(job.id)])
        db.refresh(job)
        return job
    res = celery_app.send_task("app.workers.tasks.run_job", args=[str(job.id)], queue=queue)
    job.celery_task_id = res.id
    db.commit()
    return job


def cancel(db: Session, job: Job) -> Job:
    if job.status not in ACTIVE_JOB_STATUSES:
        return job
    try:
        get_redis().set(_cancel_key(job.id), "1", ex=86400)
    except redis.RedisError:
        log.warning("redis indisponível ao cancelar job %s", job.id)
    if job.status == JobStatus.queued:
        job.status = JobStatus.cancelled
        job.stage = "Cancelado"
        job.finished_at = datetime.now(timezone.utc)
        if job.celery_task_id:
            try:
                from app.workers.celery_app import celery_app

                celery_app.control.revoke(job.celery_task_id)
            except Exception:  # noqa: BLE001
                pass
    else:
        job.status = JobStatus.cancelling
        job.stage = "Cancelando..."
    db.commit()
    return job


class JobContext:
    """Usado pelo worker para reportar progresso/logs com escrita no banco controlada."""

    def __init__(self, job_id: str):
        self.job_id = uuid.UUID(job_id)
        self._last_write = 0.0
        self._last_cancel_check = 0.0
        self._cancelled = False
        self._buffer: list[str] = []

    def _write(self, **fields) -> None:
        db = SessionLocal()
        try:
            job = db.get(Job, self.job_id)
            if job is None:
                return
            for k, v in fields.items():
                setattr(job, k, v)
            if self._buffer:
                job.logs = (job.logs or "") + "".join(self._buffer)
                self._buffer.clear()
            db.commit()
        finally:
            db.close()

    def log(self, msg: str) -> None:
        line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}\n"
        log.info("job %s: %s", self.job_id, msg)
        self._buffer.append(line)

    def progress(self, value: float, stage: str | None = None, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_write < 1.0:
            return
        self._last_write = now
        fields = {"progress": round(max(0.0, min(1.0, value)) * 100, 1)}
        if stage:
            fields["stage"] = stage[:120]
        self._write(**fields)

    def flush(self) -> None:
        self._write()

    def is_cancelled(self) -> bool:
        if self._cancelled:
            return True
        now = time.time()
        if now - self._last_cancel_check < 0.5:
            return False
        self._last_cancel_check = now
        try:
            self._cancelled = bool(get_redis().exists(_cancel_key(self.job_id)))
        except redis.RedisError:
            db = SessionLocal()
            try:
                job = db.get(Job, self.job_id)
                self._cancelled = bool(job and job.status == JobStatus.cancelling)
            finally:
                db.close()
        return self._cancelled
