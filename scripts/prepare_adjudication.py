"""
Prepare a human-adjudication sheet from isolated singleton
candidates produced by build_consensus.py.

This script does NOT modify annotations or consensus outputs.
It only transforms the frozen review queue into a structured
human-review worksheet.
"""

import csv
from collections import Counter
from pathlib import Path


INPUT = Path(
    "results/consensus/review_queue_interim.csv"
)

OUTPUT_DIR = Path(
    "results/adjudication"
)

OUTPUT_CSV = (
    OUTPUT_DIR / "adjudication_interim.csv"
)

GUIDELINES = (
    OUTPUT_DIR / "adjudication_guidelines.md"
)


def load_review_queue():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"Missing input file: {INPUT}"
        )

    with INPUT.open(
        encoding="utf-8"
    ) as f:
        rows = list(
            csv.DictReader(f)
        )

    if not rows:
        raise ValueError(
            "Review queue is empty."
        )

    return rows


def validate_rows(rows):
    required = {
        "isbn13",
        "title",
        "field",
        "path",
        "proposed_by",
        "reason",
        "filtered_tags",
        "canonical_paths",
    }

    missing = (
        required
        - set(rows[0].keys())
    )

    if missing:
        raise ValueError(
            "Missing columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    invalid = [
        row
        for row in rows
        if row["reason"]
        != "isolated_singleton"
    ]

    if invalid:
        raise ValueError(
            "Review queue contains "
            f"{len(invalid)} non-isolated "
            "cases. Refusing to continue."
        )


def case_sort_key(row):
    field_order = {
        "genre": 0,
        "metadata": 1,
    }

    return (
        field_order.get(
            row["field"],
            99,
        ),
        row["isbn13"],
        row["path"],
        row["proposed_by"],
    )


def build_adjudication_rows(rows):
    rows = sorted(
        rows,
        key=case_sort_key,
    )

    counters = Counter()
    output = []

    for row in rows:
        field = row["field"]

        counters[field] += 1

        prefix = (
            "GENRE"
            if field == "genre"
            else "META"
        )

        case_id = (
            f"{prefix}-"
            f"{counters[field]:04d}"
        )

        output.append({
            "case_id":
                case_id,

            "isbn13":
                row["isbn13"],

            "title":
                row["title"],

            "field":
                field,

            "candidate_path":
                row["path"],

            "proposed_by":
                row["proposed_by"],

            "filtered_tags":
                row["filtered_tags"],

            "canonical_paths":
                row["canonical_paths"],

            "decision":
                "",

            "confidence":
                "",

            "rationale":
                "",

            "adjudicator":
                "",

            "notes":
                "",
        })

    return output


def write_csv(rows):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_CSV.open(
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


def write_guidelines():
    text = """# Human Adjudication Guidelines

## Purpose

This stage reviews only isolated singleton candidates that
could not be resolved by exact or hierarchical consensus.

The goal is not to re-annotate each book from scratch.

The adjudicator decides whether the specific candidate path
is supported by the evidence available to the annotation
pipeline.

## Evidence available

Use:

1. Filtered source tags.
2. Candidate taxonomy path.
3. Existing canonical consensus paths.
4. Candidate provenance (`proposed_by`).

Do not use outside knowledge about the book unless a later
experimental protocol explicitly introduces external
evidence.

## Decision labels

### ACCEPT

Use ACCEPT when the filtered source tags provide sufficiently
direct evidence for the candidate taxonomy path.

The evidence should support the semantic meaning and
specificity of the proposed path.

### REJECT

Use REJECT when:

- the source tags contradict the candidate;
- the candidate is unsupported by the supplied evidence;
- the candidate is substantially more specific than the
  evidence permits; or
- the candidate appears to result from an unjustified
  interpretation of the source tags.

### UNSURE

Use UNSURE when the supplied evidence is insufficient to make
a defensible ACCEPT or REJECT decision.

UNSURE is preferable to guessing.

## Confidence

Use one of:

- HIGH
- MEDIUM
- LOW

Confidence records certainty in the adjudication decision.
It is separate from the decision itself.

## Rationale

Write a short evidence-based explanation.

Good example:

    Source tags explicitly include "Legal thriller" and
    "Courtroom fiction", supporting the proposed legal-fiction
    path.

Bad example:

    I know this book and think this genre fits.

## Hierarchical specificity

A broad tag does not automatically justify a more specific
descendant.

For example:

    "Mystery"

does not by itself establish:

    Mystery / Detective Mystery / Police Detective Mystery

Evidence must support the additional specificity.

A specific source tag may, however, support an appropriate
ancestor when the taxonomy represents that relationship.

## Multi-label books

A candidate should not be rejected merely because another
canonical genre is already accepted.

Books may legitimately have multiple genre or metadata paths.

Evaluate each disputed candidate independently.

## Abstention

Do not create a label merely because no model produced one.

All-model abstention remains an abstention unless a separate
human-annotation experiment is explicitly performed.

## Reproducibility

Do not edit:

- case_id
- isbn13
- title
- field
- candidate_path
- proposed_by
- filtered_tags
- canonical_paths

Human-editable columns are:

- decision
- confidence
- rationale
- adjudicator
- notes
"""

    GUIDELINES.write_text(
        text,
        encoding="utf-8",
    )


def main():
    rows = load_review_queue()

    validate_rows(rows)

    adjudication_rows = (
        build_adjudication_rows(rows)
    )

    write_csv(
        adjudication_rows
    )

    write_guidelines()

    counts = Counter(
        row["field"]
        for row in adjudication_rows
    )

    books = {
        row["isbn13"]
        for row in adjudication_rows
    }

    print(
        "===== ADJUDICATION DATASET ====="
    )

    print(
        "Total cases:",
        len(adjudication_rows),
    )

    print(
        "Genre cases:",
        counts["genre"],
    )

    print(
        "Metadata cases:",
        counts["metadata"],
    )

    print(
        "Unique books:",
        len(books),
    )

    print()

    print("Saved:")
    print(" ", OUTPUT_CSV)
    print(" ", GUIDELINES)


if __name__ == "__main__":
    main()
