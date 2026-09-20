import argparse
import json
import time
from pathlib import Path

import pandas as pd

from agents.genre_filtering_agent import (
    load_union_record,
    build_prompt,
    deterministic_noise_filter,
    query_openrouter,
    extract_json,
    validate_filter_result,
)

INPUT = Path("data/clean_master_data.csv")
OUTPUT = Path("results/filtering/processed_book_genres.json")
OUTPUT_CSV = Path("results/filtering/processed_book_genres.csv")

DEFAULT_MODEL = "qwen/qwen3-30b-a3b-instruct-2507"


def save_checkpoint(results):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    rows = []

    for item in results:
        rows.append({
            "isbn13": item["isbn13"],
            "title": item["title"],
            "model": item["model"],
            "status": item["status"],
            "raw_tag_count": len(
                item["raw_merged_tags"]
            ),
            "final_tag_count": len(
                item["final_valid_tags"]
            ),
            "removed_tag_count": len(
                item["removed_tags"]
            ),
            "final_valid_tags": " | ".join(
                item["final_valid_tags"]
            ),
            "removed_tags": " | ".join(
                x["tag"]
                for x in item["removed_tags"]
            ),
            "error": item.get("error", ""),
        })

    pd.DataFrame(rows).to_csv(
        OUTPUT_CSV,
        index=False,
    )


def load_checkpoint():
    if not OUTPUT.exists():
        return []

    try:
        data = json.loads(
            OUTPUT.read_text(encoding="utf-8")
        )

        return data if isinstance(data, list) else []

    except Exception:
        return []


def process_book(row, model):
    isbn = str(row["isbn13"]).strip()
    title = str(row["title"]).strip()

    record = load_union_record(isbn)
    record["title"] = title

    raw_tags = record["raw_merged_tags"]

    candidates, deterministic_removed = (
        deterministic_noise_filter(raw_tags)
    )

    # No candidate genres at all.
    if not candidates:
        return {
            "isbn13": isbn,
            "title": title,
            "model": model,
            "status": "no_candidates",
            "source_tags": record["source_tags"],
            "source_provenance":
                record["source_provenance"],
            "raw_merged_tags": raw_tags,
            "final_valid_tags": [],
            "removed_tags":
                deterministic_removed,
            "error": "",
        }

    try:
        prompt = build_prompt(
            record,
            candidates,
        )

        raw_response = query_openrouter(
            prompt,
            model,
        )

        parsed = extract_json(raw_response)

        validated = validate_filter_result(
            parsed,
            candidates,
        )

        removed = (
            deterministic_removed
            + validated["removed_tags"]
        )

        return {
            "isbn13": isbn,
            "title": title,
            "model": model,
            "status": "success",
            "source_tags": record["source_tags"],
            "source_provenance":
                record["source_provenance"],
            "raw_merged_tags": raw_tags,
            "final_valid_tags":
                validated["final_valid_tags"],
            "removed_tags": removed,
            "error": "",
        }

    except Exception as exc:
        # Never silently claim failed LLM output
        # was successfully filtered.
        return {
            "isbn13": isbn,
            "title": title,
            "model": model,
            "status": "error",
            "source_tags": record["source_tags"],
            "source_provenance":
                record["source_provenance"],
            "raw_merged_tags": raw_tags,
            "final_valid_tags": candidates,
            "removed_tags":
                deterministic_removed,
            "error": str(exc),
        }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
    )

    args = parser.parse_args()

    df = pd.read_csv(
        INPUT,
        dtype={"isbn13": str},
    )

    if args.limit:
        df = df.head(args.limit)

    results = load_checkpoint()

    completed = {
        item["isbn13"]
        for item in results
        if item.get("status") in {
            "success",
            "no_candidates",
        }
    }

    print("MODEL       :", args.model)
    print("BOOKS       :", len(df))
    print("RESUMED     :", len(completed))
    print()

    total = len(df)

    for number, (_, row) in enumerate(
        df.iterrows(),
        start=1,
    ):
        isbn = str(row["isbn13"]).strip()

        if isbn in completed:
            print(
                f"[{number}/{total}] "
                f"{isbn} SKIP"
            )
            continue

        print(
            f"[{number}/{total}] "
            f"{isbn} filtering...",
            flush=True,
        )

        result = process_book(
            row,
            args.model,
        )

        # Replace previous failed attempt for ISBN.
        results = [
            x
            for x in results
            if x["isbn13"] != isbn
        ]

        results.append(result)

        save_checkpoint(results)

        print(
            f"    {result['status']} | "
            f"kept={len(result['final_valid_tags'])} | "
            f"removed={len(result['removed_tags'])}"
        )

        if result["status"] == "error":
            print(
                "    ERROR:",
                result["error"][:300],
            )

        time.sleep(args.delay)

    print()
    print("GENRE FILTERING COMPLETE")
    print("------------------------")
    print("Records:", len(results))

    success = sum(
        x["status"] == "success"
        for x in results
    )

    errors = sum(
        x["status"] == "error"
        for x in results
    )

    print("Success:", success)
    print("Errors :", errors)
    print("JSON   :", OUTPUT)
    print("CSV    :", OUTPUT_CSV)


if __name__ == "__main__":
    main()
