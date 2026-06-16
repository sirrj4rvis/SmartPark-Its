<div align="center">

# 🅿️ SmartPark ITS — Real-Time Smart Parking Platform

### A production-grade **Intelligent Transport System (ITS)** — real-time availability, dynamic pricing, occupancy forecasting, full observability, and a complete CI/CD pipeline.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Socket.IO](https://img.shields.io/badge/WebSockets-Socket.IO-010101?style=for-the-badge&logo=socketdotio&logoColor=white)](https://socket.io/)
[![Celery](https://img.shields.io/badge/Celery-Tasks-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-pytest%20%E2%9C%93-success?style=for-the-badge)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

</div>

---

## 📖 Overview

**SmartPark ITS** is an end-to-end smart-parking platform: drivers discover live slot availability, get **demand-based dynamic pricing**, reserve or book a slot (with a strict concurrency guarantee), and receive a **QR-verifiable digital receipt**. Admins get a **real-time analytics dashboard**, slot management, and full system auditing. The whole thing is observable, tested, containerized, and shipped through CI/CD.

It is intentionally engineered to production standards — not as a CRUD demo, but as something you can defend, end-to-end, in a senior-level system-design conversation.

---

## ✨ Key Capabilities

| Area | What it does |
|------|--------------|
| ⚡ **Real-time** | Slot status pushed to every client over **WebSockets** (Socket.IO + Redis pub/sub), with graceful polling fallback. |
| 🔒 **Concurrency-safe booking** | Double-booking is **impossible by construction** — a partial unique DB index + row-level locking + transactional writes (proven by a 50-thread Postgres test). |
| 🗺️ **Geospatial map** | Multi-lot support with coordinates; a live **Leaflet** map shows availability per lot and finds the **nearest lot** to your location (Haversine; PostGIS-ready). |
| 💳 **Payments** | **Razorpay** checkout for the parking fee, with HMAC-SHA256 **webhook signature verification** and **idempotency** (mock provider for local dev). |
| 📷 **ANPR** | **License-plate recognition** (OpenCV detection + Tesseract OCR) auto-fills the vehicle number from a photo. |
| 💸 **Dynamic pricing** | Surge multiplier ramps with live occupancy (configurable threshold & cap). |
| 🧠 **Occupancy forecasting** | Exponentially-weighted hour-of-week demand model → 24h forecast + cheapest-slot recommendations. |
| ⏳ **Reservations** | Hold a slot with a TTL; a **Celery beat** job auto-releases expired holds. |
| 🧾 **QR receipts** | Each completed session yields a scannable, verifiable receipt. |
| 📊 **Analytics** | Revenue trend, peak-hour histogram, vehicle mix, live occupancy (Chart.js). |
| 🔭 **Observability** | Structured JSON logs w/ request IDs, Sentry, Prometheus `/metrics`, `/healthz`, **Grafana dashboards** + alert rules. |
| 🔌 **REST API** | Versioned `/api/v1`, JWT-authenticated, self-documenting **Swagger UI**. |
| 🛡️ **Hardened auth** | Hashing, CSRF, rate limiting, login lockout, secure cookies, 12-factor config. |
| ✅ **Tested + load-tested** | pytest unit + integration (incl. a real-Postgres concurrency proof), **~88% coverage** gate in CI, **Locust** load tests (0% errors, p95 43ms @ 80 users). |

---

## 🏛️ Architecture

```
                      ┌────────────────────────── Clients ──────────────────────────┐
                      │   Browser (Jinja + Socket.IO)        REST consumers (JWT)     │
                      └───────────────┬───────────────────────────────┬──────────────┘
                                      │ HTTP / WebSocket               │ /api/v1 (JWT)
                          ┌───────────▼───────────────────────────────▼───────────┐
                          │                 Flask (app factory)                    │
                          │  Blueprints: public · auth · user · admin · api · ops  │
                          │  Extensions: SQLAlchemy · Migrate · WTF/CSRF · Limiter │
                          │              · Caching · SocketIO · JWT                 │
                          │  Services:  booking · slot · pricing · forecast · …    │
                          └───┬───────────────┬───────────────┬──────────────┬─────┘
                              │               │               │              │
                       ┌──────▼─────┐  ┌──────▼─────┐  ┌──────▼─────┐  ┌─────▼──────┐
                       │ PostgreSQL │  │   Redis    │  │  Celery    │  │  Sentry /  │
                       │ (+Alembic) │  │ cache·pub  │  │ worker+beat│  │ Prometheus │
                       └────────────┘  └────────────┘  └────────────┘  └────────────┘
```

**Layout**
```
app/
├── __init__.py            # application factory
├── extensions.py          # db, migrate, csrf, cache, limiter, socketio
├── models.py              # ORM: User, ParkingSlot, Booking (+ partial unique indexes)
├── security.py            # auth, guards, lockout
├── logging_config.py      # structured JSON logs + request IDs
├── observability.py       # Sentry, Prometheus, /healthz, /metrics
├── realtime.py            # Socket.IO events + broadcast
├── tasks.py               # Celery tasks + beat schedule
├── cli.py                 # `flask seed`, `flask create-admin`
├── services/              # booking · slot · pricing · analytics · forecast · notification
└── blueprints/            # public · auth · user · admin · api/v1 · errors
wsgi.py · celery_worker.py · config.py · migrations/ · tests/ · docker-compose.yml
```

---

## 🚀 Quick Start

### Option A — Full stack with Docker Compose (Postgres + Redis + worker + beat)
```bash
# A SECRET_KEY is required (compose refuses to start without one — by design).
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")   # Windows PowerShell: $env:SECRET_KEY=...
docker compose up --build
# → http://localhost:5000   (admin: admin@parking.com / admin123)
```
The web container runs Gunicorn with a **gevent WebSocket worker** (native
WebSockets + high connection concurrency); emits fan out across workers via the
Redis message queue.

### Option B — Local (zero infra; SQLite + in-memory cache)
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app wsgi seed          # create schema + demo data
python wsgi.py                 # → http://localhost:5000
```

> With no `DATABASE_URL`/`REDIS_URL` set, the app falls back to SQLite + in-memory cache so it boots with **zero configuration**. Set them (see [.env.example](.env.example)) to use Postgres/Redis. In **production** (`FLASK_ENV=production`) the app *refuses* to start without a real `DATABASE_URL` and `REDIS_URL` — it never silently runs on SQLite.

### Deploy it free
Ship to a public URL on free tiers (Render + Neon + Upstash) — see **[DEPLOY_FREE.md](DEPLOY_FREE.md)**.

---

## 🔌 API & Real-Time

- **Swagger UI:** `/api/docs` · **OpenAPI spec:** `/api/v1/openapi.json`
- **Auth:** `POST /api/v1/auth/login` → `{ access_token }`, then `Authorization: Bearer <token>`

```bash
TOKEN=$(curl -s localhost:5000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@parking.com","password":"admin123"}' | jq -r .access_token)

curl localhost:5000/api/v1/slots
curl -X POST localhost:5000/api/v1/bookings -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"slot_id":1,"vehicle_number":"KA01AB1234"}'
```

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/slots` | GET | – | Live availability + counts |
| `/api/v1/slots/recommend` | GET | – | Cheapest available slots |
| `/api/v1/forecast` | GET | – | 24h occupancy forecast |
| `/api/v1/bookings` | GET/POST | JWT | List / create bookings |
| `/api/v1/bookings/{id}/exit` | POST | JWT | Exit + receipt |
| `/api/v1/analytics` | GET | JWT (admin) | KPIs + chart series |
| `/api/v1/lots` · `/api/v1/lots/nearest` | GET | – | Lots w/ availability · nearest to a point |
| `/api/v1/anpr` | POST | – | License-plate recognition (multipart image) |
| `/api/v1/auth/register` · `/auth/login` | POST | – | Get a JWT |
| `/api/webhooks/razorpay` | POST | HMAC | Payment webhook (signature-verified) |
| `/healthz` · `/metrics` | GET | – | Liveness · Prometheus |

---

## 🔐 The Concurrency Guarantee (interview-ready)

Two drivers tapping "Book A1" at the same instant **cannot** both succeed:

1. `SELECT … FOR UPDATE` locks the slot row (PostgreSQL), serializing contenders.
2. A **partial unique index** is the hard backstop:
   ```sql
   CREATE UNIQUE INDEX uq_active_booking_per_slot
       ON bookings (slot_id) WHERE status = 'active';
   ```
   The second writer gets an `IntegrityError`, which the service translates into a clean *"that slot was just taken."*

This is proven by a test that bypasses the service layer and asserts the **database itself** rejects a second active booking (`tests/test_booking.py::test_db_constraint_blocks_two_active_bookings`).

---

## 📈 Scalability & Production Readiness

Engineered to scale horizontally by configuration, not rewrites:

| Concern | How it's handled |
|---------|------------------|
| **WSGI / WebSockets** | Gunicorn **gevent WebSocket worker** — native WebSockets + thousands of connections/worker. `WEB_CONCURRENCY` workers fan out via the Redis message queue (use a sticky-session LB across instances). |
| **DB connection pool** | Tuned Postgres pool (`pool_size`/`max_overflow`/`pool_timeout` + `pre_ping`/`recycle`), env-tunable; pair with a pooled endpoint / PgBouncer at scale. |
| **Read-heavy availability** | Short-TTL Redis cache on the hot availability read, invalidated in the service layer on every booking / reservation / slot change. |
| **Fail-fast config** | In production the app refuses to boot without `DATABASE_URL` + `REDIS_URL` and rejects a SQLite fallback or an insecure `SECRET_KEY` — no silent data-loss misconfigs. |
| **Background jobs** | Celery tasks with retry/back-off + broker reconnection; **RedBeat** (Redis-backed) scheduler survives restarts. |
| **Static assets** | Served by **WhiteNoise** with long-lived cache headers, off the request workers. |
| **Health** | `/healthz` verifies Postgres (hard) and Redis (reported) so a load balancer sees real dependency state. |

Sizing guidance and a free-tier deploy are in **[DEPLOY_FREE.md](DEPLOY_FREE.md)**.

---

## ✅ Quality, Testing & Observability

```bash
pytest                                   # unit + integration, coverage gate (≥85%)
locust -f loadtest/locustfile.py ...     # load test (see loadtest/README.md)
docker compose up                        # app + db + redis + worker + beat + prometheus + grafana
```
- **~88% coverage**; suite covers auth/lockout, the concurrency guarantee, pricing,
  forecasting, geo, payments (signature + idempotency), ANPR, the REST API, and admin.
- **Integration tests** spin a real PostgreSQL (testcontainers) and prove 50 concurrent
  bookers racing one slot → exactly one wins.
- **Load test baseline:** 0% errors, p95 43ms @ 80 users ([loadtest/README.md](loadtest/README.md)).
- **Observability:** Grafana dashboards + Prometheus alert rules under [`monitoring/`](monitoring/)
  (Grafana :3000, Prometheus :9090 via compose).
- **Design docs:** [system design](docs/architecture.md) + [ADRs](docs/adr/).
- The **Jenkins** pipeline gates on tests, then SonarCloud → Trivy → Docker → push → deploy:

```
GitHub → Tests (pytest, gated) → SonarCloud → Trivy → Docker build → DockerHub → Render
```

---

## 🛠️ Tech Stack

**Backend** Python 3.11 · Flask 3 (app factory + blueprints) · SQLAlchemy 2 · Alembic
**Data/Infra** PostgreSQL · Redis · Celery (worker + beat)
**Realtime/API** Flask-SocketIO (gevent WebSocket worker) · Flask-JWT-Extended · OpenAPI/Swagger
**Security** Werkzeug hashing · Flask-WTF (CSRF) · Flask-Limiter · login lockout
**Payments / Vision** Razorpay (HMAC webhooks) · OpenCV + Tesseract (ANPR)
**Geo** Leaflet + OpenStreetMap · Haversine (PostGIS-ready)
**Observability** structured logging · Sentry · Prometheus · Grafana
**Testing** pytest · pytest-cov · testcontainers · Locust
**Frontend** Jinja2 · vanilla JS · Chart.js · Socket.IO client · Space Grotesk/DM Sans dark UI
**Serving/Scale** Gunicorn (gevent WebSocket worker) · WhiteNoise · RedBeat · tuned SQLAlchemy pool
**DevOps** Docker (multi-stage, non-root) · docker-compose · Jenkins · SonarCloud · Trivy · Render

---

## 📜 License

MIT — see [LICENSE](LICENSE).

<div align="center"><sub>Built as a production-grade Intelligent Transport System · © 2026</sub></div>
