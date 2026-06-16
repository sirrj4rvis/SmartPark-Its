# ADR 0004 — Real-time updates via WebSockets (Socket.IO + Redis)

**Status:** Accepted

## Context
The dashboard originally polled `/api/slots` every ~20s. That is laggy (users
see stale availability), wasteful (constant requests regardless of change), and
doesn't scale (N clients × poll interval).

## Decision
Push slot changes over **WebSockets** using **Flask-SocketIO**. After any
mutation (book/exit/admin change) the server emits `slot_update` to the `slots`
room. With a **Redis message queue** configured, emits fan out across all
gunicorn workers/replicas. The client **degrades to polling** if WebSockets are
blocked (corporate proxies).

## Consequences
- Sub-second updates; traffic proportional to *changes*, not client count.
- Horizontal scaling works because Redis pub/sub bridges worker processes.
- Adds Redis as a dependency for multi-process real-time (already used for cache).
- Uses `threading` async mode to avoid eventlet/gevent build complexity; true
  WS transport at high scale would move to gevent-websocket.

## Alternatives considered
- **Server-Sent Events (SSE):** simpler, but one-directional and awkward through
  some proxies; we want a bidirectional channel for future features.
- **Long-polling only:** what we replaced; kept solely as a fallback.
