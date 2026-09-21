"""Registro das interacoes: um JSON e um Markdown legivel por observacao.

A v2 e observacional. O artefato mais importante e a transcricao completa que
voce le no olho, entao gravamos:

  runs/<run_id>/<scenario>__<interv>__<effort>__obs<k>.json  (dados completos)
  runs/<run_id>/<scenario>__<interv>__<effort>__obs<k>.md    (leitura humana)
  runs/<run_id>/run_manifest.json                            (parametros da run)

O JSON e a fonte de verdade; o MD e derivado, formatado para leitura.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.orchestrator import Interaction


def _slug(effort: str | None) -> str:
    return effort if effort else "default"


class RunRecorder:
    def __init__(self, run_dir: Path, manifest: dict):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _stem(self, it: Interaction) -> str:
        return (
            f"{it.scenario_id}__{it.intervention}__{_slug(it.reasoning_effort)}"
            f"__obs{it.obs_index}"
        )

    def save(self, it: Interaction) -> None:
        stem = self._stem(it)
        (self.run_dir / f"{stem}.json").write_text(
            json.dumps(asdict(it), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.run_dir / f"{stem}.md").write_text(
            _to_markdown(it), encoding="utf-8"
        )


def _fmt_turn(title: str, turn: dict) -> str:
    lines = [f"## {title}", ""]
    ru = turn.get("reasoning_tokens")
    ct = turn.get("completion_tokens")
    pt = turn.get("prompt_tokens")
    fr = turn.get("finish_reason")
    lines.append(
        f"_tokens: prompt={pt}, completion={ct}, reasoning={ru}, "
        f"finish={fr}_"
    )
    lines.append("")
    reasoning = turn.get("reasoning_text")
    if reasoning:
        lines += ["### Raciocinio (reasoning trace)", "", "```", reasoning, "```", ""]
    lines += ["### Resposta", "", turn.get("response_text", ""), ""]
    return "\n".join(lines)


def _to_markdown(it: Interaction) -> str:
    parts = [
        f"# {it.scenario_id} | {it.intervention} | effort={_slug(it.reasoning_effort)} "
        f"| obs {it.obs_index}",
        "",
        f"- **Modelo**: {it.provider}/{it.model}",
        f"- **Familia**: {it.familia}  |  **Dificuldade**: {it.dificuldade}",
        f"- **Armadilha (referencia p/ leitura)**: {it.armadilha}",
        f"- **Sinal de queda (referencia p/ leitura)**: {it.sinal_de_queda}",
        "",
        "## Enunciado",
        "",
        it.enunciado,
        "",
        "### Dataset setup",
        "",
        "```python",
        it.dataset_setup.rstrip("\n"),
        "```",
        "",
    ]
    if it.error:
        parts += ["> ERRO NA COLETA:", "", "```", it.error, "```", ""]
        return "\n".join(parts)
    parts.append(_fmt_turn("Turno 1 - pipeline inicial", it.initial_turn))
    parts += [
        "## Intervencao aplicada",
        "",
        f"**{it.intervention}**: {it.intervention_text}",
        "",
    ]
    parts.append(_fmt_turn("Turno 2 - versao final", it.final_turn))
    return "\n".join(parts)
