from __future__ import annotations

import os


CELERY_AVAILABLE = False
celery_app = None

try:
    from celery import Celery

    CELERY_AVAILABLE = True
    celery_app = Celery(
        "stock_ming_command_center_3",
        broker=os.getenv("COMMAND_CENTER_REDIS_URL", "redis://localhost:6379/0"),
        backend=os.getenv("COMMAND_CENTER_REDIS_URL", "redis://localhost:6379/0"),
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
