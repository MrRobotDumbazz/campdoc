"""Runtime configuration. Secrets come from env only (constitution I52)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    # Muse Spark (Meta Model API). No defaults for secrets/URLs: env only.
    muse_api_key: str | None = field(default_factory=lambda: os.environ.get("MUSE_SPARK_API_KEY") or os.environ.get("MUSESPARK_API_KEY"))
    muse_base_url: str | None = field(default_factory=lambda: os.environ.get("MUSE_SPARK_BASE_URL"))
    muse_model: str = field(default_factory=lambda: os.environ.get("MUSE_SPARK_MODEL", "muse-spark"))
    # Simulator seam (contracts/simulation.api.yaml); unset -> deterministic mock client.
    simulator_base_url: str | None = field(default_factory=lambda: os.environ.get("SIMULATOR_BASE_URL"))
    # Data dir (zone B /data); if absent/empty -> built-in deterministic demo datasets.
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("CAMPDOC_DATA_DIR", str(REPO_ROOT / "data"))))
    state_dir: Path = field(default_factory=lambda: Path(os.environ.get("CAMPDOC_STATE_DIR", str(BACKEND_ROOT / ".state"))))
    agent_max_steps: int = field(default_factory=lambda: int(os.environ.get("CAMPDOC_AGENT_MAX_STEPS", "12")))
    simulation_threshold_pct: float = field(default_factory=lambda: float(os.environ.get("CAMPDOC_SIM_THRESHOLD_PCT", "5.0")))
    request_timeout_s: float = field(default_factory=lambda: float(os.environ.get("MUSE_SPARK_TIMEOUT_S", "60")))

    @property
    def llm_available(self) -> bool:
        return bool(self.muse_api_key and self.muse_base_url)

    def ensure_state_dir(self) -> Path:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return self.state_dir


def get_settings() -> Settings:
    return Settings()
