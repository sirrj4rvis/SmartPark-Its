"""
settings_service.py — runtime-editable application settings.

Admin-tunable values (pricing, reservation TTL, UPI payee) live in the
app_settings table and override the environment-derived config defaults. This
lets an operator change behaviour from the UI without a redeploy, while config
remains the source of the initial/default values.
"""
from flask import current_app

from ..extensions import db
from ..models import AppSetting

# key -> (type, config-default-key)
_SPEC = {
    "pricing_surge_enabled": (bool, "PRICING_SURGE_ENABLED"),
    "pricing_surge_threshold": (float, "PRICING_SURGE_THRESHOLD"),
    "pricing_surge_max": (float, "PRICING_SURGE_MAX"),
    "reservation_ttl_minutes": (int, "RESERVATION_TTL_MINUTES"),
    "upi_vpa": (str, "UPI_VPA"),
    "upi_payee_name": (str, "UPI_PAYEE_NAME"),
}


def _coerce(typ, raw):
    if typ is bool:
        return str(raw).lower() in ("1", "true", "yes", "on")
    return typ(raw)


def get(key):
    """Return the setting: DB override if present, else the config default."""
    if key not in _SPEC:
        raise KeyError(key)
    typ, cfg_key = _SPEC[key]
    row = db.session.get(AppSetting, key)
    if row is not None and row.value != "":
        try:
            return _coerce(typ, row.value)
        except (ValueError, TypeError):
            pass
    return current_app.config.get(cfg_key)


def set_many(values: dict):
    """Upsert a batch of settings (ignores unknown keys)."""
    for key, raw in values.items():
        if key not in _SPEC:
            continue
        typ, _ = _SPEC[key]
        # Normalise booleans/numbers to a canonical string.
        if typ is bool:
            val = "true" if _coerce(bool, raw) else "false"
        else:
            val = str(_coerce(typ, raw))
        row = db.session.get(AppSetting, key)
        if row is None:
            db.session.add(AppSetting(key=key, value=val))
        else:
            row.value = val
    db.session.commit()


def all_settings() -> dict:
    return {key: get(key) for key in _SPEC}
