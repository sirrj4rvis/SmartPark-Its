# Deploying SmartPark ITS for Free

This guide ships SmartPark to a public URL on **free tiers** with managed Postgres
and Redis. It comfortably handles a portfolio / pilot load (tens–hundreds of
concurrent users). For true high concurrency, see [Scaling Up](#scaling-up) at the end.

> **Cost: ₹0.** Hosting: Render (web) · Neon (Postgres) · Upstash (Redis).

---

## 0. One-time: push your code to GitHub

The app deploys from your GitHub repo. Make sure it's pushed (see the repo's
push instructions). Render watches the repo and auto-deploys on every push.

---

## 1. Postgres — Neon (free, includes a connection pooler)

1. Create a project at <https://neon.tech> → it gives you a database.
2. Copy the **pooled** connection string (Neon labels it *"Pooled connection"*).
   It looks like:
   ```
   postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname?sslmode=require
   ```
3. SmartPark uses the `psycopg` (v3) driver, so rewrite the scheme to:
   ```
   postgresql+psycopg://user:pass@ep-xxx-pooler.region.aws.neon.tech/dbname?sslmode=require
   ```
   (The app also auto-normalizes `postgres://` / `postgresql://`, but setting it
   explicitly is clearest.) This is your **`DATABASE_URL`**.

> The pooled endpoint **is** your free PgBouncer — keep `DB_POOL_SIZE` small (5).

## 2. Redis — Upstash (free, serverless)

1. Create a database at <https://upstash.com> (Redis).
2. Copy the connection string in `redis://...` form (Upstash shows a
   `rediss://` TLS URL — that works too). This single URL is used for cache,
   rate-limit storage, the Socket.IO message queue, and the Celery broker.
   This is your **`REDIS_URL`**.

## 3. Web app — Render (free, Docker)

The repo already has [`render.yaml`](render.yaml). Easiest path:

1. <https://render.com> → **New → Blueprint** → connect your GitHub repo.
   Render reads `render.yaml` and provisions the web service.
2. Or **New → Web Service → Docker** pointing at the repo (Render uses the
   [`Dockerfile`](Dockerfile)).
3. Set these **environment variables** on the web service:

   | Key | Value |
   |-----|-------|
   | `FLASK_ENV` | `production` |
   | `SECRET_KEY` | a long random string (Render: *Generate*) |
   | `JWT_SECRET_KEY` | another random string |
   | `DATABASE_URL` | the Neon **pooled** URL from step 1 |
   | `REDIS_URL` | the Upstash URL from step 2 |
   | `SESSION_COOKIE_SECURE` | `1` |
   | `AUTO_SEED` | `1` (creates schema + demo admin/slots on first boot) |
   | `WEB_CONCURRENCY` | `1` *(important on free tier — see note)* |
   | `DB_POOL_SIZE` | `5` |
   | `METRICS_ENABLED` | `1` |

4. Deploy. Render uses the container's `/healthz` as the health check.
   First boot seeds the demo admin: **admin@parking.com / admin123** — change it.

> **Why `WEB_CONCURRENCY=1` on free?** A single instance with one gevent worker
> owns all WebSocket connections, so you don't need a sticky load balancer.
> The Dockerfile defaults to 4 workers (for paid multi-core instances); override
> it to `1` for the 512 MB free instance.

---

## 4. Expired-hold sweep without paid Celery (optional)

Celery worker/beat need a paid Render plan. You usually **don't need them**:
an expired reservation is released automatically the next time anyone touches
that slot (`booking_service._release_if_reservation_expired`). The only gap is
slots nobody touches.

If you want a guaranteed periodic sweep for free, trigger it from an external
cron (e.g. <https://cron-job.org> or a GitHub Actions schedule) hitting a small
token-protected endpoint. Ask and this can be added — it's a few lines.

---

## 5. Verify

```bash
curl https://<your-app>.onrender.com/healthz       # {"status":"ok","checks":{"db":"ok","redis":"ok"}}
curl https://<your-app>.onrender.com/api/v1/slots
```
Open the site, register, book a slot, watch the live grid update over WebSockets.

---

## Free-tier caveats (be honest about these)

- **Cold starts:** the free Render web instance sleeps when idle; first request
  after idle takes ~30–60 s to wake.
- **RAM:** 512 MB — fine for one gevent worker.
- **Neon free** auto-suspends the DB when idle (adds to cold-start) and has
  storage/compute limits.
- **Upstash free** has a daily command quota — generous for a pilot.

---

## Scaling Up

When you outgrow free tier, the code is already built for it — no rewrites,
just configuration:

1. **More web throughput:** raise `WEB_CONCURRENCY` and run multiple instances.
   Put a **sticky-session** load balancer in front (Socket.IO handshake +
   polling fallback must hit the same worker). The Redis message queue already
   fans broadcasts across all workers/instances.
2. **Database:** a paid Postgres tier + the pooled endpoint (or a dedicated
   **PgBouncer**). Keep `(DB_POOL_SIZE + DB_MAX_OVERFLOW) × processes` under the
   server's `max_connections`.
3. **Background jobs:** enable the **Celery worker + beat** services (uncomment
   them in [`render.yaml`](render.yaml) / they're already in
   [`docker-compose.yml`](docker-compose.yml)). Beat uses RedBeat (Redis-backed,
   restart-safe).
4. **Static/CDN:** WhiteNoise already serves static with long cache headers; put
   a CDN in front for global edge caching.
