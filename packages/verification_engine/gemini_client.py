from __future__ import annotations

from google import genai
from google.genai import types

from packages.intent_compiler.errors import GeminiNotConfigured
from packages.verification_engine.semantic_draft import SemanticDraft


class SemanticGeminiClient:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise GeminiNotConfigured("GEMINI_API_KEY is not set")
        self.model = model
        self._client = genai.Client(api_key=api_key)

    def generate_json(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SemanticDraft,
            ),
        )
        text = (response.text or "").strip()
        if not text:
            return "{}"
        return text
