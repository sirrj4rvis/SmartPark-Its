"""
celery_worker.py — Celery entrypoint.

  Worker: celery -A celery_worker.celery worker --loglevel=info -Q smartpark
  Beat:   celery -A celery_worker.celery beat --loglevel=info
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.tasks import init_celery

flask_app = create_app()
celery = init_celery(flask_app)

# Ensure tasks are registered.
from app import tasks  # noqa: E402,F401
