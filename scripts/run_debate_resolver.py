import argparse
import json
import time
from collections import Counter
from pathlib import Path

from agents.annotation_agent import load_taxonomies
from agents.debate_resolver import resolve_debate

INPUT = Path("results/resolution/debate_inputs.json")
OUTPUT = Path("results/resolution/debate_resolutions.json")


def load_existing():
    if not OUTPUT.exists():
        return {}

    data = json.loads(
        OUTPUT.read_text(encoding="utf-8")
    )

    return {
        x["isbn13"]: x
        for x in data
    }


def save(records):
    OUTPUT.write_text(
        json.dumps(
            list(records.values()),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def run(limit=None, delay=1.0):
    books = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    if limit is not None:
        books = books[:limit]

    taxonomies = load_taxonomies()
    records = load_existing()

    total = len(books)

    for i, book in enumerate(books, 1):
        isbn = book["isbn13"]
        title = book.get("title", "")

        print(
            f"\n[{i}/{total}] "
            f"{isbn} - {title}"
        )

        existing = records.get(isbn)

        if existing and existing.get("status") == "success":
            print("  checkpoint ✓")
            continue

        try:
            print("  resolving...")

            result = resolve_debate(
                book,
                taxonomies,
            )

            records[isbn] = {
                "isbn13": isbn,
                "title": title,
                "available_original_models":
                    book.get("available_count", 0),
                "resolver_model":
                    result["model"],
                "status": "success",
                "genre_paths":
                    result["genre_paths"],
                "metadata_paths":
                    result["metadata_paths"],
                "error": "",
            }

            print(
                "  success ✓",
                f"G={len(result['genre_paths'])}",
                f"M={len(result['metadata_paths'])}",
            )

        except Exception as e:
            records[isbn] = {
                "isbn13": isbn,
                "title": title,
                "available_original_models":
                    book.get("available_count", 0),
                "resolver_model":
                    "nex-agi/nex-n2.5-pro:free",
                "status": "error",
                "genre_paths": [],
                "metadata_paths": [],
                "error": str(e),
            }

            print(
                "  ERROR:",
                str(e)[:300],
            )

        save(records)

        if delay:
            time.sleep(delay)

    counts = Counter(
        x.get("status", "missing")
        for x in records.values()
    )

    print("\n===== DEBATE STATUS =====")

    for status, count in sorted(counts.items()):
        print(f"{status:10} {count}")

    print("\nJSON:", OUTPUT)


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
        default=1.0,
    )

    args = parser.parse_args()

    run(
        limit=args.limit,
        delay=args.delay,
    )
