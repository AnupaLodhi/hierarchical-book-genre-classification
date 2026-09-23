import argparse
import csv
import json
import time
from pathlib import Path

from agents.annotation_agent import (
    load_taxonomies,
    retrieve_candidate_paths,
    build_annotation_prompt,
    validate_annotation,
)

from agents.llm_providers import query_model

INPUT = Path("results/filtering/processed_book_genres.json")
OUTPUT = Path("results/annotations/multi_llm_annotations.json")
CSV_OUTPUT = Path("results/annotations/multi_llm_annotations.csv")

MODELS = {
    "qwen_groq": {
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "max_tokens": 700,
    },
    "gpt_oss_groq": {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "max_tokens": 700,
    },
    "gpt_oss_20b": {
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "max_tokens": 1000,
    },
}

def load_existing():
    if not OUTPUT.exists():
        return {}

    data = json.loads(
        OUTPUT.read_text(encoding="utf-8")
    )

    return {
        str(x["isbn13"]): x
        for x in data
    }


def save_checkpoint(records):
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    ordered = list(records.values())

    OUTPUT.write_text(
        json.dumps(
            ordered,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with CSV_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        fields = [
            "isbn13",
            "title",
            "filtered_tags",
        ]

        for name in MODELS:
            fields += [
                f"{name}_status",
                f"{name}_genre_paths",
                f"{name}_metadata_paths",
                f"{name}_error",
            ]

        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )

        writer.writeheader()

        for rec in ordered:
            row = {
                "isbn13": rec["isbn13"],
                "title": rec.get("title", ""),
                "filtered_tags": " | ".join(
                    rec.get("filtered_tags", [])
                ),
            }

            for name in MODELS:
                ann = rec.get(
                    "annotations", {}
                ).get(name, {})

                row[f"{name}_status"] = ann.get(
                    "status", ""
                )

                row[f"{name}_genre_paths"] = " | ".join(
                    ann.get("genre_paths", [])
                )

                row[f"{name}_metadata_paths"] = " | ".join(
                    ann.get("metadata_paths", [])
                )

                row[f"{name}_error"] = ann.get(
                    "error", ""
                )

            writer.writerow(row)



def parse_annotation_json_strict(raw):
    """
    Parse annotation output without silently converting malformed
    model responses into empty annotations.

    Explicit empty lists are valid abstentions.
    Malformed/truncated JSON is an error.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeError(
            "Model returned empty annotation response"
        )

    text = raw.strip()

    # Accept a single Markdown JSON code fence.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().lower() in {
            "```",
            "```json",
        }:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # Some models may add short text around the JSON.
    # Extract only when both complete object boundaries exist.
    if not text.startswith("{") or not text.endswith("}"):
        start = text.find("{")
        end = text.rfind("}")

        if start < 0 or end <= start:
            raise RuntimeError(
                "Model returned incomplete or non-JSON annotation"
            )

        text = text[start:end + 1].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Model returned malformed annotation JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(
            "Annotation response must be a JSON object"
        )

    required = {
        "genre_paths",
        "metadata_paths",
    }

    missing = required - set(parsed)

    if missing:
        raise RuntimeError(
            "Annotation response missing required keys: "
            + ", ".join(sorted(missing))
        )

    if not isinstance(parsed["genre_paths"], list):
        raise RuntimeError(
            "genre_paths must be a JSON list"
        )

    if not isinstance(parsed["metadata_paths"], list):
        raise RuntimeError(
            "metadata_paths must be a JSON list"
        )

    for field in ("genre_paths", "metadata_paths"):
        if not all(
            isinstance(value, str)
            for value in parsed[field]
        ):
            raise RuntimeError(
                f"{field} must contain only strings"
            )

    return parsed


def annotate_model(
    book,
    config,
    taxonomies,
    candidates,
):
    prompt = build_annotation_prompt(
        book,
        book["final_valid_tags"],
        candidates["genre_paths"],
        candidates["metadata_paths"],
    )

    raw = query_model(
        prompt,
        provider=config["provider"],
        model=config["model"],
        max_tokens=config.get("max_tokens", 350),
    )

    try:
        parsed = parse_annotation_json_strict(raw)
    except RuntimeError as exc:
        preview = raw.strip().replace("\\n", " ")[:1500]

        raise RuntimeError(
            f"{exc} | RAW_RESPONSE_PREVIEW: {preview}"
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(
            "Model response could not be parsed as a JSON object"
        )

    if (
        "genre_paths" not in parsed
        or "metadata_paths" not in parsed
    ):
        raise RuntimeError(
            "Model response missing required annotation keys"
        )

    return validate_annotation(
        parsed,
        taxonomies,
        candidate_paths=candidates,
    )


def run(limit=None, delay=0.2):
    books = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    if limit is not None:
        books = books[:limit]

    taxonomies = load_taxonomies()
    records = load_existing()

    total = len(books)

    for index, book in enumerate(
        books,
        start=1,
    ):
        isbn = str(book["isbn13"])

        record = records.get(
            isbn,
            {
                "isbn13": isbn,
                "title": book.get("title", ""),
                "filtered_tags": book.get(
                    "final_valid_tags", []
                ),
                "annotations": {},
            },
        )

        # Keep only annotations belonging to the currently
        # configured annotators. Historical provider/model tests
        # are preserved separately in provider_tests/.
        annotations = record.get("annotations", {})

        record["annotations"] = {
            name: annotations[name]
            for name in MODELS
            if name in annotations
        }

        # Refresh source fields from the current filtering output.
        record["title"] = book.get("title", "")
        record["filtered_tags"] = book.get(
            "final_valid_tags", []
        )

        tags = book.get(
            "final_valid_tags", []
        )

        if not tags:
            print(
                f"[{index}/{total}] "
                f"{isbn} - no filtered tags"
            )

            for name, config in MODELS.items():
                record["annotations"][name] = {
                    "status": "no_filtered_tags",
                    "provider": config["provider"],
                    "model": config["model"],
                    "genre_paths": [],
                    "metadata_paths": [],
                }

            records[isbn] = record
            save_checkpoint(records)
            continue

        candidates = retrieve_candidate_paths(
            tags,
            taxonomies,
        )

        print(
            f"\n[{index}/{total}] "
            f"{isbn} - {book.get('title', '')}"
        )

        for name, config in MODELS.items():

            old = record["annotations"].get(
                name, {}
            )

            if (
                old.get("status") == "success"
                and old.get("provider") == config["provider"]
                and old.get("model") == config["model"]
            ):
                print(
                    f"  {name}: checkpoint ✓"
                )
                continue

            print(
                f"  {name}: querying..."
            )

            try:
                result = annotate_model(
                    book,
                    config,
                    taxonomies,
                    candidates,
                )

                record["annotations"][name] = {
                    "status": "success",
                    "provider": config["provider"],
                    "model": config["model"],
                    **result,
                }

                print(
                    f"  {name}: success "
                    f"(G={len(result['genre_paths'])}, "
                    f"M={len(result['metadata_paths'])})"
                )

            except Exception as e:
                record["annotations"][name] = {
                    "status": "error",
                    "provider": config["provider"],
                    "model": config["model"],
                    "genre_paths": [],
                    "metadata_paths": [],
                    "error": str(e),
                }

                print(
                    f"  {name}: ERROR {e}"
                )

            records[isbn] = record
            save_checkpoint(records)

            if delay:
                time.sleep(delay)

    print("\n===== FINAL STATUS =====")

    counts = {}

    for rec in records.values():
        for name, ann in rec.get(
            "annotations", {}
        ).items():
            key = (
                name,
                ann.get("status", "missing"),
            )

            counts[key] = (
                counts.get(key, 0) + 1
            )

    for key in sorted(counts):
        print(
            f"{key[0]:8} "
            f"{key[1]:18} "
            f"{counts[key]}"
        )

    print(
        "\nJSON:",
        OUTPUT,
    )
    print(
        "CSV :",
        CSV_OUTPUT,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
    )

    args = parser.parse_args()

    run(
        limit=args.limit,
        delay=args.delay,
    )
