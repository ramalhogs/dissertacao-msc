"""Cliente de LLM configurável por provider, com interface única.

Abstrai vários providers atrás de `LLMClient.chat(messages)`, para que o
orquestrador não dependa do provider. Também traz utilitários para extrair o
corpo da solução (o que vai no [insert] do DS-1000) e a confiança verbalizada
(escala 0-100 exigida pelo protocolo) da resposta em texto livre.

Providers suportados:
  - openai      (pago)    — API padrão da OpenAI
  - anthropic   (pago)    — API Claude
  - gemini      (grátis*) — Google, free tier
  - groq        (grátis*) — modelos abertos, free tier sem cartão
  - openrouter  (grátis*) — inclui modelos com sufixo ":free"

  (*) free tier com limites de taxa; exige chave gratuita.

Gemini, Groq e OpenRouter expõem endpoints compatíveis com a API da OpenAI,
então usam o mesmo SDK apenas mudando base_url e a chave.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    # tokens, se o provider reportar (para registrar orçamento).
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMError(RuntimeError):
    """Erro de configuração/chamada de provider."""


def _is_retryable(exc: Exception) -> bool:
    """Erros transitórios que valem retry: rate limit, timeouts, 5xx, conexão."""
    name = type(exc).__name__
    if name in {
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
        "InternalServerError",
    }:
        return True
    status = getattr(exc, "status_code", None)
    if status in (429, 500, 502, 503, 504):
        return True
    return False


def _retry_delay(exc: Exception, attempt: int, base: float) -> float:
    """Tempo de espera antes do próximo retry.

    Usa o cabeçalho Retry-After quando o provider o fornece; caso contrário
    aplica backoff exponencial (base * 2**attempt), com teto de 60s.
    """
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


# Providers acessados via SDK da OpenAI (endpoints Chat Completions
# compatíveis). Cada um define base_url e a variável de ambiente da chave.
OPENAI_COMPATIBLE: dict[str, dict] = {
    "openai": {
        "base_url": None,  # padrão da OpenAI
        "key_env": "OPENAI_API_KEY",
        "requires_key": True,
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "requires_key": True,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "requires_key": True,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "requires_key": True,
    },
}

# Providers que ignoram ou rejeitam o parâmetro `seed` no Chat Completions.
_NO_SEED_PROVIDERS = {"gemini", "groq", "openrouter"}


class LLMClient:
    """Interface única sobre os providers suportados."""

    def __init__(
        self,
        provider: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        seed: int | None = None,
        max_retries: int = 6,
        retry_base_delay: float = 2.0,
    ):
        self.provider = provider.lower()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._client = self._build_client()

    def _build_client(self):
        if self.provider in OPENAI_COMPATIBLE:
            from openai import OpenAI

            spec = OPENAI_COMPATIBLE[self.provider]
            key = os.getenv(spec["key_env"])
            if spec["requires_key"] and not key:
                raise LLMError(
                    f"{spec['key_env']} não definida no ambiente/.env "
                    f"(necessária para o provider '{self.provider}')."
                )
            kwargs: dict = {"api_key": key or "not-needed"}
            if spec["base_url"]:
                kwargs["base_url"] = spec["base_url"]
            return OpenAI(**kwargs)

        if self.provider == "anthropic":
            from anthropic import Anthropic

            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise LLMError("ANTHROPIC_API_KEY não definida no ambiente/.env")
            return Anthropic(api_key=key)

        raise LLMError(f"Provider não suportado: {self.provider}")

    def chat(self, messages: list[dict]) -> LLMResponse:
        """Envia uma conversa (lista de {role, content}) e devolve a resposta.

        `messages` usa o formato comum: role em {system, user, assistant}.
        Aplica retry com backoff exponencial em erros de rate limit / rede,
        importante para os free tiers (Groq/Gemini) que limitam tokens/minuto.
        """
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                if self.provider in OPENAI_COMPATIBLE:
                    return self._chat_openai(messages)
                return self._chat_anthropic(messages)
            except Exception as e:  # noqa: BLE001 - reagimos por tipo abaixo
                if not _is_retryable(e) or attempt == self.max_retries - 1:
                    last_exc = e
                    break
                delay = _retry_delay(e, attempt, base=self.retry_base_delay)
                time.sleep(delay)
                last_exc = e
        raise LLMError(f"Falha após {self.max_retries} tentativas: {last_exc}")

    def _chat_openai(self, messages: list[dict]) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        # seed só onde é suportado (mantém reprodutibilidade quando possível).
        if self.seed is not None and self.provider not in _NO_SEED_PROVIDERS:
            kwargs["seed"] = self.seed
        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=choice,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )

    def _chat_anthropic(self, messages: list[dict]) -> LLMResponse:
        # Anthropic separa o system dos turnos user/assistant.
        system = "\n\n".join(
            m["content"] for m in messages if m["role"] == "system"
        )
        turns = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
        resp = self._client.messages.create(
            model=self.model,
            system=system or None,
            messages=turns,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            prompt_tokens=getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "output_tokens", None),
        )


# ---------------------------------------------------------------------------
# Extração de solução e confiança a partir do texto livre da resposta.
# ---------------------------------------------------------------------------

_CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_CONFIDENCE = re.compile(
    r"(?:confian[çc]a|confidence)\D{0,20}?(\d{1,3})", re.IGNORECASE
)


def extract_code(text: str) -> str:
    """Extrai o corpo da solução da resposta do modelo.

    Estratégia:
    1. Se houver bloco cercado ```...```, usa o último (costuma ser a solução
       final após explicações).
    2. Caso contrário, devolve o texto sem cercas, assumindo que o modelo
       respondeu só com código.
    Remove `BEGIN/END SOLUTION` residuais que o modelo às vezes ecoa.
    """
    blocks = _CODE_FENCE.findall(text)
    if blocks:
        code = blocks[-1]
    else:
        # Fallback para bloco NÃO fechado: alguns modelos abrem ```python mas
        # não fecham a cerca. Pega tudo após a última abertura de cerca.
        m = list(re.finditer(r"```(?:python)?\s*\n", text, re.IGNORECASE))
        code = text[m[-1].end():] if m else text
    # Remove qualquer cerca residual e marcadores do template do DS-1000.
    code = code.replace("```", "")
    code = re.sub(r"</?code>", "", code)
    code = re.sub(r"BEGIN SOLUTION|END SOLUTION", "", code)
    # Remove linhas de confiança verbalizada que o modelo às vezes coloca
    # dentro do bloco de código (não são Python e quebrariam o exec).
    code = re.sub(
        r"(?im)^\s*(?:confian[çc]a|confidence)\s*[:=].*$", "", code
    )
    return code.strip("\n")


def extract_confidence(text: str) -> int | None:
    """Extrai a confiança verbalizada (0-100), se presente.

    Procura por padrões como "confiança: 85" ou "confidence 90". Devolve None
    se não encontrar ou se o valor estiver fora de 0-100.
    """
    m = _CONFIDENCE.search(text)
    if not m:
        return None
    val = int(m.group(1))
    return val if 0 <= val <= 100 else None
