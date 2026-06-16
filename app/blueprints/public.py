"""public.py — landing page and unauthenticated content."""
from flask import Blueprint, render_template

from ..services import geo_service, slot_service

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    c = slot_service.counts()
    return render_template("index.html", total=c["total"], avail=c["available"], occupied=c["occupied"])


@public_bp.route("/map")
def parking_map():
    lots = [lot.to_dict() for lot in geo_service.list_lots()]
    return render_template("map.html", lots=lots)
