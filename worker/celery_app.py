from __future__ import annotations

import os


CELERY_AVAILABLE = False
celery_app = None

_DEFAULT_REDIS_URL = "redis://localhost:6379/0"

try:
    from celery import Celery

    redis_url = os.getenv("COMMAND_CENTER_REDIS_URL", _DEFAULT_REDIS_URL)
    broker_url = os.getenv("COMMAND_CENTER_CELERY_BROKER_URL", redis_url)
    result_backend = os.getenv("COMMAND_CENTER_CELERY_RESULT_BACKEND", redis_url)

    CELERY_AVAILABLE = True
    celery_app = Celery(
        "stock_ming_command_center_3",
        broker=broker_url,
        backend=result_backend,
    )
    celery_app.conf.task_track_started = True
except Exception:
    CELERY_AVAILABLE = False
    celery_app = None


def task(name: str):
    def decorator(fn):
        if celery_app is None:
            return fn
        return celery_app.task(name=name)(fn)

    return decorator
