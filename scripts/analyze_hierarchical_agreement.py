import csv
import json
from itertools import combinations
from pathlib import Path


INPUT = Path(
    "results/agreement/three_model_complete_interim.json"
)

OUTPUT = Path(
    "results/agreement/hierarchical_agreement_interim.csv"
)

SUMMARY = Path(
    "results/agreement/hierarchical_summary_interim.csv"
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

    similarity =
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


def is_ancestor(path_a, path_b):
    """
    True when A is a strict ancestor of B.
    """

    a = split_path(path_a)
    b = split_path(path_b)

    return (
        len(a) < len(b)
        and b[:len(a)] == a
    )


def best_match_score(source, target):
    """
    For each path in source, find its
    most similar path in target.
    """

    if not source:
        return 0.0

    if not target:
        return 0.0

    scores = []

    for path_a in source:
        best = max(
            path_similarity(path_a, path_b)
            for path_b in target
        )
        scores.append(best)

    return sum(scores) / len(scores)


def symmetric_set_similarity(set_a, set_b):
    """
    Symmetric best-match similarity.

    Empty/empty is returned as None so
    joint abstention is NOT counted as
    semantic agreement.
    """

    if not set_a and not set_b:
        return None

    if not set_a or not set_b:
        return 0.0

    a_to_b = best_match_score(
        set_a,
        set_b,
    )

    b_to_a = best_match_score(
        set_b,
        set_a,
    )

    return (a_to_b + b_to_a) / 2.0


def has_ancestor_relation(set_a, set_b):
    for a in set_a:
        for b in set_b:
            if (
                is_ancestor(a, b)
                or is_ancestor(b, a)
            ):
                return True

    return False


def has_exact_path_overlap(set_a, set_b):
    return bool(set_a & set_b)


def has_zero_prefix_pair(set_a, set_b):
    """
    True when at least one cross-model path
    pair lies in completely different
    top-level branches.

    This is descriptive; it does NOT mean
    the entire annotation sets disagree.
    """

    if not set_a or not set_b:
        return False

    return any(
        common_prefix_depth(a, b) == 0
        for a in set_a
        for b in set_b
    )


def mean(values):
    values = [
        x for x in values
        if x is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def main():
    records = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    rows = []

    summary_values = {}

    for field in [
        "genre_paths",
        "metadata_paths",
    ]:

        for model_a, model_b in combinations(
            MODELS,
            2,
        ):
            key = (
                field,
                model_a,
                model_b,
            )

            summary_values[key] = {
                "similarities": [],
                "joint_abstentions": 0,
                "one_sided_abstentions": 0,
                "ancestor_relation_books": 0,
                "exact_overlap_books": 0,
                "zero_prefix_books": 0,
                "evaluated_books": 0,
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

                key = (
                    field,
                    model_a,
                    model_b,
                )

                stats = summary_values[key]

                similarity = (
                    symmetric_set_similarity(
                        set_a,
                        set_b,
                    )
                )

                joint_empty = (
                    not set_a
                    and not set_b
                )

                one_empty = (
                    bool(set_a)
                    != bool(set_b)
                )

                ancestor = (
                    has_ancestor_relation(
                        set_a,
                        set_b,
                    )
                )

                exact_overlap = (
                    has_exact_path_overlap(
                        set_a,
                        set_b,
                    )
                )

                zero_prefix = (
                    has_zero_prefix_pair(
                        set_a,
                        set_b,
                    )
                )

                pair = (
                    f"{model_a}__{model_b}"
                )

                row[
                    f"{short}_hier_sim__{pair}"
                ] = (
                    ""
                    if similarity is None
                    else round(
                        similarity,
                        6,
                    )
                )

                row[
                    f"{short}_ancestor_relation__{pair}"
                ] = ancestor

                row[
                    f"{short}_exact_overlap__{pair}"
                ] = exact_overlap

                row[
                    f"{short}_zero_prefix__{pair}"
                ] = zero_prefix

                if joint_empty:
                    stats[
                        "joint_abstentions"
                    ] += 1

                else:
                    stats[
                        "evaluated_books"
                    ] += 1

                    stats[
                        "similarities"
                    ].append(
                        similarity
                    )

                if one_empty:
                    stats[
                        "one_sided_abstentions"
                    ] += 1

                if ancestor:
                    stats[
                        "ancestor_relation_books"
                    ] += 1

                if exact_overlap:
                    stats[
                        "exact_overlap_books"
                    ] += 1

                if zero_prefix:
                    stats[
                        "zero_prefix_books"
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
        "===== HIERARCHICAL AGREEMENT ====="
    )

    for (
        field,
        model_a,
        model_b,
    ), stats in summary_values.items():

        avg = mean(
            stats["similarities"]
        )

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
            stats[
                "one_sided_abstentions"
            ],
        )

        print(
            "  mean hierarchical similarity:",
            (
                round(avg, 4)
                if avg is not None
                else "N/A"
            ),
        )

        print(
            "  books with exact path overlap:",
            stats[
                "exact_overlap_books"
            ],
        )

        print(
            "  books with ancestor/descendant relation:",
            stats[
                "ancestor_relation_books"
            ],
        )

        print(
            "  books containing zero-prefix pair:",
            stats[
                "zero_prefix_books"
            ],
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
                stats[
                    "one_sided_abstentions"
                ],
            "mean_hierarchical_similarity":
                avg,
            "exact_overlap_books":
                stats[
                    "exact_overlap_books"
                ],
            "ancestor_relation_books":
                stats[
                    "ancestor_relation_books"
                ],
            "zero_prefix_books":
                stats[
                    "zero_prefix_books"
                ],
        })

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
