"""Executa a coleta observacional da v2.

Modelo parametrizavel, tres intervencoes (I1 errada, I2 correta, I3 duvida),
um ou mais niveis de raciocinio, e N observacoes por combinacao. Nao calcula
metricas: registra cada interacao em JSON + Markdown para leitura.

O teto opcional de custo usa os tokens reportados pelo provider e impede uma
nova interacao quando o saldo restante nao cobre o pior caso configurado.
Interacoes ja gravadas sao puladas, permitindo retomar uma run sem pagar duas
vezes pela mesma celula.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from problems.scenarios import get_scenario, list_scenarios
from src.config import CONFIG, RUNS_DIR
from src.interventions import INTERVENTIONS
from src.llm import LLMClient
from src.orchestrator import Interaction, run_interaction
from src.recorder import RunRecorder


def parse_args():
    p = argparse.ArgumentParser(description="Coleta observacional v2")
    p.add_argument("--provider", default=CONFIG.provider)
    p.add_argument("--model", default=CONFIG.model)
    p.add_argument("--temperature", type=float, default=CONFIG.temperature)
    p.add_argument("--max-tokens", type=int, default=CONFIG.max_tokens)
    p.add_argument(
        "--efforts",
        nargs="+",
        default=["default"],
        help="Niveis de raciocinio; 'default' nao envia effort.",
    )
    p.add_argument(
        "--interventions",
        nargs="+",
        choices=INTERVENTIONS,
        default=list(INTERVENTIONS),
    )
    p.add_argument("--scenarios", nargs="+", default=None)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--run-id", default=None)
    p.add_argument(
        "--max-cost-usd",
        type=float,
        default=None,
        help="Teto desta run. A coleta para antes de ultrapassa-lo.",
    )
    p.add_argument("--input-price-per-million", type=float, default=None)
    p.add_argument("--output-price-per-million", type=float, default=None)
    return p.parse_args()


def _record_path(
    run_dir: Path,
    scenario_id: str,
    intervention: str,
    effort: str | None,
    obs_index: int,
) -> Path:
    effort_slug = effort or "default"
    return run_dir / (
        f"{scenario_id}__{intervention}__{effort_slug}__obs{obs_index}.json"
    )


def _record_cost(record: dict, input_price: float, output_price: float) -> float:
    prompt = 0
    completion = 0
    for turn_name in ("initial_turn", "final_turn"):
        turn = record.get(turn_name) or {}
        prompt += turn.get("prompt_tokens") or 0
        completion += turn.get("completion_tokens") or 0
    return (prompt * input_price + completion * output_price) / 1_000_000


def _existing_cost(run_dir: Path, input_price: float, output_price: float) -> float:
    total = 0.0
    for path in run_dir.glob("*.json"):
        if path.name in {"run_manifest.json", "cost_summary.json"}:
            continue
        try:
            total += _record_cost(
                json.loads(path.read_text(encoding="utf-8")),
                input_price,
                output_price,
            )
        except (json.JSONDecodeError, OSError):
            continue
    return total


def _write_cost_summary(
    run_dir: Path,
    spent: float,
    completed: int,
    total: int,
    stopped_due_to_budget: bool,
) -> None:
    data = {
        "spent_usd": round(spent, 6),
        "completed_interactions": completed,
        "planned_interactions": total,
        "stopped_due_to_budget": stopped_due_to_budget,
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (run_dir / "cost_summary.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    args = parse_args()
    prices = (args.input_price_per_million, args.output_price_per_million)
    has_any_price = any(p is not None for p in prices)
    has_all_prices = all(p is not None for p in prices)
    if args.max_cost_usd is not None and not has_all_prices:
        raise SystemExit(
            "--max-cost-usd exige --input-price-per-million e "
            "--output-price-per-million"
        )
    if has_any_price and not has_all_prices:
        raise SystemExit("informe os dois precos por milhao")

    scenarios = (
        [get_scenario(sid) for sid in args.scenarios]
        if args.scenarios
        else list_scenarios()
    )

    run_id = args.run_id or f"run_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = RUNS_DIR / run_id
    manifest = {
        "run_id": run_id,
        "provider": args.provider,
        "model": args.model,
        "corpus": "principal",
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "efforts": args.efforts,
        "interventions": args.interventions,
        "scenarios": [s.id for s in scenarios],
        "repeats": args.repeats,
        "max_cost_usd": args.max_cost_usd,
        "input_price_per_million": args.input_price_per_million,
        "output_price_per_million": args.output_price_per_million,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    recorder = RunRecorder(run_dir, manifest)

    total = len(scenarios) * len(args.efforts) * len(args.interventions) * args.repeats
    input_price = args.input_price_per_million or 0.0
    output_price = args.output_price_per_million or 0.0
    spent = _existing_cost(run_dir, input_price, output_price) if has_all_prices else 0.0
    # Duas respostas por interacao. Reserva toda a saida configurada e uma
    # entrada conservadora: historico de ate 2*max_tokens + 10k tokens.
    reserve = (
        (2 * args.max_tokens + 10_000) * input_price
        + (2 * args.max_tokens) * output_price
    ) / 1_000_000

    print(f"Run: {run_id}")
    print(f"Modelo: {args.provider}/{args.model}")
    print(f"Combinacoes planejadas: {total} -> {run_dir}")
    if args.max_cost_usd is not None:
        print(
            f"Orcamento: gasto existente US${spent:.4f}; "
            f"teto US${args.max_cost_usd:.2f}; reserva/interacao US${reserve:.4f}"
        )

    completed = 0
    position = 0
    for effort in args.efforts:
        effort_value = None if effort == "default" else effort
        client = LLMClient(
            provider=args.provider,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            seed=CONFIG.seed,
            reasoning_effort=effort_value,
        )
        for scenario in scenarios:
            for intervention in args.interventions:
                for k in range(1, args.repeats + 1):
                    position += 1
                    path = _record_path(
                        run_dir, scenario.id, intervention, effort_value, k
                    )
                    if path.exists():
                        completed += 1
                        print(
                            f"[{position}/{total}] JA EXISTE: {scenario.id} "
                            f"{intervention} effort={effort} obs{k}"
                        )
                        continue
                    if (
                        args.max_cost_usd is not None
                        and spent + reserve > args.max_cost_usd
                    ):
                        print(
                            f"PARADA POR ORCAMENTO: gasto US${spent:.4f}; "
                            f"saldo insuficiente para reserva US${reserve:.4f}"
                        )
                        _write_cost_summary(
                            run_dir, spent, completed, total, True
                        )
                        return

                    print(
                        f"[{position}/{total}] {scenario.id} {intervention} "
                        f"effort={effort} obs{k}"
                    )
                    try:
                        interaction = run_interaction(
                            scenario=scenario,
                            client=client,
                            intervention=intervention,
                            obs_index=k,
                        )
                    except Exception as exc:  # noqa: BLE001 - registra e segue
                        interaction = Interaction(
                            scenario_id=scenario.id,
                            familia=scenario.familia,
                            dificuldade=scenario.dificuldade,
                            intervention=intervention,
                            reasoning_effort=effort_value,
                            provider=args.provider,
                            model=args.model,
                            obs_index=k,
                            enunciado=scenario.enunciado,
                            dataset_setup=scenario.dataset_setup,
                            armadilha=scenario.armadilha,
                            sinal_de_queda=scenario.sinal_de_queda,
                            intervention_text="",
                            initial_turn={},
                            final_turn={},
                            error=f"{type(exc).__name__}: {exc}",
                        )
                        print(f"    ERRO registrado: {interaction.error}")
                    recorder.save(interaction)
                    completed += 1
                    if has_all_prices:
                        spent += _record_cost(
                            json.loads(path.read_text(encoding="utf-8")),
                            input_price,
                            output_price,
                        )
                        print(f"    custo acumulado: US${spent:.4f}")
                    _write_cost_summary(run_dir, spent, completed, total, False)

    print(
        f"\nColeta concluida: {completed}/{total} interacoes; "
        f"custo US${spent:.4f}; pasta {run_dir}"
    )


if __name__ == "__main__":
    main()
