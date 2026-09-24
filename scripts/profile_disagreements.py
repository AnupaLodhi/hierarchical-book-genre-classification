import csv
import json
from collections import Counter
from pathlib import Path


INPUT = Path(
    "results/agreement/three_model_complete_interim.json"
)

OUTPUT = Path(
    "results/agreement/dispute_profile_interim.csv"
)

SUMMARY = Path(
    "results/agreement/dispute_summary_interim.csv"
)

MODELS = [
    "qwen_groq",
    "gpt_oss_groq",
    "gpt_oss_20b",
]


def split_path(path):
    return tuple(
        part.strip()
        for part in path.split(" / ")
        if part.strip()
    )


def is_ancestor(a, b):
    a = split_path(a)
    b = split_path(b)

    return (
        len(a) < len(b)
        and b[:len(a)] == a
    )


def ancestor_related(a, b):
    return (
        is_ancestor(a, b)
        or is_ancestor(b, a)
    )


def classify_path(path, model_sets):
    voters = [
        model
        for model, paths in model_sets.items()
        if path in paths
    ]

    vote_count = len(voters)

    if vote_count == 3:
        category = "unanimous"

    elif vote_count == 2:
        category = "majority"

    else:
        # Exact singleton. Check whether another
        # model selected an ancestor/descendant.
        related_models = []

        for model, paths in model_sets.items():

            if model in voters:
                continue

            if any(
                ancestor_related(path, other)
                for other in paths
            ):
                related_models.append(model)

        if related_models:
            category = "hierarchical_singleton"
        else:
            category = "isolated_singleton"

    return {
        "category": category,
        "vote_count": vote_count,
        "voters": voters,
    }


def main():
    records = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    rows = []
    counts = Counter()

    book_counts = {
        "genre": Counter(),
        "metadata": Counter(),
    }

    for record in records:

        for field, short in [
            ("genre_paths", "genre"),
            ("metadata_paths", "metadata"),
        ]:

            model_sets = {
                model: set(
                    record["annotations"][
                        model
                    ].get(field, [])
                )
                for model in MODELS
            }

            union = set().union(
                *model_sets.values()
            )

            categories_in_book = set()

            for path in sorted(union):

                result = classify_path(
                    path,
                    model_sets,
                )

                category = result["category"]

                counts[
                    (short, category)
                ] += 1

                categories_in_book.add(
                    category
                )

                rows.append({
                    "isbn13":
                        record["isbn13"],
                    "title":
                        record.get("title", ""),
                    "field":
                        short,
                    "path":
                        path,
                    "depth":
                        len(split_path(path)),
                    "category":
                        category,
                    "vote_count":
                        result["vote_count"],
                    "qwen_groq":
                        int(
                            path in model_sets[
                                "qwen_groq"
                            ]
                        ),
                    "gpt_oss_groq":
                        int(
                            path in model_sets[
                                "gpt_oss_groq"
                            ]
                        ),
                    "gpt_oss_20b":
                        int(
                            path in model_sets[
                                "gpt_oss_20b"
                            ]
                        ),
                    "voters":
                        "|".join(
                            result["voters"]
                        ),
                })

            # Explicitly record complete field
            # abstention at book level.
            if not union:
                book_counts[short][
                    "all_models_abstain"
                ] += 1

            for category in categories_in_book:
                book_counts[short][
                    category
                ] += 1

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)

    summary_rows = []

    print(
        "===== PATH-LEVEL DISPUTE PROFILE ====="
    )

    for short in [
        "genre",
        "metadata",
    ]:

        print()
        print(short.upper())

        relevant = {
            category: count
            for (
                field,
                category
            ), count in counts.items()
            if field == short
        }

        total = sum(
            relevant.values()
        )

        print(
            "Total unique book-path decisions:",
            total,
        )

        for category in [
            "unanimous",
            "majority",
            "hierarchical_singleton",
            "isolated_singleton",
        ]:

            count = relevant.get(
                category,
                0,
            )

            rate = (
                count / total
                if total
                else 0
            )

            print(
                f"  {category:24}",
                f"{count:4}",
                f"{rate:.2%}",
            )

            summary_rows.append({
                "level": "path",
                "field": short,
                "category": category,
                "count": count,
                "denominator": total,
                "rate": rate,
            })

    print()
    print(
        "===== BOOK-LEVEL PRESENCE ====="
    )

    for short in [
        "genre",
        "metadata",
    ]:

        print()
        print(short.upper())

        for category, count in sorted(
            book_counts[short].items()
        ):

            print(
                f"  {category:24}",
                f"{count:4}",
                f"{count / len(records):.2%}",
            )

            summary_rows.append({
                "level": "book",
                "field": short,
                "category": category,
                "count": count,
                "denominator": len(records),
                "rate":
                    count / len(records),
            })

    with SUMMARY.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "level",
                "field",
                "category",
                "count",
                "denominator",
                "rate",
            ],
        )

        writer.writeheader()
        writer.writerows(
            summary_rows
        )

    print()
    print("Saved:")
    print(" ", OUTPUT)
    print(" ", SUMMARY)


if __name__ == "__main__":
    main()
