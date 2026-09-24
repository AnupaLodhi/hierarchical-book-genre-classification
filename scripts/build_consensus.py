import csv
import json
from collections import Counter
from pathlib import Path


INPUT = Path(
    "results/agreement/three_model_complete_interim.json"
)

OUTPUT_DIR = Path("results/consensus")

CONSENSUS_JSON = (
    OUTPUT_DIR / "provisional_consensus_interim.json"
)

REVIEW_CSV = (
    OUTPUT_DIR / "review_queue_interim.csv"
)

RESOLVED_CSV = (
    OUTPUT_DIR / "resolved_hierarchy_interim.csv"
)

SUMMARY_CSV = (
    OUTPUT_DIR / "consensus_summary_interim.csv"
)


MODELS = [
    "qwen_groq",
    "gpt_oss_groq",
    "gpt_oss_20b",
]


FIELDS = {
    "genre_paths": "genre",
    "metadata_paths": "metadata",
}


def split_path(path):
    return tuple(
        part.strip()
        for part in path.split(" / ")
        if part.strip()
    )


def is_strict_ancestor(ancestor, descendant):
    a = split_path(ancestor)
    d = split_path(descendant)

    return (
        len(a) < len(d)
        and d[:len(a)] == a
    )


def remove_redundant_ancestors(paths):
    """
    If both an ancestor and one of its descendants
    are accepted, retain the more specific path.

    Example:
        Fiction
        Fiction / Historical Fiction

    becomes:
        Fiction / Historical Fiction
    """

    paths = set(paths)

    keep = set()

    for path in paths:

        has_accepted_descendant = any(
            is_strict_ancestor(
                path,
                other,
            )
            for other in paths
            if other != path
        )

        if not has_accepted_descendant:
            keep.add(path)

    return sorted(keep)


def exact_votes(model_sets):
    votes = Counter()

    for paths in model_sets.values():
        for path in paths:
            votes[path] += 1

    return votes


def ancestor_support(path, model_sets):
    """
    A model supports `path` when it selected:
      - the exact path, OR
      - a descendant of that path.

    Support only propagates upward.
    """

    supporters = []

    for model, paths in model_sets.items():

        supported = any(
            candidate == path
            or is_strict_ancestor(
                path,
                candidate,
            )
            for candidate in paths
        )

        if supported:
            supporters.append(model)

    return supporters


def hierarchical_candidates(
    model_sets,
    exact_accepted,
):
    """
    Hierarchical consensus is allowed only for an
    OBSERVED model prediction.

    An observed path receives hierarchical support
    from another model only when that model selected
    a descendant of the path.

    We never manufacture an unobserved common
    ancestor as a consensus label.
    """

    observed_paths = set().union(
        *model_sets.values()
    )

    supported = {}

    for path in observed_paths:

        # Exact >=2-model agreement is already
        # handled by the stronger exact-consensus
        # rule.
        if path in exact_accepted:
            continue

        exact_supporters = {
            model
            for model, paths
            in model_sets.items()
            if path in paths
        }

        descendant_supporters = {
            model
            for model, paths
            in model_sets.items()
            if any(
                is_strict_ancestor(
                    path,
                    candidate,
                )
                for candidate in paths
            )
        }

        supporters = (
            exact_supporters
            | descendant_supporters
        )

        # Require >=2 distinct models and require
        # the path itself to have actually been
        # predicted by at least one model.
        if (
            exact_supporters
            and len(supporters) >= 2
        ):
            supported[path] = sorted(
                supporters
            )

    return supported


def most_specific_paths(paths):
    """
    Remove a path when another path in the same
    set is its strict descendant.
    """

    paths = set(paths)

    return {
        path
        for path in paths
        if not any(
            is_strict_ancestor(
                path,
                other,
            )
            for other in paths
            if other != path
        )
    }


def analyze_field(record, field):
    model_sets = {
        model: set(
            record["annotations"][model]
            .get(field, [])
        )
        for model in MODELS
    }

    votes = exact_votes(model_sets)

    unanimous = sorted(
        path
        for path, count in votes.items()
        if count == 3
    )

    majority = sorted(
        path
        for path, count in votes.items()
        if count == 2
    )

    exact_accepted = set(
        unanimous + majority
    )

    hierarchical = hierarchical_candidates(
        model_sets,
        exact_accepted,
    )

    hierarchical_specific = (
        most_specific_paths(
            hierarchical.keys()
        )
    )

    hierarchical_specific = {
        path: hierarchical[path]
        for path in hierarchical_specific
        if not any(
            is_strict_ancestor(
                path,
                accepted,
            )
            for accepted in exact_accepted
        )
    }

    # Exact evidence takes precedence.
    provisional = set(exact_accepted)

    # Add hierarchy-supported paths only when
    # they are not redundant ancestors of an
    # already accepted exact path.
    for path in hierarchical_specific:

        redundant = any(
            path == accepted
            or is_strict_ancestor(
                path,
                accepted,
            )
            for accepted in provisional
        )

        if not redundant:
            provisional.add(path)

    canonical = remove_redundant_ancestors(
        provisional
    )

    # Anything observed by only one model and
    # not represented by the canonical consensus
    # becomes a review candidate.
    review = []

    for path, count in sorted(
        votes.items()
    ):
        if count != 1:
            continue

        represented = any(
            path == accepted
            or is_strict_ancestor(
                path,
                accepted,
            )
            or is_strict_ancestor(
                accepted,
                path,
            )
            for accepted in canonical
        )

        if represented:
            reason = (
                "singleton_hierarchically_"
                "related_to_consensus"
            )
        else:
            reason = "isolated_singleton"

        voter = next(
            model
            for model, paths
            in model_sets.items()
            if path in paths
        )

        review.append({
            "path": path,
            "model": voter,
            "reason": reason,
        })

    all_abstain = all(
        not paths
        for paths in model_sets.values()
    )

    return {
        "model_sets": model_sets,
        "unanimous": unanimous,
        "majority": majority,
        "hierarchical": {
            path: supporters
            for path, supporters
            in sorted(
                hierarchical_specific.items()
            )
        },
        "canonical": canonical,
        "review": review,
        "all_abstain": all_abstain,
    }


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    output_records = []
    review_rows = []
    resolved_rows = []

    stats = Counter()

    for record in records:

        result_record = {
            "isbn13": record["isbn13"],
            "title": record.get(
                "title",
                "",
            ),
            "filtered_tags": record.get(
                "filtered_tags",
                [],
            ),
            "consensus": {},
        }

        for field, short in FIELDS.items():

            result = analyze_field(
                record,
                field,
            )

            result_record[
                "consensus"
            ][short] = {
                "unanimous_paths":
                    result["unanimous"],
                "majority_paths":
                    result["majority"],
                "hierarchical_paths":
                    result["hierarchical"],
                "canonical_paths":
                    result["canonical"],
                "all_models_abstain":
                    result["all_abstain"],
            }

            stats[
                f"{short}_unanimous_paths"
            ] += len(
                result["unanimous"]
            )

            stats[
                f"{short}_majority_paths"
            ] += len(
                result["majority"]
            )

            stats[
                f"{short}_hierarchical_paths"
            ] += len(
                result["hierarchical"]
            )

            stats[
                f"{short}_canonical_paths"
            ] += len(
                result["canonical"]
            )

            if result["all_abstain"]:
                stats[
                    f"{short}_all_abstain_books"
                ] += 1

            if result["review"]:
                stats[
                    f"{short}_books_with_review"
                ] += 1

            isolated_items = [
                item
                for item in result["review"]
                if item["reason"]
                == "isolated_singleton"
            ]

            resolved_items = [
                item
                for item in result["review"]
                if item["reason"]
                == (
                    "singleton_hierarchically_"
                    "related_to_consensus"
                )
            ]

            if isolated_items:
                stats[
                    f"{short}_adjudication_books"
                ] += 1

            for item in isolated_items:

                stats[
                    f"{short}_adjudication_paths"
                ] += 1

                review_rows.append({
                    "isbn13":
                        record["isbn13"],
                    "title":
                        record.get(
                            "title",
                            "",
                        ),
                    "field":
                        short,
                    "path":
                        item["path"],
                    "proposed_by":
                        item["model"],
                    "reason":
                        "isolated_singleton",
                    "filtered_tags":
                        " | ".join(
                            record.get(
                                "filtered_tags",
                                [],
                            )
                        ),
                    "canonical_paths":
                        " | ".join(
                            result["canonical"]
                        ),
                })

            for item in resolved_items:

                stats[
                    f"{short}_resolved_"
                    "hierarchy_paths"
                ] += 1

                resolved_rows.append({
                    "isbn13":
                        record["isbn13"],
                    "title":
                        record.get(
                            "title",
                            "",
                        ),
                    "field":
                        short,
                    "path":
                        item["path"],
                    "proposed_by":
                        item["model"],
                    "resolution":
                        "hierarchically_represented",
                    "canonical_paths":
                        " | ".join(
                            result["canonical"]
                        ),
                })

        output_records.append(
            result_record
        )

    CONSENSUS_JSON.write_text(
        json.dumps(
            output_records,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    if review_rows:

        with REVIEW_CSV.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=list(
                    review_rows[0].keys()
                ),
            )

            writer.writeheader()
            writer.writerows(
                review_rows
            )

    if resolved_rows:

        with RESOLVED_CSV.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=list(
                    resolved_rows[0].keys()
                ),
            )

            writer.writeheader()
            writer.writerows(
                resolved_rows
            )

    summary_rows = [
        {
            "metric": key,
            "value": value,
        }
        for key, value
        in sorted(stats.items())
    ]

    with SUMMARY_CSV.open(
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
        writer.writerows(
            summary_rows
        )

    print(
        "===== PROVISIONAL CONSENSUS ====="
    )

    print(
        "Books processed:",
        len(records),
    )

    print()

    for short in [
        "genre",
        "metadata",
    ]:

        print(short.upper())

        print(
            "  unanimous paths:",
            stats[
                f"{short}_unanimous_paths"
            ],
        )

        print(
            "  majority paths:",
            stats[
                f"{short}_majority_paths"
            ],
        )

        print(
            "  hierarchical paths:",
            stats[
                f"{short}_hierarchical_paths"
            ],
        )

        print(
            "  canonical paths:",
            stats[
                f"{short}_canonical_paths"
            ],
        )

        print(
            "  adjudication books:",
            stats[
                f"{short}_adjudication_books"
            ],
        )

        print(
            "  adjudication paths:",
            stats[
                f"{short}_adjudication_paths"
            ],
        )

        print(
            "  hierarchy-resolved paths:",
            stats[
                f"{short}_resolved_"
                "hierarchy_paths"
            ],
        )

        print(
            "  all-model abstention books:",
            stats[
                f"{short}_all_abstain_books"
            ],
        )

        print()

    print("Saved:")
    print(" ", CONSENSUS_JSON)
    print(" ", REVIEW_CSV)
    print(" ", RESOLVED_CSV)
    print(" ", SUMMARY_CSV)


if __name__ == "__main__":
    main()
