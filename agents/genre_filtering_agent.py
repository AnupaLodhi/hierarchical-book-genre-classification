import argparse
import ast
import json
import re
from pathlib import Path

import pandas as pd


INPUT_CSV = Path("data/clean_master_data.csv")
OUTPUT_JSON = Path("results/filtering/processed_book_genres.json")
OUTPUT_CSV = Path("results/filtering/processed_book_genres.csv")


NOISE_TAGS = {
    "to-read",
    "currently-reading",
    "owned",
    "favorites",
    "favourites",
    "favorite-books",
    "books-i-own",
    "ebook",
    "ebooks",
    "kindle",
    "kindle ebooks",
    "audiobook",
    "audiobooks",
    "paperback",
    "hardcover",
}


PROMPT_TEMPLATE = """You are a book-tag evidence filtering agent.

Your task is NOT to perform final hierarchical classification.

You are given raw genre/category tags collected independently from:
- Open Library
- Goodreads
- Amazon

You are also given textual evidence about the book.

A candidate may be:
1. a genuine genre,
2. a useful metadata-like literary tag,
3. a broad but relevant category,
4. a publisher/imprint/franchise/store label,
5. scraping noise or a personal shelf tag,
6. factually inconsistent with the book.

TASK:
Evaluate ONLY the supplied candidate tags.

Keep a tag when it is relevant and supported or reasonably compatible
with the available book evidence.

Remove a tag when it is:
- clearly contradictory to the book,
- scraping/navigation noise,
- a personal shelf/status label,
- merely a publisher, imprint, franchise, storefront, or product label
  with no useful genre/metadata meaning,
- unsupported and clearly misleading.

IMPORTANT:
- Do NOT invent new tags.
- Do NOT map tags to the final genre hierarchy yet.
- Do NOT force a tag to be a genre.
- Useful metadata-like tags such as Young Adult, Middle Grade,
  Short Stories, Graphic Novel, or similar evidence may be retained.
- Treat Open Library, Goodreads, and Amazon as evidence sources.
  Do not automatically trust or reject a tag merely because of its source.
- If textual evidence is insufficient to disprove a plausible candidate,
  prefer retaining it rather than fabricating certainty.

Return ONLY valid JSON:

{{
  "final_valid_tags": ["tag"],
  "removed_tags": [
    {{
      "tag": "tag",
      "reason": "brief evidence-based reason"
    }}
  ]
}}

ISBN: {isbn13}
Title: {title}

Candidate tags:
{candidate_tags}

Source provenance:
{source_provenance}

Book blurbs:
{blurbs}

Book reviews:
{reviews}
"""


def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def split_pipe(value):
    text = clean_text(value)
    if not text:
        return []

    result = []
    seen = set()

    for item in text.split("|"):
        item = clean_text(item)
        key = item.casefold()

        if item and key not in seen:
            seen.add(key)
            result.append(item)

    return result


def unique_tags(tags):
    result = []
    seen = set()

    for tag in tags:
        tag = clean_text(tag)
        key = tag.casefold()

        if tag and key not in seen:
            seen.add(key)
            result.append(tag)

    return result


def build_record(row):
    source_tags = {
        "OpenLibrary": split_pipe(row.get("openlibrary_genres")),
        "Goodreads": split_pipe(row.get("goodreads_genres")),
        "Amazon": split_pipe(row.get("amazon_genres")),
    }

    provenance = {}

    for source, tags in source_tags.items():
        for tag in tags:
            provenance.setdefault(tag, []).append(source)

    raw_tags = unique_tags(
        source_tags["OpenLibrary"]
        + source_tags["Goodreads"]
        + source_tags["Amazon"]
    )

    return {
        "isbn13": clean_text(row.get("isbn13")),
        "title": clean_text(row.get("title")),
        "source_tags": source_tags,
        "raw_merged_tags": raw_tags,
        "source_provenance": provenance,
        "blurbs": clean_text(row.get("blurbs")),
        "reviews": clean_text(row.get("reviews")),
    }



def load_union_record(isbn):
    """Load the precomputed genre union and source provenance."""

    path = Path("data/genre union") / f"{isbn}.json"

    if not path.exists():
        raise FileNotFoundError(
            f"Genre union missing for ISBN {isbn}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    return {
        "isbn13": str(data.get("isbn13", isbn)),
        "source_tags": data.get("source_genres") or {},
        "raw_merged_tags": data.get("genre_union") or [],
        "source_provenance": data.get("provenance") or {},
    }


def deterministic_noise_filter(tags):
    kept = []
    removed = []

    for tag in tags:
        normalized = tag.casefold().strip()

        if normalized in NOISE_TAGS:
            removed.append({
                "tag": tag,
                "reason": "Deterministic removal: format, reading-status, or storefront noise."
            })
        else:
            kept.append(tag)

    return kept, removed


def extract_json(text):
    if not text:
        return {}

    match = re.search(
        r"```json\s*(\{.*?\})\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    candidate = match.group(1) if match else text

    if not match:
        start = candidate.find("{")
        end = candidate.rfind("}")

        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}


def load_evidence(isbn):
    """Load source-aware evidence from old-style research files."""

    blurb_dir = Path("data/book blurb")
    review_dir = Path("data/book reviews")

    blurbs = []
    reviews = []

    for path in sorted(blurb_dir.glob(f"{isbn} b *.txt")):
        parts = path.stem.split(" b ", 1)

        if len(parts) != 2:
            continue

        remainder = parts[1].rsplit(" ", 1)
        source = remainder[0] if remainder else "unknown"

        content = clean_text(
            path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )

        if content:
            blurbs.append(
                f"[{source.title()}] {content}"
            )

    for path in sorted(review_dir.glob(f"{isbn} r *.txt")):
        parts = path.stem.split(" r ", 1)

        if len(parts) != 2:
            continue

        remainder = parts[1].rsplit(" ", 1)
        source = remainder[0] if remainder else "unknown"

        content = clean_text(
            path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )

        if content:
            reviews.append(
                f"[{source.title()}] {content}"
            )

    return {
        "blurbs": blurbs,
        "reviews": reviews,
    }

def build_prompt(record, candidates):
    evidence = load_evidence(record["isbn13"])

    provenance = {
        tag: record["source_provenance"].get(tag, [])
        for tag in candidates
    }

    return PROMPT_TEMPLATE.format(
        isbn13=record["isbn13"],
        title=record["title"],
        candidate_tags=json.dumps(
            candidates,
            ensure_ascii=False,
            indent=2,
        ),
        source_provenance=json.dumps(
            provenance,
            ensure_ascii=False,
            indent=2,
        ),
        blurbs="\n\n".join(evidence["blurbs"]) or "No blurb available.",
        reviews="\n\n".join(evidence["reviews"]) or "No reviews available.",
    )


def load_openrouter_key():
    env_path = Path(".env")

    if not env_path.exists():
        raise RuntimeError(".env file not found")

    for line in env_path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()

        if line.startswith("OPENROUTER_API_KEY="):
            key = line.split("=", 1)[1].strip()

            if key:
                return key

    raise RuntimeError(
        "OPENROUTER_API_KEY missing from .env"
    )


def query_openrouter(prompt, model, max_tokens=1500):
    import requests

    key = load_openrouter_key()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(
            f"OpenRouter HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "OpenRouter response missing choices/message: "
            + json.dumps(data, ensure_ascii=False)[:1000]
        ) from exc

    content = message.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()

    # Some reasoning models may place the useful output
    # in a reasoning field instead of normal content.
    reasoning = message.get("reasoning")

    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()

    raise RuntimeError(
        "OpenRouter returned no usable text. Message: "
        + json.dumps(message, ensure_ascii=False)[:1500]
    )


def validate_filter_result(result, candidates):
    """
    Enforce closed-set filtering.

    The LLM cannot introduce tags that were not
    supplied in the original candidate set.
    """

    if not isinstance(result, dict):
        raise ValueError("LLM output is not a JSON object")

    lookup = {
        tag.casefold(): tag
        for tag in candidates
    }

    kept_raw = result.get("final_valid_tags") or []
    removed_raw = result.get("removed_tags") or []

    kept = []
    kept_keys = set()

    for item in kept_raw:
        if not isinstance(item, str):
            continue

        key = item.strip().casefold()

        if key in lookup and key not in kept_keys:
            kept.append(lookup[key])
            kept_keys.add(key)

    reasons = {}

    for item in removed_raw:
        if not isinstance(item, dict):
            continue

        tag = clean_text(item.get("tag"))
        reason = clean_text(item.get("reason"))

        key = tag.casefold()

        if (
            key in lookup
            and key not in kept_keys
            and key not in reasons
        ):
            reasons[key] = (
                reason or "Removed by filtering model."
            )

    # Every original candidate must be accounted for.
    # If the model omitted a candidate, conservatively
    # retain it rather than silently deleting evidence.
    for tag in candidates:
        key = tag.casefold()

        if key not in kept_keys and key not in reasons:
            kept.append(tag)
            kept_keys.add(key)

    removed = []

    for tag in candidates:
        key = tag.casefold()

        if key in reasons and key not in kept_keys:
            removed.append({
                "tag": tag,
                "reason": reasons[key],
            })

    return {
        "final_valid_tags": kept,
        "removed_tags": removed,
    }
