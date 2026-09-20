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

from agents.genre_filtering_agent import (
    query_openrouter,
    extract_json,
)

INPUT = Path("results/filtering/processed_book_genres.json")
OUTPUT = Path("results/annotations/multi_llm_annotations.json")
CSV_OUTPUT = Path("results/annotations/multi_llm_annotations.csv")

MODELS = {
    "llama": "meta-llama/llama-3.3-70b-instruct",
    "qwen": "qwen/qwen-2.5-72b-instruct",
    "mistral": "mistralai/mistral-small-2603",
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


def annotate_model(
    book,
    model,
    taxonomies,
    candidates,
):
    prompt = build_annotation_prompt(
        book,
        book["final_valid_tags"],
        candidates["genre_paths"],
        candidates["metadata_paths"],
    )

    raw = query_openrouter(
        prompt,
        model,
        max_tokens=350,
    )

    parsed = extract_json(raw)

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

        tags = book.get(
            "final_valid_tags", []
        )

        if not tags:
            print(
                f"[{index}/{total}] "
                f"{isbn} - no filtered tags"
            )

            for name, model in MODELS.items():
                record["annotations"][name] = {
                    "status": "no_filtered_tags",
                    "model": model,
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

        for name, model in MODELS.items():

            old = record["annotations"].get(
                name, {}
            )

            if old.get("status") == "success":
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
                    model,
                    taxonomies,
                    candidates,
                )

                record["annotations"][name] = {
                    "status": "success",
                    "model": model,
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
                    "model": model,
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
