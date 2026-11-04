from celery import Celery
from kombu import Queue

from app.core.config import get_settings

_s = get_settings()

celery_app = Celery("forja", broker=_s.broker, backend=_s.result_backend, include=["app.workers.tasks"])
celery_app.conf.update(
    task_default_queue="default",
    task_queues=(Queue("default"), Queue("render")),
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=_s.render_soft_time_limit + 300,
    task_soft_time_limit=_s.render_soft_time_limit,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    worker_max_tasks_per_child=50,
    task_always_eager=_s.celery_task_always_eager,
    timezone="UTC",
    beat_schedule={
        "cleanup-temp": {"task": "app.workers.tasks.cleanup_temp", "schedule": 3600.0},
        "reap-stale-jobs": {"task": "app.workers.tasks.reap_stale_jobs", "schedule": 600.0},
    },
)
