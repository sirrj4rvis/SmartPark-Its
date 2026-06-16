# ADR 0001 — Application factory + blueprints + service layer

**Status:** Accepted

## Context
The original app was a single 490-line `app.py` mixing routing, DB access, auth,
and business logic. This made testing hard (no app isolation), invited circular
imports, and gave no separation of concerns.

## Decision
Adopt the Flask **application factory** pattern (`create_app(config)`), split
HTTP handlers into **blueprints** (public/auth/user/admin/api/ops/errors), and
move all business logic into a **service layer** (`app/services/*`) that is
framework-agnostic and unit-testable without HTTP.

## Consequences
- Tests build isolated app instances with a test config; no global state leakage.
- Routes stay thin; logic is reused by both the web UI and the REST API.
- Extensions are instantiated once (`extensions.py`) and bound in the factory,
  eliminating circular imports.
- Slightly more files / indirection than a single module.

## Alternatives considered
- **Keep single module:** simplest, but untestable and unscalable.
- **Django:** batteries-included, but heavier than needed and a larger rewrite;
  Flask keeps the stack explicit (a better learning/interview artifact).
