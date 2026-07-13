from __future__ import annotations

import os
from functools import wraps


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
        include=["worker.tasks_candidate"],
    )
    celery_app.conf.task_track_started = True
except Exception:
    CELERY_AVAILABLE = False
    celery_app = None


def task(name: str, **options):
    def decorator(fn):
        if celery_app is None:
            if options.get("bind") is True:
                @wraps(fn)
                def bound_fallback(payload=None, *args, **kwargs):
                    request = type(
                        "LocalFallbackRequest",
                        (),
                        {
                            "id": "",
                            "hostname": "",
                            "delivery_info": {},
                            "synthetic_fixture": True,
                        },
                    )()
                    bound = type("LocalFallbackTask", (), {"request": request})()
                    return fn(bound, payload, *args, **kwargs)

                return bound_fallback
            return fn
        return celery_app.task(name=name, **options)(fn)

    return decorator
