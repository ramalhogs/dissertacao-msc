"""Cliente LLM da v2, com controle de esforco de raciocinio.

Diferencas em relacao a v1:
  - aceita `reasoning_effort` (low/medium/high/...) e o envia via `reasoning`
    (formato unificado do OpenRouter) ou `reasoning_effort` conforme o provider;
  - captura `reasoning_tokens` do usage, quando o provider reporta;
  - NUNCA descarta o texto bruto: a resposta completa e devolvida intacta.

Providers acessados via SDK da OpenAI (endpoints compativeis com Chat
Completions): openai, gemini, groq, openrouter. Anthropic usa o SDK proprio.
O foco da v2 e OpenRouter, onde o esforco de raciocinio e exposto de forma
uniforme entre modelos baratos.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    reasoning_text: str | None = None
    finish_reason: str | None = None
    raw_usage: dict = field(default_factory=dict)
    raw_response: dict = field(default_factory=dict)


class LLMError(RuntimeError):
    """Erro de configuracao/chamada de provider."""


def _is_retryable(exc: Exception) -> bool:
    name = type(exc).__name__
    if name in {
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
        "InternalServerError",
    }:
        return True
    status = getattr(exc, "status_code", None)
    return status in (429, 500, 502, 503, 504)


def _retry_delay(exc: Exception, attempt: int, base: float) -> float:
    retry_after = None
    resp = getattr(exc, "response", None)
    if resp is not None:
        headers = getattr(resp, "headers", None)
        if headers:
            raw = headers.get("retry-after") or headers.get("Retry-After")
            if raw:
                try:
                    retry_after = float(raw)
                except ValueError:
                    retry_after = None
    if retry_after is not None:
        return min(retry_after + 0.5, 60.0)
    return min(base * (2 ** attempt), 60.0)


OPENAI_COMPATIBLE: dict[str, dict] = {
    "openai": {"base_url": None, "key_env": "OPENAI_API_KEY"},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
    },
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY"},
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
    },
}

# Providers que ignoram/rejeitam `seed` no Chat Completions.
_NO_SEED_PROVIDERS = {"gemini", "groq", "openrouter"}


class LLMClient:
    """Interface unica sobre os providers, com esforco de raciocinio opcional."""

    def __init__(
        self,
        provider: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: int | None = None,
        reasoning_effort: str | None = None,
        max_retries: int = 6,
        retry_base_delay: float = 2.0,
    ):
        self.provider = provider.lower()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        # None = nao envia nada (usa o default do modelo). Um valor explicito
        # (low/medium/high/xhigh/max/minimal/none) e enviado ao provider.
        self.reasoning_effort = reasoning_effort
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._client = self._build_client()

    def _build_client(self):
        if self.provider in OPENAI_COMPATIBLE:
            from openai import OpenAI

            spec = OPENAI_COMPATIBLE[self.provider]
            key = os.getenv(spec["key_env"])
            if not key:
                raise LLMError(
                    f"{spec['key_env']} nao definida no ambiente/.env "
                    f"(necessaria para o provider '{self.provider}')."
                )
            kwargs: dict = {"api_key": key}
            if spec["base_url"]:
                kwargs["base_url"] = spec["base_url"]
            return OpenAI(**kwargs)

        if self.provider == "anthropic":
            from anthropic import Anthropic

            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise LLMError("ANTHROPIC_API_KEY nao definida no ambiente/.env")
            return Anthropic(api_key=key)

        raise LLMError(f"Provider nao suportado: {self.provider}")

    def chat(self, messages: list[dict]) -> LLMResponse:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                if self.provider in OPENAI_COMPATIBLE:
                    return self._chat_openai(messages)
                return self._chat_anthropic(messages)
            except Exception as e:  # noqa: BLE001 - reagimos por tipo
                if not _is_retryable(e) or attempt == self.max_retries - 1:
                    last_exc = e
                    break
                time.sleep(_retry_delay(e, attempt, base=self.retry_base_delay))
                last_exc = e
        raise LLMError(f"Falha apos {self.max_retries} tentativas: {last_exc}")

    def _chat_openai(self, messages: list[dict]) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None and self.provider not in _NO_SEED_PROVIDERS:
            kwargs["seed"] = self.seed
        if self.reasoning_effort is not None:
            if self.provider == "openrouter":
                # Formato unificado do OpenRouter.
                kwargs["extra_body"] = {
                    "reasoning": {"effort": self.reasoning_effort}
                }
            else:
                # OpenAI e compativeis aceitam reasoning_effort direto.
                kwargs["reasoning_effort"] = self.reasoning_effort

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        message = choice.message
        text = message.content or ""
        # Alguns providers expoem o raciocinio em campos nao padronizados.
        reasoning_text = (
            getattr(message, "reasoning", None)
            or getattr(message, "reasoning_content", None)
        )
        usage = getattr(resp, "usage", None)
        reasoning_tokens = None
        raw_usage: dict = {}
        if usage is not None:
            raw_usage = _usage_to_dict(usage)
            details = getattr(usage, "completion_tokens_details", None)
            if details is not None:
                reasoning_tokens = getattr(details, "reasoning_tokens", None)
        return LLMResponse(
            text=text,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            reasoning_tokens=reasoning_tokens,
            reasoning_text=reasoning_text,
            finish_reason=getattr(choice, "finish_reason", None),
            raw_usage=raw_usage,
            raw_response=resp.model_dump(mode="json"),
        )

    def _chat_anthropic(self, messages: list[dict]) -> LLMResponse:
        system = "\n\n".join(
            m["content"] for m in messages if m["role"] == "system"
        )
        turns = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
        create_kwargs: dict = {
            "model": self.model,
            "system": system or None,
            "messages": turns,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.reasoning_effort is not None:
            # Anthropic usa orcamento de tokens; mapeamos o effort em fracao de
            # max_tokens (aprox. as razoes documentadas pelo OpenRouter).
            ratio = {
                "minimal": 0.1,
                "low": 0.2,
                "medium": 0.5,
                "high": 0.8,
                "xhigh": 0.95,
                "max": 0.95,
            }.get(self.reasoning_effort)
            if ratio is not None:
                budget = max(min(int(self.max_tokens * ratio), 128000), 1024)
                create_kwargs["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget,
                }
        resp = self._client.messages.create(**create_kwargs)
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        )
        reasoning_text = "".join(
            getattr(b, "thinking", "")
            for b in resp.content
            if getattr(b, "type", "") == "thinking"
        ) or None
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            prompt_tokens=getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "output_tokens", None),
            reasoning_text=reasoning_text,
            finish_reason=getattr(resp, "stop_reason", None),
            raw_usage=_usage_to_dict(usage) if usage is not None else {},
            raw_response=resp.model_dump(mode="json"),
        )


def _usage_to_dict(usage) -> dict:
    """Serializa o objeto usage do SDK em dict simples (best effort)."""
    for attr in ("model_dump", "to_dict", "dict"):
        fn = getattr(usage, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:  # noqa: BLE001
                pass
    out: dict = {}
    for k in dir(usage):
        if k.startswith("_"):
            continue
        v = getattr(usage, k, None)
        if isinstance(v, (int, float, str, bool)) or v is None:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Extracao de codigo (para inspecao; nao ha julgamento automatico na v2).
# ---------------------------------------------------------------------------

_CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code_blocks(text: str) -> list[str]:
    """Devolve todos os blocos de codigo cercados da resposta, em ordem."""
    return [b.strip("\n") for b in _CODE_FENCE.findall(text)]
