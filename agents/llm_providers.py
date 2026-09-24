import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def _load_env():
    env_path = Path(".env")

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip(),
        )


def query_groq(
    prompt,
    model,
    max_tokens=350,
    max_retries=3,
):
    _load_env()

    api_key = os.environ.get(
        "GROQ_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured"
        )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0,
        "max_completion_tokens": max_tokens,
    }

    if model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"

    body = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "book-genre-research/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            break

        except urllib.error.HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            error_lower = error_body.lower()

            is_daily_quota = (
                error.code == 429
                and (
                    "tokens per day" in error_lower
                    or "tpd" in error_lower
                )
            )

            is_transient_rate_limit = (
                error.code == 429
                and not is_daily_quota
            )

            if is_transient_rate_limit and attempt < max_retries:
                retry_after = error.headers.get(
                    "Retry-After"
                )

                try:
                    wait_seconds = float(retry_after)
                except (TypeError, ValueError):
                    wait_seconds = 2 ** attempt

                wait_seconds = max(
                    wait_seconds,
                    1.0,
                )

                print(
                    "    Groq rate limit; "
                    f"retrying in {wait_seconds:.1f}s..."
                )

                time.sleep(wait_seconds)
                continue

            # Daily quota and other HTTP errors propagate
            # to the annotation runner.
            raise RuntimeError(
                f"Groq HTTP {error.code}: {error_body}"
            ) from error

        except (
            TimeoutError,
            urllib.error.URLError,
            ConnectionError,
            ConnectionResetError,
        ) as error:
            if attempt < max_retries:
                wait_seconds = 2 ** attempt

                print(
                    "    Groq connection error; "
                    f"retrying in {wait_seconds}s..."
                )

                time.sleep(wait_seconds)
                continue

            raise RuntimeError(
                f"Groq connection error after retries: {error}"
            ) from error

    else:
        raise RuntimeError(
            "Groq request failed after retries"
        )

    try:
        content = data["choices"][0]["message"]["content"]

        if not content or not content.strip():
            finish_reason = data["choices"][0].get(
                "finish_reason"
            )

            raise RuntimeError(
                "Model returned empty final content "
                f"(finish_reason={finish_reason})"
            )

        return content

    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(
            f"Unexpected Groq response: {data}"
        ) from error


def query_gemini(
    prompt,
    model,
    max_tokens=1000,
    max_retries=4,
):
    _load_env()

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured"
        )

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/interactions"
    )

    payload = {
        "model": model,
        "input": prompt,
        "generation_config": {
            "temperature": 0,
            "max_output_tokens": max_tokens,
        },
    }

    body = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                req,
                timeout=180,
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            if data.get("error"):
                raise RuntimeError(
                    "Gemini provider error: "
                    + json.dumps(
                        data["error"],
                        ensure_ascii=False,
                    )[:1000]
                )

            texts = []

            for step in data.get("steps", []):
                if step.get("type") != "model_output":
                    continue

                for item in step.get("content", []):
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "text"
                    ):
                        value = item.get("text", "")

                        if value:
                            texts.append(value)

            content = "\n".join(texts).strip()

            if not content:
                raise RuntimeError(
                    "Gemini returned no model_output text "
                    f"(status={data.get('status')})"
                )

            return content

        except urllib.error.HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            # Do not automatically retry Gemini HTTP 429/503.
            # Free-tier quotas are small, and repeated retries can
            # consume the request allowance without producing an
            # annotation. A failed provider call remains an error
            # and can be retried explicitly in a later run.
            raise RuntimeError(
                f"Gemini HTTP {error.code}: "
                f"{error_body[:1000]}"
            ) from error

        except (
            TimeoutError,
            urllib.error.URLError,
        ) as error:
            if attempt < max_retries:
                wait_seconds = 2 ** attempt

                print(
                    "    Gemini connection error; "
                    f"retrying in {wait_seconds}s..."
                )

                time.sleep(wait_seconds)
                continue

            raise RuntimeError(
                f"Gemini connection error: {error}"
            ) from error

    raise RuntimeError(
        "Gemini request failed after retries"
    )

def query_openrouter(
    prompt,
    model,
    max_tokens=500,
):
    _load_env()

    api_key = os.environ.get(
        "OPENROUTER_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured"
        )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }

    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "book-genre-research/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=180,
        ) as response:
            raw_body = response.read().decode(
                "utf-8",
                errors="replace",
            )

    except urllib.error.HTTPError as error:
        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"OpenRouter HTTP {error.code}: "
            f"{body[:1500]}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"OpenRouter network error: {error}"
        ) from error

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "OpenRouter returned non-JSON response: "
            f"{raw_body[:1000]}"
        ) from error

    # OpenRouter may return HTTP 200 while the
    # upstream provider reports an error.
    if data.get("error"):
        error = data["error"]

        if isinstance(error, dict):
            code = error.get("code")
            message = error.get(
                "message",
                "Unknown provider error",
            )

            metadata = error.get("metadata") or {}

            error_type = (
                metadata.get("error_type")
                or metadata.get(
                    "provider_error_code"
                )
                or "unknown"
            )

            provider_name = metadata.get(
                "provider_name",
                data.get("provider", "unknown"),
            )

            raise RuntimeError(
                "OpenRouter provider error "
                f"(code={code}, "
                f"type={error_type}, "
                f"provider={provider_name}): "
                f"{message}"
            )

        raise RuntimeError(
            f"OpenRouter provider error: {error}"
        )

    choices = data.get("choices")

    if not isinstance(choices, list) or not choices:
        raise RuntimeError(
            "OpenRouter response contained no choices"
        )

    choice = choices[0]

    if not isinstance(choice, dict):
        raise RuntimeError(
            "OpenRouter returned invalid choice structure"
        )

    message = choice.get("message") or {}

    content = message.get("content")

    if not isinstance(content, str) or not content.strip():
        finish_reason = choice.get(
            "finish_reason"
        )

        raise RuntimeError(
            "OpenRouter returned empty final content "
            f"(finish_reason={finish_reason})"
        )

    return content.strip()


def query_model(
    prompt,
    provider,
    model,
    max_tokens=350,
):
    if provider == "groq":
        return query_groq(
            prompt,
            model,
            max_tokens=max_tokens,
        )

    if provider == "openrouter":
        return query_openrouter(
            prompt,
            model,
            max_tokens=max_tokens,
        )

    if provider == "gemini":
        return query_gemini(
            prompt,
            model,
            max_tokens=max_tokens,
        )

    raise ValueError(
        f"Unsupported provider: {provider}"
    )
