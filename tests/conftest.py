import json
from pathlib import Path

import pytest

from app import create_app
from app.weather import providers

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakePipeline:
    """Deterministic stand-in for the participant's model: answers come from a lookup table."""

    def __init__(self, answers=None):
        # text -> (label, match_id or None)
        self.answers = answers or {}

    def classify(self, text):
        return self.answers.get(text, ("query", None))[0]

    def match_suggestion(self, text, suggestions):
        return self.answers.get(text, (None, None))[1]

    def match_issue(self, text, issues):
        return self.answers.get(text, (None, None))[1]


@pytest.fixture
def fake_pipeline():
    return FakePipeline()


@pytest.fixture
def app(tmp_path, fake_pipeline):
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "ML_ARTIFACTS": str(tmp_path / "artifacts"),
        "PIPELINE": fake_pipeline,
        "ADMIN_PASSWORD": "pw",
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(client):
    client.post("/admin/login", data={"password": "pw"})
    return client


@pytest.fixture
def offline_weather(monkeypatch):
    """Serve recorded upstream responses instead of calling the network."""
    calls = {}

    def forecast(lat, lon, units):
        calls["forecast"] = (lat, lon, units)
        return fixture("forecast_pilani.json")

    def air(lat, lon):
        return fixture("air_pilani.json")

    def search(query, count=8):
        calls["search"] = query
        return fixture("geocode_zurich.json")

    def reverse(lat, lon):
        return fixture("reverse_pilani.json")

    monkeypatch.setattr(providers, "fetch_forecast", forecast)
    monkeypatch.setattr(providers, "fetch_air_quality", air)
    monkeypatch.setattr(providers, "search_places", search)
    monkeypatch.setattr(providers, "reverse_lookup", reverse)
    return calls
