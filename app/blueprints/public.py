"""public.py — landing page and unauthenticated content."""
from flask import Blueprint, render_template

from ..services import slot_service

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    c = slot_service.counts()
    return render_template("index.html", total=c["total"], avail=c["available"], occupied=c["occupied"])
