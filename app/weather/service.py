"""Turns raw upstream responses into the payload the frontend renders."""
from datetime import date
from functools import lru_cache

from . import providers

# WMO weather interpretation codes -> (description, day icon, night icon)
WEATHER_CODES = {
    0: ("Clear sky", "☀️", "🌙"),
    1: ("Mainly clear", "🌤️", "🌙"),
    2: ("Partly cloudy", "⛅", "☁️"),
    3: ("Overcast", "☁️", "☁️"),
    45: ("Fog", "🌫️", "🌫️"),
    48: ("Depositing rime fog", "🌫️", "🌫️"),
    51: ("Light drizzle", "🌦️", "🌧️"),
    53: ("Drizzle", "🌦️", "🌧️"),
    55: ("Dense drizzle", "🌧️", "🌧️"),
    56: ("Freezing drizzle", "🌧️", "🌧️"),
    57: ("Freezing drizzle", "🌧️", "🌧️"),
    61: ("Light rain", "🌦️", "🌧️"),
    63: ("Rain", "🌧️", "🌧️"),
    65: ("Heavy rain", "🌧️", "🌧️"),
    66: ("Freezing rain", "🌧️", "🌧️"),
    67: ("Freezing rain", "🌧️", "🌧️"),
    71: ("Light snow", "🌨️", "🌨️"),
    73: ("Snow", "🌨️", "🌨️"),
    75: ("Heavy snow", "❄️", "❄️"),
    77: ("Snow grains", "🌨️", "🌨️"),
    80: ("Rain showers", "🌦️", "🌧️"),
    81: ("Rain showers", "🌧️", "🌧️"),
    82: ("Violent rain showers", "⛈️", "⛈️"),
    85: ("Snow showers", "🌨️", "🌨️"),
    86: ("Heavy snow showers", "❄️", "❄️"),
    95: ("Thunderstorm", "⛈️", "⛈️"),
    96: ("Thunderstorm with hail", "⛈️", "⛈️"),
    99: ("Thunderstorm with hail", "⛈️", "⛈️"),
}

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

AQI_BANDS = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for sensitive groups"),
    (200, "Unhealthy"),
    (300, "Very unhealthy"),
    (float("inf"), "Hazardous"),
]


def describe(code, is_day=True):
    text, day_icon, night_icon = WEATHER_CODES.get(code, ("Unknown", "❔", "❔"))
    return {"code": code, "text": text, "icon": day_icon if is_day else night_icon}


def compass_point(degrees):
    """Direction the wind is blowing FROM, as a 16-point compass label."""
    return COMPASS[round((degrees % 360) / 22.5) % 16]


def day_name(iso_date, today_iso):
    if iso_date == today_iso:
        return "Today"
    return date.fromisoformat(iso_date).strftime("%a")


def clock(iso_datetime):
    """'2026-10-22T06:32' -> '06:32'. Times are already in the location's timezone."""
    return iso_datetime[11:16]


def aqi_category(value):
    if value is None:
        return None
    for upper, label in AQI_BANDS:
        if value <= upper:
            return label


def current_hour_index(hourly_times, current_time):
    hour = current_time[:13] + ":00"
    try:
        return hourly_times.index(hour)
    except ValueError:
        return 0


def build_forecast(lat, lon, units="metric"):
    raw = providers.fetch_forecast(lat, lon, units)
    cur, hourly, daily = raw["current"], raw["hourly"], raw["daily"]
    today = daily["time"][0]
    start = current_hour_index(hourly["time"], cur["time"])

    current = {
        "time": cur["time"],
        "temperature": round(cur["temperature_2m"]),
        "feels_like": round(cur["temperature_2m"]),
        "humidity": cur["relative_humidity_2m"],
        "wind_speed": round(cur["wind_speed_10m"]),
        "wind_direction": cur["wind_direction_10m"],
        "wind_from": compass_point(cur["wind_direction_10m"]),
        "pressure": round(cur["pressure_msl"]),
        "precipitation": cur["precipitation"],
        "precip_probability": hourly["precipitation_probability"][0],
        "uv_index": daily["uv_index_max"][0],
        **describe(cur["weather_code"], cur["is_day"]),
    }

    next_24 = []
    for i in range(start, min(start + 24, len(hourly["time"]))):
        next_24.append({
            "time": clock(hourly["time"][i]),
            "temperature": round(hourly["temperature_2m"][i]),
            "precip_probability": hourly["precipitation_probability"][i],
            **describe(hourly["weather_code"][i], hourly["is_day"][i]),
        })

    days = []
    for i, d in enumerate(daily["time"]):
        days.append({
            "date": d,
            "day": day_name(d, today),
            "high": round(daily["temperature_2m_max"][i]),
            "low": round(daily["temperature_2m_min"][i]),
            "precip_probability": daily["precipitation_probability_max"][i],
            "sunrise": clock(daily["sunrise"][i]),
            "sunset": clock(daily["sunset"][i]),
            **describe(daily["weather_code"][i]),
        })

    try:
        aqi = build_air_quality(lat, lon)
    except providers.UpstreamError:
        aqi = {"value": None, "category": None}

    return {
        "location": {"lat": raw["latitude"], "lon": raw["longitude"], "timezone": raw["timezone"]},
        "units": {
            "temperature": "°F" if units == "imperial" else "°C",
            "wind": "mph" if units == "imperial" else "km/h",
            "precipitation": "in" if units == "imperial" else "mm",
            "pressure": "hPa",
        },
        "current": current,
        "hourly": next_24,
        "daily": days,
        "air_quality": aqi,
    }


def build_air_quality(lat, lon):
    raw = providers.fetch_air_quality(lat, lon)
    value = raw.get("current", {}).get("us_aqi")
    return {"value": value, "category": aqi_category(value)}


def search(query):
    raw = providers.search_places(query)
    results = []
    for r in raw.get("results", []):
        parts = [r["name"], r.get("admin1"), r.get("country")]
        results.append({
            "name": r["name"],
            "label": ", ".join(p for p in parts if p),
            "lat": r["latitude"],
            "lon": r["longitude"],
        })
    return results


@lru_cache(maxsize=1024)
def _reverse_cached(lat, lon):
    raw = providers.reverse_lookup(lat, lon)
    addr = raw.get("address", {})
    name = next((addr[k] for k in ("city", "town", "village", "suburb", "county") if k in addr),
                raw.get("name") or "Unknown location")
    region = addr.get("state")
    return {"name": name, "label": ", ".join(p for p in (name, region, addr.get("country")) if p)}


def reverse_geocode(lat, lon):
    # nearby lookups share a cache entry
    return _reverse_cached(round(lat, 1), round(lon, 1))
