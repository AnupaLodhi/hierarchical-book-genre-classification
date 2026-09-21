import json
from collections import Counter
from pathlib import Path

from agents.annotation_agent import load_taxonomies

OUT = Path("results/final")
EVALUATION = Path("results/evaluation")
EVALUATION.mkdir(parents=True, exist_ok=True)

final = json.loads(
    (OUT / "final_output.json").read_text(encoding="utf-8")
)
manual = json.loads(
    (OUT / "manual_review.json").read_text(encoding="utf-8")
)

tax = load_taxonomies()

valid_genres = set(tax["genre_paths"])
valid_metadata = set(tax["metadata_paths"])

issues = []
empty_resolved = 0
fiction_nonfiction_conflicts = 0
bad_genres = 0
bad_metadata = 0

genre_counts = Counter()
metadata_counts = Counter()
method_counts = Counter()

for book in final:
    isbn = book["isbn13"]
    genres = book.get("genre_paths", []) or []
    metadata = book.get("metadata_paths", []) or []

    method_counts[book["resolution_method"]] += 1

    if not genres and not metadata:
        empty_resolved += 1
        issues.append((isbn, "empty_resolved"))

    invalid_g = [x for x in genres if x not in valid_genres]
    invalid_m = [x for x in metadata if x not in valid_metadata]

    if invalid_g:
        bad_genres += 1
        issues.append((isbn, "invalid_genre", invalid_g))

    if invalid_m:
        bad_metadata += 1
        issues.append((isbn, "invalid_metadata", invalid_m))

    roots = {x.split(" / ")[0] for x in genres}

    if "Fiction" in roots and "Nonfiction" in roots:
        fiction_nonfiction_conflicts += 1
        issues.append((isbn, "fiction_nonfiction_conflict"))

    genre_counts.update(genres)
    metadata_counts.update(metadata)


final_isbns = [x["isbn13"] for x in final]
manual_isbns = [x["isbn13"] for x in manual]
all_isbns = final_isbns + manual_isbns

duplicates = len(all_isbns) - len(set(all_isbns))
overlap = set(final_isbns) & set(manual_isbns)

print("\n===== FINAL INTEGRITY AUDIT =====")
print("Resolved records:", len(final))
print("Manual-review records:", len(manual))
print("Total accounted:", len(all_isbns))
print("Unique ISBNs:", len(set(all_isbns)))

print("\n===== STRUCTURAL CHECKS =====")
print("Duplicate ISBN occurrences:", duplicates)
print("Final/manual overlap:", len(overlap))
print("Empty resolved records:", empty_resolved)
print("Invalid genre-path records:", bad_genres)
print("Invalid metadata-path records:", bad_metadata)
print(
    "Fiction + Nonfiction violations:",
    fiction_nonfiction_conflicts
)

print("\n===== RESOLUTION METHODS =====")
for method, count in sorted(method_counts.items()):
    print(f"{method:35} {count}")

print("\n===== TOP GENRE PATHS =====")
for path, count in genre_counts.most_common(10):
    print(f"{count:4}  {path}")

print("\n===== TOP METADATA PATHS =====")
for path, count in metadata_counts.most_common(10):
    print(f"{count:4}  {path}")

if issues:
    print("\n===== ISSUES =====")
    for issue in issues[:20]:
        print(issue)

assert len(all_isbns) == len(set(all_isbns)), (
    "ISBN duplication detected"
)
assert not overlap, "ISBN appears in both final and manual review"
assert empty_resolved == 0, "Empty resolved annotation detected"
assert bad_genres == 0, "Invalid genre taxonomy path detected"
assert bad_metadata == 0, "Invalid metadata taxonomy path detected"
assert fiction_nonfiction_conflicts == 0, (
    "Book classified as both Fiction and Nonfiction"
)

report = {
    "resolved_records": len(final),
    "manual_review_records": len(manual),
    "total_accounted": len(all_isbns),
    "unique_isbns": len(set(all_isbns)),
    "duplicate_isbn_occurrences": duplicates,
    "final_manual_overlap": len(overlap),
    "empty_resolved_records": empty_resolved,
    "invalid_genre_records": bad_genres,
    "invalid_metadata_records": bad_metadata,
    "fiction_nonfiction_violations":
        fiction_nonfiction_conflicts,
    "resolution_methods": dict(method_counts),
    "top_genre_paths": genre_counts.most_common(20),
    "top_metadata_paths": metadata_counts.most_common(20),
}

(EVALUATION / "final_integrity_audit.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("\nSaved: results/evaluation/final_integrity_audit.json")
print("✅ FINAL INTEGRITY AUDIT PASSED")
