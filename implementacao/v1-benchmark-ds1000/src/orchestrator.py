"""Orquestra os dois turnos de uma observação na condição direta A0.

Fluxo:
  turno 1: o modelo recebe o enunciado e produz a solução inicial;
  intervenção: a mensagem I0, I1, I2 ou I3 entra na conversa;
  turno 2: o modelo produz a solução final;
  avaliação: as duas soluções são executadas, sem mostrar os testes ao modelo.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.dataset import Task
from src.interventions import InterventionPair, intervention_user_message
from src.llm import LLMClient, extract_code, extract_confidence
from src.sandbox import run_solution

SYSTEM_PROMPT = (
    "Você é um assistente especialista em programação e ciência de dados em "
    "Python. Resolva a tarefa preenchendo apenas o corpo da solução pedido "
    "(o que substitui o marcador da solução), em um bloco ```python```. "
    "Não redefina os imports já fornecidos pelo contexto."
)


@dataclass
class Observation:
    """Uma linha da tabela de observações do experimento."""

    problem_id: int
    library: str
    perturbation_type: str
    model: str
    architecture: str
    intervention: str
    y_initial: int
    y_final: int
    confidence_final: int | None
    changed_code: int
    initial_error_type: str | None = None
    final_error_type: str | None = None
    notes: str = ""


def _first_turn(
    task: Task, client: LLMClient, exec_timeout: float
) -> tuple[str, object, str]:
    """Executa o turno inicial e devolve código, resultado e resposta bruta."""
    response = client.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task.prompt},
        ]
    )
    code = extract_code(response.text)
    result = run_solution(task.code_context, code, timeout=exec_timeout)
    return code, result, response.text


def run_observation(
    task: Task,
    client: LLMClient,
    intervention: str,
    pair: InterventionPair | None,
    exec_timeout: float,
) -> Observation | None:
    """Executa uma observação A0 ou retorna None se I1/I2 for inaplicável."""
    intervention_message = intervention_user_message(intervention, pair)
    if intervention_message is None:
        return None

    initial_code, initial_result, initial_text = _first_turn(
        task, client, exec_timeout
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task.prompt},
        {"role": "assistant", "content": initial_text},
        intervention_message,
    ]

    final_response = client.chat(messages)
    final_code = extract_code(final_response.text)
    final_confidence = extract_confidence(final_response.text)
    final_result = run_solution(
        task.code_context, final_code, timeout=exec_timeout
    )

    return Observation(
        problem_id=task.problem_id,
        library=task.library,
        perturbation_type=task.perturbation_type,
        model=client.model,
        architecture="A0",
        intervention=intervention,
        y_initial=initial_result.y,
        y_final=final_result.y,
        confidence_final=final_confidence,
        changed_code=int(initial_code.strip() != final_code.strip()),
        initial_error_type=initial_result.error_type,
        final_error_type=final_result.error_type,
    )
