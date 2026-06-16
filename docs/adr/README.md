# Architecture Decision Records

Short documents capturing significant architectural decisions, their context,
and trade-offs. Format: Context → Decision → Consequences → Alternatives.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-app-factory-blueprints.md) | Flask app factory + blueprints + service layer | Accepted |
| [0002](0002-postgres-over-sqlite.md) | PostgreSQL over SQLite for production | Accepted |
| [0003](0003-booking-concurrency.md) | Pessimistic locking + partial unique index for booking | Accepted |
| [0004](0004-realtime-websockets.md) | WebSockets (Socket.IO + Redis) over polling/SSE | Accepted |
| [0005](0005-dynamic-pricing.md) | Occupancy-based surge pricing | Accepted |
