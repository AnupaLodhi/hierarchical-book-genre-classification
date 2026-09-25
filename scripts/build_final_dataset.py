import csv
import json
from pathlib import Path
from collections import Counter

CONSENSUS = Path(
    "results/consensus/provisional_consensus_interim.json"
)
ADJ = Path(
    "results/adjudication/adjudication_v1.0.csv"
)
OUT = Path("results/final")
OUT.mkdir(parents=True, exist_ok=True)

FINAL = OUT / "canonical_labels_v1.0.csv"
PROV = OUT / "label_provenance_v1.0.csv"
UNRESOLVED = OUT / "unresolved_cases_v1.0.csv"
SUMMARY = OUT / "dataset_summary_v1.0.txt"


def split_path(path):
    return tuple(
        x.strip()
        for x in path.split(" / ")
        if x.strip()
    )


def is_strict_ancestor(a, d):
    a = split_path(a)
    d = split_path(d)
    return len(a) < len(d) and d[:len(a)] == a


def remove_redundant_ancestors(paths):
    paths = set(paths)

    return sorted(
        p for p in paths
        if not any(
            p != q and is_strict_ancestor(p, q)
            for q in paths
        )
    )


# --------------------------------------------------
# Load frozen inputs
# --------------------------------------------------

records = json.loads(
    CONSENSUS.read_text(encoding="utf-8")
)

with ADJ.open(encoding="utf-8") as f:
    adjudications = list(csv.DictReader(f))


if len(adjudications) != 186:
    raise SystemExit(
        f"ERROR: expected 186 adjudication rows, "
        f"found {len(adjudications)}"
    )


valid_decisions = {"ACCEPT", "REJECT", "UNSURE"}

for r in adjudications:
    if r["decision"] not in valid_decisions:
        raise SystemExit(
            f"ERROR: invalid decision in {r['case_id']}: "
            f"{r['decision']}"
        )


# --------------------------------------------------
# Index adjudications
# --------------------------------------------------

adj_by_book_field = {}

for r in adjudications:
    key = (
        str(r["isbn13"]),
        r["field"].strip().lower(),
    )
    adj_by_book_field.setdefault(key, []).append(r)


# --------------------------------------------------
# Construct final labels
# --------------------------------------------------

final_rows = []
provenance_rows = []
unresolved_rows = []

stats = Counter()

for rec in records:

    isbn = str(rec["isbn13"])
    title = rec.get("title", "")

    row = {
        "isbn13": isbn,
        "title": title,
    }

    for field in ("genre", "metadata"):

        automatic = set(
            rec["consensus"][field]
            .get("canonical_paths", [])
        )

        accepted_adj = set()

        for a in adj_by_book_field.get(
            (isbn, field), []
        ):

            decision = a["decision"]
            candidate = a["candidate_path"]

            if decision == "ACCEPT":
                accepted_adj.add(candidate)

            elif decision == "UNSURE":
                unresolved_rows.append({
                    "case_id": a["case_id"],
                    "isbn13": isbn,
                    "title": title,
                    "field": field,
                    "candidate_path": candidate,
                    "confidence": a["confidence"],
                    "rationale": a["rationale"],
                })

            # REJECT deliberately contributes no label.

        before_pruning = automatic | accepted_adj

        final_paths = remove_redundant_ancestors(
            before_pruning
        )

        row[f"{field}_paths"] = " | ".join(
            final_paths
        )

        row[f"{field}_label_count"] = len(
            final_paths
        )

        stats[f"{field}_automatic_paths"] += len(
            automatic
        )
        stats[f"{field}_accepted_adjudication_paths"] += len(
            accepted_adj
        )
        stats[f"{field}_final_paths"] += len(
            final_paths
        )

        if not final_paths:
            stats[f"{field}_empty_books"] += 1

        # Provenance only for labels surviving final pruning.
        for path in final_paths:

            exact_auto = path in automatic
            exact_adj = path in accepted_adj

            if exact_auto and exact_adj:
                source = (
                    "automatic_consensus+"
                    "accepted_adjudication"
                )
            elif exact_auto:
                source = "automatic_consensus"
            elif exact_adj:
                source = "accepted_adjudication"
            else:
                # Should be impossible because pruning only
                # removes paths; it never creates paths.
                raise SystemExit(
                    "ERROR: final path has no provenance: "
                    f"{isbn} | {field} | {path}"
                )

            provenance_rows.append({
                "isbn13": isbn,
                "title": title,
                "field": field,
                "path": path,
                "source": source,
            })

    final_rows.append(row)


# --------------------------------------------------
# Integrity checks
# --------------------------------------------------

if len(final_rows) != len(records):
    raise SystemExit(
        "ERROR: final row count differs from consensus"
    )

if len({
    r["isbn13"] for r in final_rows
}) != len(final_rows):
    raise SystemExit(
        "ERROR: duplicate ISBNs in final dataset"
    )

if len(unresolved_rows) != 3:
    raise SystemExit(
        f"ERROR: expected 3 unresolved cases, "
        f"found {len(unresolved_rows)}"
    )


# Every ACCEPT adjudication must either:
#   1. survive as a final path, or
#   2. be a redundant ancestor of a surviving path.
final_index = {}

for r in final_rows:
    final_index[
        (r["isbn13"], "genre")
    ] = set(
        x.strip()
        for x in r["genre_paths"].split(" | ")
        if x.strip()
    )

    final_index[
        (r["isbn13"], "metadata")
    ] = set(
        x.strip()
        for x in r["metadata_paths"].split(" | ")
        if x.strip()
    )


for a in adjudications:

    if a["decision"] != "ACCEPT":
        continue

    key = (
        str(a["isbn13"]),
        a["field"].strip().lower(),
    )

    candidate = a["candidate_path"]
    surviving = final_index[key]

    represented = (
        candidate in surviving
        or any(
            is_strict_ancestor(
                candidate,
                path,
            )
            for path in surviving
        )
    )

    if not represented:
        raise SystemExit(
            "ERROR: accepted adjudication disappeared "
            "without hierarchical representation:\n"
            f"{a['case_id']} | {candidate}"
        )


# --------------------------------------------------
# Write final dataset
# --------------------------------------------------

with FINAL.open(
    "w", encoding="utf-8", newline=""
) as f:

    fields = [
        "isbn13",
        "title",
        "genre_paths",
        "genre_label_count",
        "metadata_paths",
        "metadata_label_count",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields,
    )

    w.writeheader()
    w.writerows(final_rows)


with PROV.open(
    "w", encoding="utf-8", newline=""
) as f:

    fields = [
        "isbn13",
        "title",
        "field",
        "path",
        "source",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields,
    )

    w.writeheader()
    w.writerows(provenance_rows)


with UNRESOLVED.open(
    "w", encoding="utf-8", newline=""
) as f:

    fields = [
        "case_id",
        "isbn13",
        "title",
        "field",
        "candidate_path",
        "confidence",
        "rationale",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields,
    )

    w.writeheader()
    w.writerows(unresolved_rows)


# --------------------------------------------------
# Summary
# --------------------------------------------------

decision_counts = Counter(
    r["decision"]
    for r in adjudications
)

books_with_genre = sum(
    bool(r["genre_paths"])
    for r in final_rows
)

books_with_metadata = sum(
    bool(r["metadata_paths"])
    for r in final_rows
)

books_with_both = sum(
    bool(r["genre_paths"])
    and bool(r["metadata_paths"])
    for r in final_rows
)

summary = f"""===== SILVER LABEL DATASET v1.0 =====

Books processed: {len(final_rows)}

ADJUDICATION
Accept: {decision_counts['ACCEPT']}
Reject: {decision_counts['REJECT']}
Unsure: {decision_counts['UNSURE']}

GENRE
Automatic canonical paths: {stats['genre_automatic_paths']}
Accepted adjudication paths: {stats['genre_accepted_adjudication_paths']}
Final canonical paths: {stats['genre_final_paths']}
Books with genre labels: {books_with_genre}
Books without genre labels: {stats['genre_empty_books']}

METADATA
Automatic canonical paths: {stats['metadata_automatic_paths']}
Accepted adjudication paths: {stats['metadata_accepted_adjudication_paths']}
Final canonical paths: {stats['metadata_final_paths']}
Books with metadata labels: {books_with_metadata}
Books without metadata labels: {stats['metadata_empty_books']}

COVERAGE
Books with both genre and metadata: {books_with_both}

UNRESOLVED
Unresolved adjudication paths: {len(unresolved_rows)}

INTEGRITY
Unique ISBNs: {len(set(r['isbn13'] for r in final_rows))}
Duplicate ISBNs: 0
Accepted-path representation check: PASS
Unresolved-count check: PASS
FINAL BUILD: PASS
"""

SUMMARY.write_text(
    summary,
    encoding="utf-8",
)

print(summary)

print("Saved:")
print(" ", FINAL)
print(" ", PROV)
print(" ", UNRESOLVED)
print(" ", SUMMARY)
