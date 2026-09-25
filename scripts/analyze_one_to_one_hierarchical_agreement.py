import csv
import json
from functools import lru_cache
from itertools import combinations
from pathlib import Path


INPUT = Path(
    "results/agreement/three_model_complete_interim.json"
)

OUTPUT = Path(
    "results/agreement/"
    "one_to_one_hierarchical_agreement_interim.csv"
)

SUMMARY = Path(
    "results/agreement/"
    "one_to_one_hierarchical_summary_interim.csv"
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


def common_prefix_depth(path_a, path_b):
    a = split_path(path_a)
    b = split_path(path_b)

    depth = 0

    for x, y in zip(a, b):
        if x != y:
            break
        depth += 1

    return depth


def path_similarity(path_a, path_b):
    """
    Prefix-based Dice similarity.

        2 * common_prefix_depth
        -----------------------
             depth_a + depth_b
    """

    a = split_path(path_a)
    b = split_path(path_b)

    if not a and not b:
        return 1.0

    if not a or not b:
        return 0.0

    shared = common_prefix_depth(
        path_a,
        path_b,
    )

    return (
        2.0 * shared
        / (len(a) + len(b))
    )


def maximum_matching_weight(paths_a, paths_b):
    """
    Exact maximum-weight one-to-one matching.

    Dynamic programming is used because annotation
    sets are small. Each path may participate in at
    most one matched pair.

    Zero-similarity matches do not increase the score.
    """

    a = tuple(sorted(paths_a))
    b = tuple(sorted(paths_b))

    if not a or not b:
        return 0.0

    # Keep the second dimension as the smaller set
    # because its membership is represented by a bitmask.
    if len(b) > len(a):
        a, b = b, a

    similarities = tuple(
        tuple(
            path_similarity(path_a, path_b)
            for path_b in b
        )
        for path_a in a
    )

    @lru_cache(maxsize=None)
    def solve(i, used_mask):
        if i == len(a):
            return 0.0

        # Option 1: leave this path unmatched.
        best = solve(
            i + 1,
            used_mask,
        )

        # Option 2: match it to one currently
        # unused path from the other set.
        for j in range(len(b)):
            if used_mask & (1 << j):
                continue

            score = (
                similarities[i][j]
                + solve(
                    i + 1,
                    used_mask | (1 << j),
                )
            )

            if score > best:
                best = score

        return best

    return solve(0, 0)


def one_to_one_similarity(set_a, set_b):
    """
    One-to-one hierarchical set similarity.

    Joint abstention -> None
    One-sided abstention -> 0

    For non-empty sets:

        2 * maximum matching weight
        ---------------------------
              |A| + |B|

    This penalizes unmatched extra paths and prevents
    reuse of a single target path.
    """

    if not set_a and not set_b:
        return None

    if not set_a or not set_b:
        return 0.0

    weight = maximum_matching_weight(
        set_a,
        set_b,
    )

    return (
        2.0 * weight
        / (len(set_a) + len(set_b))
    )


def mean(values):
    values = [
        value
        for value in values
        if value is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def main():
    records = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    rows = []

    summary = {}

    for field in [
        "genre_paths",
        "metadata_paths",
    ]:
        for model_a, model_b in combinations(
            MODELS,
            2,
        ):
            summary[
                (field, model_a, model_b)
            ] = {
                "scores": [],
                "evaluated_books": 0,
                "joint_abstentions": 0,
                "one_sided_abstentions": 0,
            }

    for record in records:
        row = {
            "isbn13": record["isbn13"],
            "title": record.get(
                "title",
                "",
            ),
        }

        for field in [
            "genre_paths",
            "metadata_paths",
        ]:
            short = (
                "genre"
                if field == "genre_paths"
                else "metadata"
            )

            for model_a, model_b in combinations(
                MODELS,
                2,
            ):
                set_a = set(
                    record["annotations"][
                        model_a
                    ].get(field, [])
                )

                set_b = set(
                    record["annotations"][
                        model_b
                    ].get(field, [])
                )

                score = one_to_one_similarity(
                    set_a,
                    set_b,
                )

                pair = (
                    f"{model_a}__{model_b}"
                )

                row[
                    f"{short}_one_to_one__{pair}"
                ] = (
                    ""
                    if score is None
                    else round(score, 6)
                )

                stats = summary[
                    (field, model_a, model_b)
                ]

                if not set_a and not set_b:
                    stats[
                        "joint_abstentions"
                    ] += 1
                else:
                    stats[
                        "evaluated_books"
                    ] += 1

                    stats[
                        "scores"
                    ].append(score)

                if bool(set_a) != bool(set_b):
                    stats[
                        "one_sided_abstentions"
                    ] += 1

        rows.append(row)

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
        "===== ONE-TO-ONE HIERARCHICAL AGREEMENT ====="
    )

    for (
        field,
        model_a,
        model_b,
    ), stats in summary.items():

        avg = mean(
            stats["scores"]
        )

        summary_rows.append({
            "field": field,
            "model_a": model_a,
            "model_b": model_b,
            "evaluated_books":
                stats["evaluated_books"],
            "joint_abstentions":
                stats["joint_abstentions"],
            "one_sided_abstentions":
                stats["one_sided_abstentions"],
            "mean_one_to_one_similarity":
                avg,
        })

        print()
        print(
            field,
            ":",
            model_a,
            "vs",
            model_b,
        )

        print(
            "  evaluated:",
            stats["evaluated_books"],
        )

        print(
            "  joint abstentions:",
            stats["joint_abstentions"],
        )

        print(
            "  one-sided abstentions:",
            stats["one_sided_abstentions"],
        )

        print(
            "  mean one-to-one similarity:",
            (
                round(avg, 4)
                if avg is not None
                else "N/A"
            ),
        )

    with SUMMARY.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(
                summary_rows[0].keys()
            ),
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
