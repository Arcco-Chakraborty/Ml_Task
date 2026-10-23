"""Thin HTTP wrappers around the upstream APIs (Open-Meteo, Nominatim).

Everything here returns the raw upstream JSON; shaping happens in service.py.
Tests monkeypatch these functions with fixtures, so keep them free of logic.
"""
import requests
from flask import current_app

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "cirrus-weather/2.4 (SUTT AI/ML task)"


class UpstreamError(Exception):
    pass


def _get(url, params):
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=current_app.config["HTTP_TIMEOUT"],
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstreamError(str(exc)) from exc


def fetch_forecast(lat, lon, units):
    imperial = units == "imperial"
    return _get(FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "forecast_days": 7,
        "temperature_unit": "fahrenheit" if imperial else "celsius",
        "wind_speed_unit": "mph" if imperial else "kmh",
        "precipitation_unit": "inch" if imperial else "mm",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
                   "is_day,wind_speed_10m,wind_direction_10m,pressure_msl,precipitation",
        "hourly": "temperature_2m,precipitation_probability,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
                 "sunrise,sunset,uv_index_max",
    })


def fetch_air_quality(lat, lon):
    return _get(AIR_QUALITY_URL, {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "hourly": "us_aqi,pm2_5,pm10",
    })


def search_places(query, count=8):
    return _get(GEOCODE_URL, {"name": query, "count": count, "language": "en", "format": "json"})


def reverse_lookup(lat, lon):
    return _get(REVERSE_URL, {"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 14})
