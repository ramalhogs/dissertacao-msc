"""Sandbox de execução: aplica o critério de correção objetiva (Y) do protocolo.

Cada tarefa do DS-1000 traz um `code_context` que define `test_execution(solution)`.
Essa função insere a solução no lugar de `[insert]`, executa e dá `assert` nos
testes oficiais. Aqui rodamos isso em um subprocesso isolado, com timeout, e
mapeamos o resultado em:

    Y = 1  -> a solução passou em todos os testes
    Y = 0  -> falhou (assert, exceção, timeout, dependência ausente, etc.)

O subprocesso garante isolamento (namespace limpo por execução) e permite impor
tempo máximo real. Nenhum julgamento textual do modelo é usado: o veredito é
puramente funcional, como exige o protocolo.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

# Programa executado no subprocesso. Recebe (code_context, solution) via JSON
# em stdin e imprime o resultado como JSON em stdout.
_RUNNER = r'''
import json, sys, time, io, contextlib

payload = json.load(sys.stdin)
code_context = payload["code_context"]
solution = payload["solution"]

result = {"passed": False, "error_type": None, "error_msg": None, "elapsed": None}
start = time.time()
try:
    ns = {}
    # Define test_execution e demais helpers no namespace isolado.
    exec(code_context, ns)
    test_execution = ns.get("test_execution")
    if test_execution is None:
        result["error_type"] = "NoTestExecution"
        result["error_msg"] = "code_context nao define test_execution"
    else:
        # Silencia stdout/stderr da solucao para nao poluir o protocolo.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            test_execution(solution)
        result["passed"] = True
except AssertionError as e:
    result["error_type"] = "AssertionError"
    result["error_msg"] = str(e)[:500]
except Exception as e:
    result["error_type"] = type(e).__name__
    result["error_msg"] = str(e)[:500]
finally:
    result["elapsed"] = round(time.time() - start, 4)

print(json.dumps(result))
'''


@dataclass
class ExecResult:
    y: int  # 1 se passou em todos os testes, 0 caso contrário
    passed: bool
    error_type: str | None
    error_msg: str | None
    elapsed: float | None
    timed_out: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def run_solution(
    code_context: str,
    solution: str,
    timeout: float = 30.0,
    python_executable: str | None = None,
) -> ExecResult:
    """Executa a `solution` contra os testes de `code_context` em subprocesso.

    Args:
        code_context: campo code_context da tarefa DS-1000.
        solution: corpo da solução gerada pelo modelo (o que vai no [insert]).
        timeout: tempo máximo em segundos.
        python_executable: interpretador a usar (padrão: o mesmo do processo).

    Returns:
        ExecResult com Y e metadados de falha.
    """
    py = python_executable or sys.executable
    payload = json.dumps({"code_context": code_context, "solution": solution})

    with tempfile.NamedTemporaryFile(
        "w", suffix="_runner.py", delete=False
    ) as f:
        f.write(_RUNNER)
        runner_path = f.name

    try:
        proc = subprocess.run(
            [py, runner_path],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        Path(runner_path).unlink(missing_ok=True)
        return ExecResult(
            y=0,
            passed=False,
            error_type="Timeout",
            error_msg=f"excedeu {timeout}s",
            elapsed=timeout,
            timed_out=True,
        )
    finally:
        Path(runner_path).unlink(missing_ok=True)

    stdout = proc.stdout.strip()
    if not stdout:
        return ExecResult(
            y=0,
            passed=False,
            error_type="RunnerCrash",
            error_msg=(proc.stderr or "sem stdout")[:500],
            elapsed=None,
        )

    try:
        # A última linha do stdout é o JSON do resultado.
        data = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return ExecResult(
            y=0,
            passed=False,
            error_type="RunnerParseError",
            error_msg=stdout[:500],
            elapsed=None,
        )

    passed = bool(data.get("passed"))
    return ExecResult(
        y=1 if passed else 0,
        passed=passed,
        error_type=data.get("error_type"),
        error_msg=data.get("error_msg"),
        elapsed=data.get("elapsed"),
    )
