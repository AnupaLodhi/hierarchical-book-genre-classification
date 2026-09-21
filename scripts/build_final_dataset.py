import csv
import json
from pathlib import Path
from collections import Counter

CONSENSUS = Path("results/consensus")
RESOLUTION = Path("results/resolution")
FINAL = Path("results/final")
FINAL.mkdir(parents=True, exist_ok=True)

perfect = json.load(open(CONSENSUS / "perfect_consensus.json"))
partial = json.load(open(CONSENSUS / "partial_agreement.json"))
debate_inputs = json.load(open(RESOLUTION / "debate_inputs.json"))
debate_results = json.load(open(RESOLUTION / "debate_resolutions.json"))
incomplete = json.load(open(RESOLUTION / "incomplete_annotations.json"))
no_evidence = json.load(open(CONSENSUS / "no_evidence.json"))

debate_input_by_isbn = {x["isbn13"]: x for x in debate_inputs}
debate_result_by_isbn = {x["isbn13"]: x for x in debate_results}

final = []
manual = []


def resolved_record(x, method):
    return {
        "isbn13": x["isbn13"],
        "title": x.get("title", ""),
        "resolution_method": method,
        "genre_paths": x.get("genre_paths", []),
        "metadata_paths": x.get("metadata_paths", []),
    }


# 1. Perfect 3/3 consensus
for x in perfect:
    final.append(
        resolved_record(x, "perfect_3_of_3_consensus")
    )


# 2. Partial multi-model agreement
for x in partial:
    final.append(
        resolved_record(
            x,
            x.get("agreement_type", "partial_agreement")
        )
    )


# 3. Debate cases
for isbn, inp in debate_input_by_isbn.items():
    result = debate_result_by_isbn.get(isbn)

    if result is None:
        manual.append({
            "isbn13": isbn,
            "title": inp.get("title", ""),
            "review_reason": "debate_not_run",
            "available_original_models": inp.get("available_count", 0),
            "filtered_tags": inp.get("filtered_tags", []),
            "original_annotations": inp.get("original_annotations", {}),
            "resolver_error": "",
        })
        continue

    if result.get("status") != "success":
        manual.append({
            "isbn13": isbn,
            "title": inp.get("title", ""),
            "review_reason": "debate_api_error",
            "available_original_models": inp.get("available_count", 0),
            "filtered_tags": inp.get("filtered_tags", []),
            "original_annotations": inp.get("original_annotations", {}),
            "resolver_error": result.get("error", ""),
        })
        continue

    genres = result.get("genre_paths", [])
    metadata = result.get("metadata_paths", [])

    if not genres and not metadata:
        manual.append({
            "isbn13": isbn,
            "title": inp.get("title", ""),
            "review_reason": "resolver_returned_empty",
            "available_original_models": inp.get("available_count", 0),
            "filtered_tags": inp.get("filtered_tags", []),
            "original_annotations": inp.get("original_annotations", {}),
            "resolver_error": "",
        })
        continue

    final.append({
        "isbn13": isbn,
        "title": inp.get("title", ""),
        "resolution_method": "debate_resolver",
        "resolver_provider": result.get("provider", ""),
        "resolver_model": result.get("model", ""),
        "genre_paths": genres,
        "metadata_paths": metadata,
    })


# 4. Incomplete original annotations
for x in incomplete:
    manual.append({
        "isbn13": x["isbn13"],
        "title": x.get("title", ""),
        "review_reason": "insufficient_original_annotations",
        "available_original_models": x.get("available_count", 0),
        "filtered_tags": [],
        "original_annotations": {},
        "resolver_error": "",
    })


# 5. No filtered evidence
for x in no_evidence:
    manual.append({
        "isbn13": x["isbn13"],
        "title": x.get("title", ""),
        "review_reason": "no_filtered_tags",
        "available_original_models": 0,
        "filtered_tags": [],
        "original_annotations": {},
        "resolver_error": "",
    })


# Safety checks
all_isbns = [x["isbn13"] for x in final] + [
    x["isbn13"] for x in manual
]

expected_isbns = set()

for group in (
    perfect,
    partial,
    debate_inputs,
    incomplete,
    no_evidence,
):
    expected_isbns.update(
        str(x["isbn13"])
        for x in group
    )

assert set(map(str, all_isbns)) == expected_isbns, (
    "Final/manual outputs do not exactly match "
    "the experiment input ISBNs"
)

assert len(all_isbns) == len(set(map(str, all_isbns))), (
    "Duplicate ISBN detected between final/manual outputs"
)


# Save JSON
(FINAL / "final_output.json").write_text(
    json.dumps(final, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

(FINAL / "manual_review.json").write_text(
    json.dumps(manual, indent=2, ensure_ascii=False),
    encoding="utf-8",
)


# Save final CSV
with open(
    FINAL / "final_output.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:
    fields = [
        "isbn13",
        "title",
        "resolution_method",
        "resolver_provider",
        "resolver_model",
        "genre_paths",
        "metadata_paths",
    ]

    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for x in final:
        writer.writerow({
            "isbn13": x["isbn13"],
            "title": x["title"],
            "resolution_method": x["resolution_method"],
            "resolver_provider": x.get("resolver_provider", ""),
            "resolver_model": x.get("resolver_model", ""),
            "genre_paths": " | ".join(x["genre_paths"]),
            "metadata_paths": " | ".join(x["metadata_paths"]),
        })


# Save manual-review CSV
with open(
    FINAL / "manual_review.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:
    fields = [
        "isbn13",
        "title",
        "review_reason",
        "available_original_models",
        "filtered_tags",
        "original_annotations",
        "resolver_error",
    ]

    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for x in manual:
        writer.writerow({
            "isbn13": x["isbn13"],
            "title": x["title"],
            "review_reason": x["review_reason"],
            "available_original_models":
                x["available_original_models"],
            "filtered_tags":
                " | ".join(x["filtered_tags"]),
            "original_annotations":
                json.dumps(
                    x["original_annotations"],
                    ensure_ascii=False,
                ),
            "resolver_error":
                x["resolver_error"],
        })


methods = Counter(
    x["resolution_method"]
    for x in final
)

reasons = Counter(
    x["review_reason"]
    for x in manual
)

print("\n===== FINAL DATASET SUMMARY =====")
print("Resolved:", len(final))
print("Manual review:", len(manual))
print("Total:", len(final) + len(manual))

print("\nRESOLUTION METHODS")
for k, v in sorted(methods.items()):
    print(f"{k:35} {v}")

print("\nMANUAL REVIEW REASONS")
for k, v in sorted(reasons.items()):
    print(f"{k:35} {v}")

print("\nUnique ISBNs:", len(set(all_isbns)))

print("\nFILES")
print("results/final/final_output.csv")
print("results/final/final_output.json")
print("results/final/manual_review.csv")
print("results/final/manual_review.json")

print("\n✅ FINAL DATASET BUILD PASSED")
