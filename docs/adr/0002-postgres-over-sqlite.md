# ADR 0002 — PostgreSQL over SQLite in production

**Status:** Accepted

## Context
The app shipped on SQLite. On Render's ephemeral filesystem the database file is
**wiped on every deploy/restart** (silent data loss), and SQLite serializes all
writers (one writer at a time) — unacceptable for concurrent bookings.

## Decision
Use **PostgreSQL** in production via `DATABASE_URL`, managed with **Alembic**
migrations. Keep a **SQLite fallback** for zero-config local dev and fast tests.
The config layer normalizes `postgres://` / `postgresql://` URLs to the
`postgresql+psycopg://` (psycopg v3) driver.

## Consequences
- Durable storage; true concurrent writers; real `SELECT … FOR UPDATE` locking.
- Access to partial unique indexes and (future) PostGIS geospatial indexing.
- Migrations give a safe, reviewable schema-change workflow.
- Two engines to support; mitigated by SQLAlchemy's abstraction and a UTC-coercion
  helper for SQLite's tz-naive datetimes.

## Alternatives considered
- **Stay on SQLite + persistent disk:** still single-writer; doesn't scale.
- **MySQL:** comparable, but Postgres has stronger partial-index and geospatial
  support, both of which this product uses.
