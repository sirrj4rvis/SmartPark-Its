# Load Testing — SmartPark ITS

Load tests use [Locust](https://locust.io/) to model realistic traffic:

- **AnonymousBrowser** (80% of users) — reads live availability (`/`, `/api/slots`,
  `/api/v1/slots`, recommendations, forecast, health).
- **ApiDriver** (20%) — registers via the JSON API, then books & exits through the
  JWT REST API, exercising the row-locking + unique-index booking path.

## Run

Start the app, then:

```bash
# Interactive UI at http://localhost:8089
locust -f loadtest/locustfile.py --host http://localhost:5000

# Headless with CSV + HTML report
locust -f loadtest/locustfile.py --host http://localhost:5000 \
    --headless -u 80 -r 20 -t 30s --csv loadtest/report --html loadtest/report.html
```

> For a true throughput benchmark, disable the per-IP rate limiter (single-source
> load otherwise measures the limiter): run the server with `RATELIMIT_ENABLED=0`.

## Baseline result (local dev)

Flask-SocketIO dev server, **SQLite**, single process, 80 concurrent users, 30s,
booking writes included:

| Metric | Value |
|--------|-------|
| Requests | 1,464 |
| **Failures** | **0 (0.00%)** |
| Throughput | ~50 req/s |
| Latency p50 / p95 / p99 | 7 ms / 43 ms / 160 ms |

`409` responses on booking are **expected** (the concurrency guard rejecting a
slot that's already taken) and are recorded as success.

> Production numbers are materially higher: gunicorn (multiple workers) + PostgreSQL
> (concurrent writers, no single-writer lock) + Redis-backed caching. SQLite serializes
> writers by design, so it is the floor, not the ceiling.
