import importlib
import os
import unittest


class WorkerCeleryAppConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            key: os.environ.get(key)
            for key in (
                "COMMAND_CENTER_REDIS_URL",
                "COMMAND_CENTER_CELERY_BROKER_URL",
                "COMMAND_CENTER_CELERY_RESULT_BACKEND",
            )
        }

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        import worker.celery_app as celery_app_module

        importlib.reload(celery_app_module)

    def test_split_celery_broker_and_backend_env_keeps_redis_fallback(self) -> None:
        os.environ["COMMAND_CENTER_REDIS_URL"] = "redis://127.0.0.1:6379/0"
        os.environ["COMMAND_CENTER_CELERY_BROKER_URL"] = "memory://"
        os.environ["COMMAND_CENTER_CELERY_RESULT_BACKEND"] = "cache+memory://"

        import worker.celery_app as celery_app_module

        importlib.reload(celery_app_module)

        self.assertTrue(celery_app_module.CELERY_AVAILABLE)
        self.assertIsNotNone(celery_app_module.celery_app)
        self.assertEqual(celery_app_module.celery_app.conf.broker_url, "memory://")
        self.assertEqual(celery_app_module.celery_app.conf.result_backend, "cache+memory://")

    def test_celery_uses_redis_url_for_broker_and_backend_by_default(self) -> None:
        os.environ["COMMAND_CENTER_REDIS_URL"] = "redis://127.0.0.1:6380/1"
        os.environ.pop("COMMAND_CENTER_CELERY_BROKER_URL", None)
        os.environ.pop("COMMAND_CENTER_CELERY_RESULT_BACKEND", None)

        import worker.celery_app as celery_app_module

        importlib.reload(celery_app_module)

        self.assertTrue(celery_app_module.CELERY_AVAILABLE)
        self.assertIsNotNone(celery_app_module.celery_app)
        self.assertEqual(celery_app_module.celery_app.conf.broker_url, "redis://127.0.0.1:6380/1")
        self.assertEqual(celery_app_module.celery_app.conf.result_backend, "redis://127.0.0.1:6380/1")
