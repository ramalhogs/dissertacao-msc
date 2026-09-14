"""Escrita das observações em CSV (uma linha por observação)."""

from __future__ import annotations

import csv
from dataclasses import asdict, fields
from pathlib import Path

from src.orchestrator import Observation

FIELDNAMES = [f.name for f in fields(Observation)]


class CsvCollector:
    """Grava observações incrementalmente para não perder dados em falhas."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=FIELDNAMES)
        self._writer.writeheader()
        self._fh.flush()

    def add(self, obs: Observation) -> None:
        self._writer.writerow(asdict(obs))
        self._fh.flush()  # flush a cada linha: coleta longa é resiliente

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "CsvCollector":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
