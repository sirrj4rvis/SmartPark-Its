"""
wsgi.py — production entrypoint.

  Dev:   python wsgi.py           (uses socketio dev server)
  Prod:  gunicorn --worker-class gthread --threads 8 -w 1 -b 0.0.0.0:$PORT wsgi:application

On first boot (when AUTO_SEED=1) the schema is created and demo data inserted,
so a fresh Postgres/SQLite database works out of the box.
"""
import os

from app import create_app
from app.extensions import socketio

application = create_app()
app = application  # convenience alias

if os.environ.get("AUTO_SEED", "1") == "1":
    with application.app_context():
        from app.cli import seed_data

        try:
            seed_data()
        except Exception as exc:  # pragma: no cover
            application.logger.warning(f"auto-seed skipped: {exc}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = application.config.get("DEBUG", False)
    socketio.run(application, host="0.0.0.0", port=port, debug=debug, allow_unsafe_werkzeug=True)
