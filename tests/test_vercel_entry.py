import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def entry(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("SESSION_SECRET", "s" * 40)
    spec = importlib.util.spec_from_file_location("vercel_entry", Path(__file__).parents[1] / "api" / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return TestClient(mod.app, base_url="https://testserver")


def test_rewritten_requests_reach_the_right_route(entry):
    # what Vercel sends for /health and for /
    assert entry.get("/api/index?__path=health").json()["ok"] is True
    r = entry.get("/api/index?__path=", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_query_string_survives_and_marker_is_removed(entry):
    r = entry.get("/api/index?__path=login&error=1")
    assert "That password is not right" in r.text


def test_direct_paths_still_work(entry):
    assert entry.get("/health").json()["ok"] is True
