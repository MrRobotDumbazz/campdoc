"""Runtime configuration. Secrets come from env only (constitution I52)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = Path(__file__).resolve().parent

# Muse Spark Open preset on Baseten (PRD 6.7 open-weights). No new env names
# for the user: the key falls back to BASETEN_API_KEY; explicit MUSE_SPARK_*
# env always wins over the preset defaults.
BASETEN_DEFAULT_BASE_URL = "https://inference.baseten.co/v1"  # проверь актуальный URL в docs.baseten.co
BASETEN_DEFAULT_MODEL = "meta-models/muse-spark-open-1026"


def resolve_muse_key(env: Mapping[str, str]) -> tuple[str | None, str | None]:
    """(key, source): MUSE_SPARK_API_KEY/MUSESPARK_API_KEY first, BASETEN_API_KEY second."""
    key = env.get("MUSE_SPARK_API_KEY") or env.get("MUSESPARK_API_KEY")
    if key:
        return key, "muse"
    if env.get("BASETEN_API_KEY"):
        return env["BASETEN_API_KEY"], "baseten"
    return None, None


def resolve_muse_base_url(env: Mapping[str, str]) -> str | None:
    url = env.get("MUSE_SPARK_BASE_URL")
    if url:
        return url
    if resolve_muse_key(env)[1] == "baseten":
        return BASETEN_DEFAULT_BASE_URL
    return None


def resolve_muse_model(env: Mapping[str, str]) -> str:
    model = env.get("MUSE_SPARK_MODEL")
    if model:
        return model
    if resolve_muse_key(env)[1] == "baseten":
        return BASETEN_DEFAULT_MODEL
    return "muse-spark"


@dataclass(frozen=True)
class Settings:
    # Muse Spark (Meta Model API / Muse Spark Open via Baseten). Secrets and
    # URLs: env only. Explicit MUSE_SPARK_* wins; BASETEN_API_KEY alone arms
    # the open-weights preset (base URL + model defaults, PRD 6.7).
    muse_api_key: str | None = field(default_factory=lambda: resolve_muse_key(os.environ)[0])
    muse_key_source: str | None = field(default_factory=lambda: resolve_muse_key(os.environ)[1])
    muse_base_url: str | None = field(default_factory=lambda: resolve_muse_base_url(os.environ))
    muse_model: str = field(default_factory=lambda: resolve_muse_model(os.environ))
    # Simulator seam (contracts/simulation.api.yaml); unset -> deterministic mock client.
    simulator_base_url: str | None = field(default_factory=lambda: os.environ.get("SIMULATOR_BASE_URL"))
    # Data dir (zone B /data/datasets); if absent/empty -> built-in deterministic demo datasets.
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("CAMPDOC_DATA_DIR", str(REPO_ROOT / "data" / "datasets"))))
    state_dir: Path = field(default_factory=lambda: Path(os.environ.get("CAMPDOC_STATE_DIR", str(BACKEND_ROOT / ".state"))))
    agent_max_steps: int = field(default_factory=lambda: int(os.environ.get("CAMPDOC_AGENT_MAX_STEPS", "12")))
    simulation_threshold_pct: float = field(default_factory=lambda: float(os.environ.get("CAMPDOC_SIM_THRESHOLD_PCT", "5.0")))
    request_timeout_s: float = field(default_factory=lambda: float(os.environ.get("MUSE_SPARK_TIMEOUT_S", "60")))

    @property
    def llm_available(self) -> bool:
        return bool(self.muse_api_key and self.muse_base_url)

    @property
    def llm_backend(self) -> str:
        """Which LLM backend the agent would use:
        - "auto": no credentials resolved -> heuristic engine (offline demo);
        - "open_weights": key came from BASETEN_API_KEY or the model is prefixed
          "meta-models/" (PRD 6.7, e.g. meta-models/muse-spark-open-1026);
        - "meta_api": hosted Muse Spark credentials."""
        if not self.llm_available:
            return "auto"
        if self.muse_key_source == "baseten" or self.muse_model.startswith("meta-models/"):
            return "open_weights"
        return "meta_api"

    def ensure_state_dir(self) -> Path:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return self.state_dir


def get_settings() -> Settings:
    return Settings()
