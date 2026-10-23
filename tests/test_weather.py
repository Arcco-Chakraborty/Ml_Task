from datetime import date

import pytest

from app.weather import providers, service
from tests.conftest import fixture


@pytest.fixture
def forecast(app, offline_weather):
    with app.app_context():
        return service.build_forecast(28.38, 75.61)


def test_daily_day_names_match_their_dates(forecast):
    days = forecast["daily"]
    assert days[0]["day"] == "Today"
    for d in days[1:]:
        assert d["day"] == date.fromisoformat(d["date"]).strftime("%a")


def test_sunrise_sunset_are_local_clock_times(forecast):
    raw = fixture("forecast_pilani.json")["daily"]
    assert forecast["daily"][0]["sunrise"] == raw["sunrise"][0][11:16]
    assert forecast["daily"][0]["sunset"] == raw["sunset"][0][11:16]


def test_hourly_starts_at_current_hour(forecast):
    raw = fixture("forecast_pilani.json")
    assert len(forecast["hourly"]) == 24
    assert forecast["hourly"][0]["time"] == raw["current"]["time"][11:13] + ":00"


@pytest.mark.parametrize("deg,label", [(0, "N"), (359, "N"), (90, "E"), (180, "S"), (225, "SW"), (337.5, "NNW")])
def test_compass_point(deg, label):
    assert service.compass_point(deg) == label


@pytest.mark.parametrize("value,label", [(0, "Good"), (50, "Good"), (51, "Moderate"), (122, "Unhealthy for sensitive groups"),
                                         (350, "Hazardous"), (None, None)])
def test_aqi_category(value, label):
    assert service.aqi_category(value) == label


def test_units_are_passed_upstream_and_labelled(client, offline_weather):
    data = client.get("/api/weather?lat=28.38&lon=75.61&units=imperial").get_json()
    assert offline_weather["forecast"][2] == "imperial"
    assert data["units"]["temperature"] == "°F"
    assert data["units"]["wind"] == "mph"


def test_weather_endpoint_shape(client, offline_weather):
    data = client.get("/api/weather?lat=28.38&lon=75.61").get_json()
    assert set(data) == {"location", "units", "current", "hourly", "daily", "air_quality"}
    assert len(data["daily"]) == 7
    assert {"temperature", "humidity", "wind_speed", "wind_direction", "wind_from", "icon", "text"} <= set(data["current"])


def test_weather_requires_valid_coords(client):
    assert client.get("/api/weather").status_code == 400
    assert client.get("/api/weather?lat=100&lon=0").status_code == 400
    assert client.get("/api/weather?lat=1&lon=1&units=kelvin").status_code == 400


def test_upstream_failure_is_a_502(client, monkeypatch):
    def boom(*a, **k):
        raise providers.UpstreamError("down")
    monkeypatch.setattr(providers, "fetch_forecast", boom)
    resp = client.get("/api/weather?lat=1&lon=1")
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_search_keeps_accents(client, offline_weather):
    data = client.get("/api/search?q=Zürich").get_json()
    assert offline_weather["search"] == "Zürich"
    assert data["results"][0]["label"] == "Zurich, Canton of Zurich, Switzerland"


def test_search_ignores_tiny_queries(client, offline_weather):
    assert client.get("/api/search?q=a").get_json() == {"results": []}
    assert "search" not in offline_weather


def test_reverse_geocode_names_a_place(client, offline_weather):
    data = client.get("/api/reverse?lat=28.38&lon=75.61").get_json()
    assert data["name"] == "Panthariya"
    assert "Rajasthan" in data["label"]


def test_night_hours_get_night_icons(forecast):
    raw = fixture("forecast_pilani.json")
    hourly = raw["hourly"]
    start = service.current_hour_index(hourly["time"], raw["current"]["time"])
    for i, h in enumerate(forecast["hourly"], start):
        assert h["icon"] == service.describe(hourly["weather_code"][i], hourly["is_day"][i])["icon"]
    assert service.describe(0, False)["icon"] == "🌙"
