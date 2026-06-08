from __future__ import annotations

from typing import Protocol, Sequence

from .models import ModelResponse


class ModelProvider(Protocol):
    def complete(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
    ) -> ModelResponse:
        """Collect one model response."""


class VercelGatewayProvider:
    def __init__(self, api_key: str, base_url: str = "https://ai-gateway.vercel.sh/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def complete(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
    ) -> ModelResponse:
        client = self._get_client()
        stream = client.chat.completions.create(
            model=model,
            messages=list(messages),
            stream=True,
            stream_options={"include_usage": True},
        )

        parts: list[str] = []
        tokens_used = 0
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if choices:
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None)
                if content:
                    parts.append(content)
            usage = getattr(chunk, "usage", None)
            if usage:
                tokens_used = int(getattr(usage, "total_tokens", 0) or tokens_used)

        text = "".join(parts)
        return ModelResponse(text=text, tokens_used=tokens_used or _estimate_tokens(text))

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The OpenAI Python package is required for Vercel AI Gateway. "
                "Install dependencies with: python3 -m pip install -e ."
            ) from exc

        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))
