"""Executa o piloto direto A0 sobre uma amostra do DS-1000.

Exemplo:
    python scripts/run_pilot.py --n-tasks 5 \
        --interventions I0 I1 I2 I3 --provider groq \
        --model openai/gpt-oss-120b
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collect import CsvCollector
from src.config import CONFIG, DATA_DIR
from src.dataset import load_pilot_tasks
from src.interventions import build_intervention_pair
from src.llm import LLMClient
from src.orchestrator import run_observation


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-tasks", type=int, default=5)
    parser.add_argument(
        "--interventions",
        nargs="+",
        choices=("I0", "I1", "I2", "I3"),
        default=["I0", "I1", "I2", "I3"],
    )
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--out", type=str, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    needs_pair = any(code in ("I1", "I2") for code in args.interventions)
    provider = args.provider or CONFIG.provider
    model = args.model or CONFIG.model

    print(
        f"Provider={provider} Model={model} "
        f"Seed={CONFIG.seed} Temp={CONFIG.temperature}"
    )
    client = LLMClient(
        provider=provider,
        model=model,
        temperature=CONFIG.temperature,
        max_tokens=CONFIG.max_tokens,
        seed=CONFIG.seed,
    )

    print("Carregando DS-1000 e checando elegibilidade (pode baixar do HF)...")
    tasks, report = load_pilot_tasks(
        n=args.n_tasks,
        seed=CONFIG.seed,
        reference_timeout=CONFIG.exec_timeout,
    )
    print("Elegibilidade:", report)
    print(f"Tarefas na amostra: {len(tasks)}")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    output = Path(args.out) if args.out else DATA_DIR / f"a0_{stamp}.csv"

    observation_count = 0
    with CsvCollector(output) as collector:
        for index, task in enumerate(tasks, 1):
            print(
                f"\n[{index}/{len(tasks)}] pid={task.problem_id} "
                f"lib={task.library} pert={task.perturbation_type}"
            )

            pair = None
            if needs_pair:
                print("  construindo/validando par I1/I2...")
                pair = build_intervention_pair(
                    task, client, exec_timeout=CONFIG.exec_timeout
                )
                if pair is None:
                    print("  par I1/I2 não validado -> I1/I2 serão puladas")

            for intervention in args.interventions:
                observation = run_observation(
                    task=task,
                    client=client,
                    intervention=intervention,
                    pair=pair,
                    exec_timeout=CONFIG.exec_timeout,
                )
                if observation is None:
                    print(f"    {intervention}: pulada (inaplicável)")
                    continue
                collector.add(observation)
                observation_count += 1
                print(
                    f"    {intervention}: "
                    f"Yi={observation.y_initial} Yf={observation.y_final} "
                    f"conf={observation.confidence_final} "
                    f"chg={observation.changed_code}"
                )

    print(f"\nColeta concluída: {observation_count} observações -> {output}")


if __name__ == "__main__":
    main()
