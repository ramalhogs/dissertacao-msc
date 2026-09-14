"""Loader e amostragem do DS-1000.

Schema real do dataset `xlangai/DS-1000` (split "test", 1000 tarefas):
  - prompt          : enunciado + contexto; termina em "BEGIN SOLUTION\n<code>\n".
                      O modelo completa apenas o corpo da solução (o que vai no
                      placeholder [insert] do code_context), sem os imports.
  - reference_code  : solução de referência (base para as intervenções I1/I2).
  - metadata        : dict com problem_id, library, test_case_cnt,
                      perturbation_type, etc.
  - code_context    : módulo Python que define `test_execution(solution)`,
                      substituindo [insert] pela solução e dando assert.
                      É o avaliador oficial usado como critério Y.

Distribuição por biblioteca (para estratificação):
  Pandas 291, Numpy 220, Matplotlib 155, Sklearn 115, Scipy 106,
  Pytorch 68, Tensorflow 45.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field

from datasets import load_dataset

DATASET_NAME = "xlangai/DS-1000"

# Bibliotecas cujo teste depende de comparação gráfica / ambiente de display.
# Excluídas por padrão na filtragem de elegibilidade do piloto (o critério Y
# não é uma comparação funcional simples e o ambiente pode não ser reprodutível).
#
# Tensorflow e Pytorch exigem dependências pesadas; ficam de fora do piloto
# leve e podem ser reincluídas na coleta principal quando o ambiente tiver
# essas libs instaladas.
DEFAULT_EXCLUDED_LIBRARIES = ("Matplotlib", "Tensorflow", "Pytorch")


@dataclass(frozen=True)
class Task:
    """Uma tarefa do DS-1000 já normalizada para o pipeline."""

    problem_id: int
    library: str
    perturbation_type: str
    test_case_cnt: int
    prompt: str
    reference_code: str
    code_context: str


@dataclass
class EligibilityReport:
    """Registro do que foi mantido/excluído, exigido pelo protocolo."""

    total: int = 0
    excluded_by_library: int = 0
    excluded_libraries: dict[str, int] = field(default_factory=dict)
    # Excluídas porque a própria solução de referência não passou na sandbox
    # (dependência ausente, não determinismo, teste não reproduzível).
    excluded_by_reference_check: int = 0
    excluded_reference_ids: list[int] = field(default_factory=list)
    eligible: int = 0


def load_tasks() -> list[Task]:
    """Carrega todas as tarefas do split de teste."""
    ds = load_dataset(DATASET_NAME, split="test")
    tasks: list[Task] = []
    for row in ds:
        meta = row["metadata"]
        tasks.append(
            Task(
                problem_id=int(meta["problem_id"]),
                library=str(meta["library"]),
                perturbation_type=str(meta["perturbation_type"]),
                test_case_cnt=int(meta["test_case_cnt"]),
                prompt=row["prompt"],
                reference_code=row["reference_code"],
                code_context=row["code_context"],
            )
        )
    return tasks


def filter_eligible(
    tasks: list[Task],
    excluded_libraries: tuple[str, ...] = DEFAULT_EXCLUDED_LIBRARIES,
) -> tuple[list[Task], EligibilityReport]:
    """Aplica a filtragem de elegibilidade e devolve o relatório."""
    report = EligibilityReport(total=len(tasks))
    excl_count: dict[str, int] = defaultdict(int)
    eligible: list[Task] = []
    for t in tasks:
        if t.library in excluded_libraries:
            excl_count[t.library] += 1
            report.excluded_by_library += 1
            continue
        eligible.append(t)
    report.excluded_libraries = dict(excl_count)
    report.eligible = len(eligible)
    return eligible, report


def stratified_sample(
    tasks: list[Task],
    n: int,
    seed: int,
    strata_key=lambda t: t.library,
) -> list[Task]:
    """Amostra `n` tarefas estratificando por `strata_key`, com semente fixa.

    Distribui `n` proporcionalmente entre os estratos e sorteia dentro de cada
    um com a mesma semente, garantindo reprodutibilidade. Se `n` >= total,
    devolve tudo em ordem determinística.
    """
    rng = random.Random(seed)
    if n >= len(tasks):
        result = sorted(tasks, key=lambda t: t.problem_id)
        return result

    # Agrupa por estrato.
    strata: dict[str, list[Task]] = defaultdict(list)
    for t in tasks:
        strata[strata_key(t)].append(t)

    # Ordena estratos por nome para determinismo e sorteia dentro de cada um.
    total = len(tasks)
    picked: list[Task] = []
    remainders: list[tuple[float, str]] = []
    alloc: dict[str, int] = {}
    for name in sorted(strata):
        exact = n * len(strata[name]) / total
        base = int(exact)
        alloc[name] = base
        remainders.append((exact - base, name))

    # Distribui as vagas restantes pelos maiores restos (determinístico).
    allocated = sum(alloc.values())
    for _, name in sorted(remainders, reverse=True)[: n - allocated]:
        alloc[name] += 1

    for name in sorted(strata):
        pool = sorted(strata[name], key=lambda t: t.problem_id)
        k = min(alloc[name], len(pool))
        picked.extend(rng.sample(pool, k))

    picked.sort(key=lambda t: t.problem_id)
    return picked


def filter_reference_passes(
    tasks: list[Task],
    report: EligibilityReport,
    timeout: float = 30.0,
) -> list[Task]:
    """Mantém apenas tarefas cuja solução de referência passa na sandbox.

    Garante que o teste oficial é reproduzível no ambiente atual. Importado
    localmente para evitar dependência circular entre dataset e sandbox.
    """
    from src.sandbox import run_solution

    kept: list[Task] = []
    for t in tasks:
        res = run_solution(t.code_context, t.reference_code, timeout=timeout)
        if res.y == 1:
            kept.append(t)
        else:
            report.excluded_by_reference_check += 1
            report.excluded_reference_ids.append(t.problem_id)
    report.eligible = len(kept)
    return kept


def load_pilot_tasks(
    n: int,
    seed: int,
    excluded_libraries: tuple[str, ...] = DEFAULT_EXCLUDED_LIBRARIES,
    check_reference: bool = True,
    reference_timeout: float = 30.0,
) -> tuple[list[Task], EligibilityReport]:
    """Fluxo completo: carrega, filtra elegibilidade e amostra estratificado.

    A amostragem estratificada é feita ANTES da checagem funcional da
    referência para manter a semente reprodutível; a checagem então poda a
    amostra. Para o piloto isso é suficiente e transparente no relatório.
    """
    all_tasks = load_tasks()
    eligible, report = filter_eligible(all_tasks, excluded_libraries)
    sample = stratified_sample(eligible, n=n, seed=seed)
    if check_reference:
        sample = filter_reference_passes(sample, report, timeout=reference_timeout)
    else:
        report.eligible = len(sample)
    return sample, report
