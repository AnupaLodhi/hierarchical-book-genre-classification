import csv
import json
from itertools import combinations
from pathlib import Path


INPUT = Path(
    "results/agreement/three_model_complete_interim.json"
)

OUTPUT_DIR = Path("results/agreement")

MODELS = [
    "qwen_groq",
    "gpt_oss_groq",
    "gpt_oss_20b",
]


def path_set(annotation, field):
    return set(annotation.get(field, []))


def jaccard(a, b):
    if not a and not b:
        return 1.0

    union = a | b

    if not union:
        return 1.0

    return len(a & b) / len(union)


def three_way_jaccard(a, b, c):
    union = a | b | c

    if not union:
        return 1.0

    intersection = a & b & c

    return len(intersection) / len(union)


def exact_three_way(a, b, c):
    return a == b == c


def pair_name(a, b):
    return f"{a}__{b}"


def mean(values):
    if not values:
        return 0.0

    return sum(values) / len(values)


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    per_book_rows = []

    pairwise_values = {
        "genre": {},
        "metadata": {},
    }

    for field in pairwise_values:
        for model_a, model_b in combinations(MODELS, 2):
            pairwise_values[field][
                pair_name(model_a, model_b)
            ] = []

    genre_exact_count = 0
    metadata_exact_count = 0
    combined_exact_count = 0

    genre_three_way_scores = []
    metadata_three_way_scores = []

    for record in records:
        annotations = record["annotations"]

        genre_sets = {
            model: path_set(
                annotations[model],
                "genre_paths",
            )
            for model in MODELS
        }

        metadata_sets = {
            model: path_set(
                annotations[model],
                "metadata_paths",
            )
            for model in MODELS
        }

        genre_exact = exact_three_way(
            genre_sets[MODELS[0]],
            genre_sets[MODELS[1]],
            genre_sets[MODELS[2]],
        )

        metadata_exact = exact_three_way(
            metadata_sets[MODELS[0]],
            metadata_sets[MODELS[1]],
            metadata_sets[MODELS[2]],
        )

        combined_exact = (
            genre_exact
            and metadata_exact
        )

        genre_exact_count += int(genre_exact)
        metadata_exact_count += int(metadata_exact)
        combined_exact_count += int(combined_exact)

        genre_three_way = three_way_jaccard(
            genre_sets[MODELS[0]],
            genre_sets[MODELS[1]],
            genre_sets[MODELS[2]],
        )

        metadata_three_way = three_way_jaccard(
            metadata_sets[MODELS[0]],
            metadata_sets[MODELS[1]],
            metadata_sets[MODELS[2]],
        )

        genre_three_way_scores.append(
            genre_three_way
        )

        metadata_three_way_scores.append(
            metadata_three_way
        )

        row = {
            "isbn13": record["isbn13"],
            "title": record.get("title", ""),
            "genre_exact_3way": genre_exact,
            "metadata_exact_3way": metadata_exact,
            "combined_exact_3way": combined_exact,
            "genre_3way_jaccard": round(
                genre_three_way,
                6,
            ),
            "metadata_3way_jaccard": round(
                metadata_three_way,
                6,
            ),
        }

        for model_a, model_b in combinations(
            MODELS,
            2,
        ):
            name = pair_name(
                model_a,
                model_b,
            )

            genre_score = jaccard(
                genre_sets[model_a],
                genre_sets[model_b],
            )

            metadata_score = jaccard(
                metadata_sets[model_a],
                metadata_sets[model_b],
            )

            pairwise_values["genre"][
                name
            ].append(genre_score)

            pairwise_values["metadata"][
                name
            ].append(metadata_score)

            row[
                f"genre_jaccard__{name}"
            ] = round(genre_score, 6)

            row[
                f"metadata_jaccard__{name}"
            ] = round(metadata_score, 6)

        per_book_rows.append(row)

    per_book_path = (
        OUTPUT_DIR
        / "per_book_agreement_interim.csv"
    )

    with per_book_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(
                per_book_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(per_book_rows)

    summary_rows = []

    n = len(records)

    summary_rows.extend([
        {
            "metric": "books_analyzed",
            "value": n,
        },
        {
            "metric": "genre_exact_3way_count",
            "value": genre_exact_count,
        },
        {
            "metric": "genre_exact_3way_rate",
            "value": genre_exact_count / n,
        },
        {
            "metric": "metadata_exact_3way_count",
            "value": metadata_exact_count,
        },
        {
            "metric": "metadata_exact_3way_rate",
            "value": metadata_exact_count / n,
        },
        {
            "metric": "combined_exact_3way_count",
            "value": combined_exact_count,
        },
        {
            "metric": "combined_exact_3way_rate",
            "value": combined_exact_count / n,
        },
        {
            "metric": "mean_genre_3way_jaccard",
            "value": mean(
                genre_three_way_scores
            ),
        },
        {
            "metric": "mean_metadata_3way_jaccard",
            "value": mean(
                metadata_three_way_scores
            ),
        },
    ])

    for field in [
        "genre",
        "metadata",
    ]:
        for pair, values in (
            pairwise_values[field].items()
        ):
            summary_rows.append({
                "metric": (
                    f"mean_{field}_jaccard__"
                    f"{pair}"
                ),
                "value": mean(values),
            })

    summary_path = (
        OUTPUT_DIR
        / "agreement_summary_interim.csv"
    )

    with summary_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "metric",
                "value",
            ],
        )

        writer.writeheader()
        writer.writerows(summary_rows)

    disagreement_rows = [
        row
        for row in per_book_rows
        if not row["combined_exact_3way"]
    ]

    disagreement_rows.sort(
        key=lambda row: (
            row["genre_3way_jaccard"]
            + row["metadata_3way_jaccard"]
        )
    )

    disagreement_path = (
        OUTPUT_DIR
        / "disagreement_cases_interim.csv"
    )

    with disagreement_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(
                disagreement_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            disagreement_rows
        )

    print(
        "===== AGREEMENT ANALYSIS ====="
    )
    print("Books:", n)

    print()
    print(
        "Genre exact 3-way:",
        genre_exact_count,
        f"({genre_exact_count / n:.2%})",
    )

    print(
        "Metadata exact 3-way:",
        metadata_exact_count,
        f"({metadata_exact_count / n:.2%})",
    )

    print(
        "Combined exact 3-way:",
        combined_exact_count,
        f"({combined_exact_count / n:.2%})",
    )

    print()
    print(
        "Mean genre 3-way Jaccard:",
        round(
            mean(genre_three_way_scores),
            4,
        ),
    )

    print(
        "Mean metadata 3-way Jaccard:",
        round(
            mean(metadata_three_way_scores),
            4,
        ),
    )

    print()
    print("===== PAIRWISE JACCARD =====")

    for field in [
        "genre",
        "metadata",
    ]:
        print(f"\n{field.upper()}")

        for pair, values in (
            pairwise_values[field].items()
        ):
            print(
                pair,
                ":",
                round(mean(values), 4),
            )

    print()
    print("Saved:")
    print(" ", summary_path)
    print(" ", per_book_path)
    print(" ", disagreement_path)


if __name__ == "__main__":
    main()
