# ADR 0005 — Occupancy-based dynamic (surge) pricing

**Status:** Accepted

## Context
A flat per-hour rate ignores demand. Real parking/transport systems price by
scarcity to shape demand and capture value at peak. The "Intelligent" in ITS
should be reflected in pricing, and it makes a defensible design discussion.

## Decision
A **surge multiplier** scales the base rate with live occupancy: below a
configurable threshold the multiplier is 1.0; above it, it ramps linearly to a
configurable cap. The price applied to a booking is **frozen at booking time**
(`rate_applied`) so the user is never surprised at exit. Pricing is recomputed
synchronously on each book/exit and periodically by a Celery beat job.

```
surge = 1.0                                   if occupancy ≤ threshold
surge = 1.0 + (occ−thr)/(1−thr) · (cap−1.0)   otherwise        (clamped to cap)
```

## Consequences
- Transparent, predictable, and bounded by a cap (fairness).
- Parameters (`PRICING_SURGE_*`) are env-tunable per deployment.
- Frozen-at-booking pricing avoids bill shock and disputes.
- Linear ramp is a heuristic, not a learned elasticity model (see future work:
  ML-based pricing).

## Alternatives considered
- **Static pricing:** simplest, leaves value and demand-shaping on the table.
- **Time-of-day schedule:** predictable but ignores real-time demand.
- **ML price optimization:** higher ceiling, but premature without usage data and
  harder to reason about/defend; deferred.
