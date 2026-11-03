"""Baseten (Muse Spark Open) preset resolver: env fallbacks and llm_backend
selection (config.py, PRD 6.7 open-weights)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from backend.config import (BASETEN_DEFAULT_BASE_URL, BASETEN_DEFAULT_MODEL,
                            Settings)

MUSE_ENV = ("MUSE_SPARK_API_KEY", "MUSESPARK_API_KEY", "BASETEN_API_KEY",
            "MUSE_SPARK_BASE_URL", "MUSE_SPARK_MODEL")


@pytest.fixture(autouse=True)
def clean_muse_env(monkeypatch):
    for var in MUSE_ENV:
        monkeypatch.delenv(var, raising=False)


def make_settings(**kw) -> Settings:
    kw.setdefault("state_dir", Path("."))
    return Settings(**kw)


def test_baseten_key_alone_arms_open_weights_preset(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "bk-123")
    s = make_settings()
    assert s.muse_api_key == "bk-123"
    assert s.muse_key_source == "baseten"
    assert s.muse_base_url == BASETEN_DEFAULT_BASE_URL
    assert s.muse_model == BASETEN_DEFAULT_MODEL == "meta-models/muse-spark-open-1026"
    assert s.llm_available
    assert s.llm_backend == "open_weights"


def test_muse_env_wins_over_baseten(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "bk-123")
    monkeypatch.setenv("MUSE_SPARK_API_KEY", "mk-1")
    monkeypatch.setenv("MUSE_SPARK_BASE_URL", "https://muse.example")
    s = make_settings()
    assert s.muse_api_key == "mk-1"
    assert s.muse_key_source == "muse"
    assert s.muse_base_url == "https://muse.example"
    assert s.muse_model == "muse-spark"
    assert s.llm_backend == "meta_api"


def test_baseten_preset_respects_explicit_url_and_model(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "bk-123")
    monkeypatch.setenv("MUSE_SPARK_BASE_URL", "https://proxy.example/v1")
    monkeypatch.setenv("MUSE_SPARK_MODEL", "custom-open-weights")
    s = make_settings()
    assert s.muse_base_url == "https://proxy.example/v1"
    assert s.muse_model == "custom-open-weights"
    # key still came from BASETEN_API_KEY -> open-weights backend regardless of model name
    assert s.llm_backend == "open_weights"


def test_no_credentials_means_auto_backend(monkeypatch):
    s = make_settings()
    assert s.muse_api_key is None
    assert s.muse_key_source is None
    assert s.muse_base_url is None
    assert not s.llm_available
    assert s.llm_backend == "auto"


def test_muse_key_without_base_url_is_not_available(monkeypatch):
    monkeypatch.setenv("MUSE_SPARK_API_KEY", "mk-1")
    s = make_settings()
    # no BASETEN_API_KEY -> no preset base URL default for muse-source keys
    assert s.muse_base_url is None
    assert not s.llm_available
    assert s.llm_backend == "auto"


def test_meta_models_prefix_selects_open_weights(monkeypatch):
    monkeypatch.setenv("MUSE_SPARK_API_KEY", "mk-1")
    monkeypatch.setenv("MUSE_SPARK_BASE_URL", "https://muse.example")
    monkeypatch.setenv("MUSE_SPARK_MODEL", "meta-models/muse-spark-open-1026")
    s = make_settings()
    assert s.llm_backend == "open_weights"


def test_health_surfaces_baseten_preset(monkeypatch, tmp_path):
    from backend.api.main import create_app

    monkeypatch.setenv("BASETEN_API_KEY", "bk-123")
    settings = Settings(data_dir=tmp_path / "no-data", state_dir=tmp_path / "state")
    out = TestClient(create_app(settings)).get("/api/health").json()
    assert out["agent_mode"] == "llm"
    assert out["llm_backend"] == "open_weights"
    assert out["llm_model"] == BASETEN_DEFAULT_MODEL
