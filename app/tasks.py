"""
tasks.py — Celery tasks & beat schedule.

Background work:
  - sweep_reservations: release expired slot holds every minute.
  - reprice: recompute surge pricing periodically.
  - send_notification: async email/SMS delivery.

Celery is created with a Flask app context wrapper so tasks can use the ORM.
"""
from celery import Celery, shared_task

celery_app = Celery("smartpark")


def init_celery(app):
    celery_app.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config.get("CELERY_RESULT_BACKEND"),
        task_default_queue="smartpark",
        beat_schedule={
            "sweep-reservations": {"task": "app.tasks.sweep_reservations", "schedule": 60.0},
            "reprice-slots": {"task": "app.tasks.reprice", "schedule": 120.0},
        },
        timezone="UTC",
    )

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app


@shared_task(name="app.tasks.sweep_reservations")
def sweep_reservations():
    from .services import booking_service
    from .realtime import broadcast_slots

    released = booking_service.sweep_expired_reservations()
    if released:
        broadcast_slots()
    return released


@shared_task(name="app.tasks.reprice")
def reprice():
    from .services import pricing_service

    return pricing_service.reprice_all()


@shared_task(name="app.tasks.send_notification")
def send_notification(to: str, subject: str, body: str):
    # Plug a real provider (SES/Twilio) here. Logged for now.
    import logging

    logging.getLogger("smartpark.notify").info(f"NOTIFY {to}: {subject}")
    return True
