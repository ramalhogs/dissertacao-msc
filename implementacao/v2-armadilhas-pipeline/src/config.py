"""Parametros da v2, com defaults de ambiente e override por linha de comando."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"


@dataclass(frozen=True)
class Config:
    provider: str = os.getenv("PROVIDER", "openrouter")
    model: str = os.getenv("MODEL", "deepseek/deepseek-v4-flash")
    temperature: float = float(os.getenv("TEMPERATURE", "0.0"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
    seed: int = int(os.getenv("SEED", "42"))


CONFIG = Config()
