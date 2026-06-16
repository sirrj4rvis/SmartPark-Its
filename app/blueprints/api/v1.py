"""
v1.py — REST API v1 (JWT-authenticated) + OpenAPI 3 spec + Swagger UI.

Endpoints (prefix /api/v1):
  POST /auth/login            -> { access_token }
  GET  /slots                 -> availability snapshot (public)
  GET  /slots/recommend       -> smart recommendations
  POST /bookings              -> create booking            (JWT)
  GET  /bookings              -> my bookings                (JWT)
  POST /bookings/<id>/exit    -> exit + receipt             (JWT)
  GET  /forecast              -> next-24h occupancy forecast
  GET  /analytics             -> KPIs + series              (JWT admin)

Swagger UI served at /api/docs ; raw spec at /api/v1/openapi.json
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy.exc import IntegrityError

from ...extensions import csrf, db, limiter
from ...models import Booking, Role, User
from ...security import authenticate
from ...services import (
    analytics_service,
    booking_service,
    forecast_service,
    geo_service,
    slot_service,
)
from ...realtime import broadcast_slots

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")
docs_bp = Blueprint("api_docs", __name__, url_prefix="/api")

# The API is stateless (JWT) — exempt from session CSRF.
csrf.exempt(api_v1_bp)


def _admin_only():
    return get_jwt().get("role") == Role.admin.value


@api_v1_bp.post("/auth/register")
@limiter.limit("20 per hour")
def api_register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not email or len(password) < 8:
        return jsonify({"error": "name, email and a password (min 8 chars) are required"}), 400
    user = User(name=name, email=email, role=Role.user)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "email already registered"}), 409
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role.value})
    return jsonify({"access_token": token, "user": user.to_dict()}), 201


@api_v1_bp.post("/auth/login")
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True) or {}
    user, error = authenticate(data.get("email", ""), data.get("password", ""))
    if error:
        return jsonify({"error": error}), 401
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role.value})
    return jsonify({"access_token": token, "user": user.to_dict()})


@api_v1_bp.get("/slots")
def slots():
    return jsonify({"slots": slot_service.availability_snapshot(), "counts": slot_service.counts()})


@api_v1_bp.get("/slots/recommend")
def recommend():
    vt = request.args.get("vehicle_type")
    return jsonify({"recommendations": forecast_service.recommend_slots(vt)})


@api_v1_bp.get("/lots")
def lots():
    return jsonify({"lots": [lot.to_dict() for lot in geo_service.list_lots()]})


@api_v1_bp.get("/lots/nearest")
def nearest_lots():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lng"])
    except (KeyError, ValueError):
        return jsonify({"error": "lat and lng query params are required"}), 400
    limit = request.args.get("limit", 5, type=int)
    return jsonify({"lots": geo_service.nearest_lots(lat, lon, limit)})


@api_v1_bp.post("/bookings")
@jwt_required()
def create_booking():
    data = request.get_json(silent=True) or {}
    try:
        booking = booking_service.book_slot(
            int(get_jwt_identity()), int(data.get("slot_id", 0)), data.get("vehicle_number", "")
        )
        broadcast_slots()
        return jsonify(booking.to_dict()), 201
    except booking_service.BookingError as exc:
        return jsonify({"error": str(exc)}), 409


@api_v1_bp.get("/bookings")
@jwt_required()
def my_bookings():
    rows = (
        db.session.query(Booking)
        .filter_by(user_id=int(get_jwt_identity()))
        .order_by(Booking.start_time.desc())
        .all()
    )
    return jsonify({"bookings": [b.to_dict() for b in rows]})


@api_v1_bp.post("/bookings/<int:booking_id>/exit")
@jwt_required()
def exit_booking(booking_id):
    try:
        booking = booking_service.exit_booking(int(get_jwt_identity()), booking_id)
        broadcast_slots()
        return jsonify(booking.to_dict())
    except booking_service.BookingError as exc:
        return jsonify({"error": str(exc)}), 409


@api_v1_bp.get("/forecast")
def forecast():
    return jsonify(forecast_service.next_24h_forecast())


@api_v1_bp.get("/analytics")
@jwt_required()
def analytics():
    if not _admin_only():
        return jsonify({"error": "admin only"}), 403
    return jsonify(
        {
            "kpis": analytics_service.kpis(),
            "revenue_trend": analytics_service.revenue_trend(),
            "peak_hours": analytics_service.peak_hours(),
            "vehicle_mix": analytics_service.vehicle_mix(),
        }
    )


# --------------------------------------------------------------------------- #
# OpenAPI 3 specification + Swagger UI
# --------------------------------------------------------------------------- #
def _openapi_spec():
    bearer = {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}

    def path(summary, secured=False, body=None, params=None):
        op = {"summary": summary, "responses": {"200": {"description": "OK"}}}
        if secured:
            op["security"] = [{"bearerAuth": []}]
        if body:
            op["requestBody"] = {
                "content": {"application/json": {"schema": {"type": "object", "properties": body}}}
            }
        if params:
            op["parameters"] = params
        return op

    return {
        "openapi": "3.0.3",
        "info": {"title": "SmartPark ITS API", "version": "1.0.0",
                 "description": "Real-time smart parking platform API."},
        "components": {"securitySchemes": bearer},
        "paths": {
            "/api/v1/auth/register": {"post": path("Register a new account, returns a JWT",
                body={"name": {"type": "string"}, "email": {"type": "string"}, "password": {"type": "string"}})},
            "/api/v1/auth/login": {"post": path("Obtain a JWT",
                body={"email": {"type": "string"}, "password": {"type": "string"}})},
            "/api/v1/slots": {"get": path("List slot availability")},
            "/api/v1/slots/recommend": {"get": path("Smart slot recommendations")},
            "/api/v1/lots": {"get": path("List parking lots with coordinates & availability")},
            "/api/v1/lots/nearest": {"get": path("Nearest lots to a point",
                params=[
                    {"name": "lat", "in": "query", "required": True, "schema": {"type": "number"}},
                    {"name": "lng", "in": "query", "required": True, "schema": {"type": "number"}},
                ])},
            "/api/v1/bookings": {
                "get": path("List my bookings", secured=True),
                "post": path("Create a booking", secured=True,
                    body={"slot_id": {"type": "integer"}, "vehicle_number": {"type": "string"}}),
            },
            "/api/v1/bookings/{id}/exit": {"post": path("Exit a booking", secured=True,
                params=[{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}])},
            "/api/v1/forecast": {"get": path("24h occupancy forecast")},
            "/api/v1/analytics": {"get": path("Admin analytics", secured=True)},
        },
    }


@api_v1_bp.get("/openapi.json")
def openapi_json():
    return jsonify(_openapi_spec())


@docs_bp.get("/docs")
def swagger_ui():
    return """<!doctype html><html><head><title>SmartPark API Docs</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head><body><div id="swagger"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>window.onload=()=>SwaggerUIBundle({url:'/api/v1/openapi.json',dom_id:'#swagger'});</script>
</body></html>"""
