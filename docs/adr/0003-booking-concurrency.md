# ADR 0003 — Booking concurrency: pessimistic lock + partial unique index

**Status:** Accepted

## Context
The original "check status, then insert" booking flow had a textbook
time-of-check/time-of-use (TOCTOU) race: two requests could both see a slot as
free and both book it. Correctness here is non-negotiable — a slot is a
physical, exclusive resource.

## Decision
Defence in depth:
1. **`SELECT … FOR UPDATE`** locks the slot row (Postgres) so concurrent bookers
   serialize on it.
2. A **partial unique index** `uq_active_booking_per_slot (slot_id) WHERE
   status='active'` makes a second active booking *physically impossible* — the
   DB raises `IntegrityError`, which the service maps to a clean `409`.
3. A symmetric index enforces one active booking **per user**.

This is verified by an integration test (`test_integration_pg.py`) where 50
threads race for one slot and exactly one wins.

## Consequences
- Correctness is guaranteed by the database, not just application checks — it
  holds even under crashes, retries, or a buggy caller.
- Lock scope is a single row, so contention is naturally low and localized.
- SQLite ignores `FOR UPDATE`, but the unique index still enforces correctness
  there too (proven by a separate test).

## Alternatives considered
- **Optimistic concurrency (version column + retry):** viable, but adds retry
  loops and client-visible churn; pessimistic locking is simpler and contention
  is low (per-slot).
- **Application-level lock (Redis):** another moving part and a new failure mode;
  the DB already provides the guarantee atomically.
