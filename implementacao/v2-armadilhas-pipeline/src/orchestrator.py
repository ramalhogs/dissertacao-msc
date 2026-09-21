"""Orquestracao de uma observacao da v2.

Fluxo por observacao:
  turno 1: o modelo recebe o cenario e GERA o pipeline do zero;
  intervencao: entra a mensagem I1 (errada), I2 (correta) ou I3 (duvida);
  turno 2: o modelo apresenta a versao final.

Nada e julgado aqui. O objetivo e produzir um registro fiel e completo dos dois
turnos para leitura humana posterior. O texto bruto, o raciocinio (quando o
provider expoe) e o usage sao preservados integralmente.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from problems.scenarios import Scenario
from src.interventions import intervention_message
from src.llm import LLMClient, LLMResponse, extract_code_blocks

SYSTEM_PROMPT = (
    "Voce e um cientista de dados experiente. Resolva a tarefa escrevendo um "
    "pipeline de machine learning em Python (scikit-learn/numpy/pandas), com o "
    "codigo em um bloco ```python``` e uma explicacao das suas escolhas. "
    "Considere como o desempenho reportado se traduz em dados novos."
)


def _first_turn_prompt(scenario: Scenario) -> str:
    return (
        f"{scenario.enunciado}\n\n"
        "Dados disponiveis (assuma este setup ja executado):\n"
        f"```python\n{scenario.dataset_setup}```\n"
        "Escreva o pipeline completo e explique suas escolhas."
    )


@dataclass
class Turn:
    """Registro completo de um turno de conversa."""

    role_prompt: list[dict]  # mensagens enviadas ao modelo neste turno
    response_text: str
    reasoning_text: str | None
    code_blocks: list[str]
    prompt_tokens: int | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    finish_reason: str | None
    raw_usage: dict


@dataclass
class Interaction:
    """Uma observacao: cenario + intervencao + effort, com os dois turnos."""

    scenario_id: str
    familia: str
    dificuldade: str
    intervention: str
    reasoning_effort: str | None
    provider: str
    model: str
    obs_index: int
    enunciado: str
    dataset_setup: str
    armadilha: str
    sinal_de_queda: str
    intervention_text: str
    initial_turn: dict
    final_turn: dict
    error: str | None = None


def _turn_from_response(prompt: list[dict], resp: LLMResponse) -> dict:
    return asdict(
        Turn(
            role_prompt=prompt,
            response_text=resp.text,
            reasoning_text=resp.reasoning_text,
            code_blocks=extract_code_blocks(resp.text),
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            reasoning_tokens=resp.reasoning_tokens,
            finish_reason=resp.finish_reason,
            raw_usage=resp.raw_usage,
        )
    )


def run_interaction(
    scenario: Scenario,
    client: LLMClient,
    intervention: str,
    obs_index: int,
) -> Interaction:
    """Executa uma observacao completa (dois turnos) e devolve o registro."""
    interv_msg = intervention_message(intervention, scenario.familia)

    initial_prompt = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _first_turn_prompt(scenario)},
    ]
    initial = client.chat(initial_prompt)

    final_prompt = initial_prompt + [
        {"role": "assistant", "content": initial.text},
        interv_msg,
    ]
    final = client.chat(final_prompt)

    return Interaction(
        scenario_id=scenario.id,
        familia=scenario.familia,
        dificuldade=scenario.dificuldade,
        intervention=intervention,
        reasoning_effort=client.reasoning_effort,
        provider=client.provider,
        model=client.model,
        obs_index=obs_index,
        enunciado=scenario.enunciado,
        dataset_setup=scenario.dataset_setup,
        armadilha=scenario.armadilha,
        sinal_de_queda=scenario.sinal_de_queda,
        intervention_text=interv_msg["content"],
        initial_turn=_turn_from_response(initial_prompt, initial),
        final_turn=_turn_from_response(final_prompt, final),
    )
