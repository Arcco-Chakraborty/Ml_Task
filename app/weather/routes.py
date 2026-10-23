from flask import Blueprint, jsonify, request

from . import service
from .providers import UpstreamError

bp = Blueprint("weather", __name__, url_prefix="/api")


def _coords():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


@bp.errorhandler(UpstreamError)
def upstream_failed(exc):
    return jsonify(error="weather service unavailable", detail=str(exc)), 502


@bp.get("/weather")
def weather():
    coords = _coords()
    if coords is None:
        return jsonify(error="lat and lon are required"), 400
    units = request.args.get("units", "metric")
    if units not in ("metric", "imperial"):
        return jsonify(error="units must be metric or imperial"), 400
    return jsonify(service.build_forecast(*coords, units=units))


@bp.get("/search")
def search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify(results=[])
    return jsonify(results=service.search(q))


@bp.get("/reverse")
def reverse():
    coords = _coords()
    if coords is None:
        return jsonify(error="lat and lon are required"), 400
    return jsonify(service.reverse_geocode(*coords))
