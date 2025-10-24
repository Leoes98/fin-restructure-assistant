from __future__ import annotations

from typing import Any, Iterable

import httpx

from app.core.config import get_settings


class AzureOpenAIClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.azure_gpt5_endpoint or not settings.azure_gpt5_api_key:
            raise RuntimeError("Azure GPT endpoint or API key not configured")
        if not settings.azure_model_name_deployment or not settings.azure_openai_api_version:
            raise RuntimeError("Azure OpenAI deployment or API version not configured")

        self._endpoint = settings.azure_gpt5_endpoint.rstrip("/")
        self._deployment = settings.azure_model_name_deployment
        self._api_version = settings.azure_openai_api_version
        self._api_key = settings.azure_gpt5_api_key

    async def chat_completion(
        self,
        messages: Iterable[dict[str, Any]],
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> str:
        url = (
            f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions"
        )
        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key,
        }
        params = {"api-version": self._api_version}
        payload: dict[str, Any] = {
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, params=params, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError("Unexpected response from Azure OpenAI") from exc
