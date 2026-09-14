"""Parâmetros do experimento, carregados de variáveis de ambiente (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class Config:
    provider: str = os.getenv("PROVIDER", "openai")
    model: str = os.getenv("MODEL", "gpt-4o-mini")
    seed: int = int(os.getenv("SEED", "42"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.0"))
    # Orçamento de tokens da resposta do modelo.
    max_tokens: int = int(os.getenv("MAX_TOKENS", "2048"))
    # Tempo máximo (s) para execução de cada solução na sandbox.
    exec_timeout: float = float(os.getenv("EXEC_TIMEOUT", "30"))


CONFIG = Config()
