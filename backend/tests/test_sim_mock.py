"""Mock simulator: determinism, direction, constraints (contracts/simulation.api.yaml)."""
from __future__ import annotations

from pathlib import Path

from backend.config import Settings
from backend.tools import make_simulation_client
from backend.tools.loader import DatasetRepository


def make_repo(tmp_path: Path) -> DatasetRepository:
    return DatasetRepository(tmp_path / "no-data")


def test_determinism_same_seed(tmp_path):
    repo = make_repo(tmp_path)
    sim = make_simulation_client(repo, Settings(data_dir=repo._data_dir, state_dir=tmp_path))
    a = sim.run_simulation("camp_001_bid_low", 7, {"bid_delta_pct": 20}, None, "impressions")
    b = sim.run_simulation("camp_001_bid_low", 7, {"bid_delta_pct": 20}, None, "impressions")
    assert a == b


def test_bid_raise_improves_impressions_for_bid_low(tmp_path):
    repo = make_repo(tmp_path)
    sim = make_simulation_client(repo, Settings(data_dir=repo._data_dir, state_dir=tmp_path))
    out = sim.run_simulation("camp_001_bid_low", 1, {"bid_delta_pct": 25}, None, "impressions")
    assert out["after"]["impressions"] > out["before"]["impressions"]
    assert out["delta_pct"]["impressions"] >= 5.0
    assert out["verified"] is True


def test_noop_change_is_not_verified(tmp_path):
    repo = make_repo(tmp_path)
    sim = make_simulation_client(repo, Settings(data_dir=repo._data_dir, state_dir=tmp_path))
    out = sim.run_simulation("camp_001_bid_low", 1, {}, None, "impressions")
    assert out["after"] == out["before"]
    assert out["verified"] is False


def test_constraint_violation_blocks_verification(tmp_path):
    repo = make_repo(tmp_path)
    sim = make_simulation_client(repo, Settings(data_dir=repo._data_dir, state_dir=tmp_path))
    out = sim.run_simulation("camp_001_bid_low", 1, {"bid_delta_pct": 40},
                             {"max_ecpm": 0.01}, "impressions")
    assert out["violated_constraints"], "tiny ecpm cap must be violated"
    assert out["verified"] is False
    assert any("max_ecpm" in v for v in out["violated_constraints"])


def test_freq_cap_relaxation_recovers_drops(tmp_path):
    repo = make_repo(tmp_path)
    sim = make_simulation_client(repo, Settings(data_dir=repo._data_dir, state_dir=tmp_path))
    out = sim.run_simulation("camp_003_freq_cap", 3, {"frequency_cap": 6}, None, "impressions")
    assert out["after"]["impressions"] > out["before"]["impressions"]


def test_limitation_note_always_present(tmp_path):
    repo = make_repo(tmp_path)
    sim = make_simulation_client(repo, Settings(data_dir=repo._data_dir, state_dir=tmp_path))
    out = sim.run_simulation("control_healthy", 0, {}, None)
    assert out["notes"], "notes must always include the limitation note"
