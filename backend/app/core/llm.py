"""Groq model-call layer: every agent gets validated, structured JSON back."""
import json
import re
import time
from typing import TypeVar

from groq import APIConnectionError, APIStatusError, Groq, RateLimitError
from pydantic import BaseModel, ValidationError

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

_client: Groq | None = None


class LLMError(RuntimeError):
    pass


def get_client() -> Groq:
    global _client
    if not settings.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is empty. Add it to backend\\.env")
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


def _extract_json(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text


def call_json(system: str, user: str, schema: type[T], retries: int = 2, max_tokens: int = 4000) -> T:
    """Call Groq in JSON mode, validate with Pydantic, retry with the error message on failure."""
    client = get_client()
    schema_text = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    messages = [
        {
            "role": "system",
            "content": (
                f"{system}\n\nRespond with ONE JSON object only (no prose, no markdown) that "
                f"validates against this JSON Schema:\n{schema_text}"
            ),
        },
        {"role": "user", "content": user},
    ]
    kwargs = {}
    if "gpt-oss" in settings.GROQ_MODEL:
        kwargs["extra_body"] = {"reasoning_effort": "low"}

    last_error = ""
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                temperature=0,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"},
                **kwargs,
            )
        except RateLimitError as exc:
            last_error = f"rate limited: {exc}"
            time.sleep(10 * (attempt + 1))
            continue
        except APIConnectionError as exc:
            raise LLMError(f"Could not reach Groq: {exc}") from exc
        except APIStatusError as exc:
            raise LLMError(f"Groq API error {exc.status_code}: {exc.message}") from exc

        content = response.choices[0].message.content or ""
        try:
            return schema.model_validate_json(_extract_json(content))
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)[:600]
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {"role": "user", "content": f"Your reply was invalid: {last_error}\nReturn corrected JSON only."}
            )
    raise LLMError(f"LLM did not return valid JSON after {retries + 1} attempts: {last_error}")