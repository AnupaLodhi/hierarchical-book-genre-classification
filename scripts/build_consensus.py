import csv
import json
from pathlib import Path
from collections import Counter

INPUT = Path("results/annotations/multi_llm_annotations.json")
OUT_DIR = Path("results/consensus")
MODELS = ["qwen_groq", "gpt_oss_groq", "gemini_google"]


def norm(paths):
    return tuple(sorted(set(paths or [])))


def signature(annotation):
    return (
        norm(annotation.get("genre_paths")),
        norm(annotation.get("metadata_paths")),
    )


def path_analysis(successful):
    if not successful:
        return {
            "shared_genre_paths": [],
            "shared_metadata_paths": [],
            "disputed_genre_paths": [],
            "disputed_metadata_paths": [],
            "model_only_paths": {},
        }

    genre_sets = {
        model: set(annotation.get("genre_paths") or [])
        for model, annotation in successful.items()
    }

    metadata_sets = {
        model: set(annotation.get("metadata_paths") or [])
        for model, annotation in successful.items()
    }

    shared_genres = set.intersection(*genre_sets.values())
    shared_metadata = set.intersection(*metadata_sets.values())

    union_genres = set.union(*genre_sets.values())
    union_metadata = set.union(*metadata_sets.values())

    disputed_genres = union_genres - shared_genres
    disputed_metadata = union_metadata - shared_metadata

    model_only = {}

    for model in successful:
        other_genres = set().union(*[
            paths
            for name, paths in genre_sets.items()
            if name != model
        ])

        other_metadata = set().union(*[
            paths
            for name, paths in metadata_sets.items()
            if name != model
        ])

        model_only[model] = {
            "genre_paths": sorted(
                genre_sets[model] - other_genres
            ),
            "metadata_paths": sorted(
                metadata_sets[model] - other_metadata
            ),
        }

    return {
        "shared_genre_paths": sorted(shared_genres),
        "shared_metadata_paths": sorted(shared_metadata),
        "disputed_genre_paths": sorted(disputed_genres),
        "disputed_metadata_paths": sorted(disputed_metadata),
        "model_only_paths": model_only,
    }


def save_csv(path, rows):
    fields = [
        "isbn13",
        "title",
        "available_models",
        "available_count",
        "agreement_type",
        "genre_paths",
        "metadata_paths",
        "shared_genre_paths",
        "shared_metadata_paths",
        "disputed_genre_paths",
        "disputed_metadata_paths",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for r in rows:
            writer.writerow({
                "isbn13": r["isbn13"],
                "title": r["title"],
                "available_models": " | ".join(r["available_models"]),
                "available_count": r["available_count"],
                "agreement_type": r["agreement_type"],
                "genre_paths": " | ".join(r.get("genre_paths", [])),
                "metadata_paths": " | ".join(r.get("metadata_paths", [])),
                "shared_genre_paths": " | ".join(
                    r.get("shared_genre_paths", [])
                ),
                "shared_metadata_paths": " | ".join(
                    r.get("shared_metadata_paths", [])
                ),
                "disputed_genre_paths": " | ".join(
                    r.get("disputed_genre_paths", [])
                ),
                "disputed_metadata_paths": " | ".join(
                    r.get("disputed_metadata_paths", [])
                ),
            })


data = json.loads(INPUT.read_text(encoding="utf-8"))

perfect = []
partial = []
conflicts = []
no_evidence = []

availability = Counter()

for book in data:
    annotations = book.get("annotations", {})

    successful = {
        m: annotations[m]
        for m in MODELS
        if annotations.get(m, {}).get("status") == "success"
    }

    n = len(successful)
    availability[n] += 1

    analysis = path_analysis(successful)

    base = {
        "isbn13": book["isbn13"],
        "title": book.get("title", ""),
        "available_models": list(successful),
        "available_count": n,
        **analysis,
    }

    # These books had no filtered evidence, so no paid annotation was needed.
    if n == 0 and all(
        annotations.get(m, {}).get("status") == "no_filtered_tags"
        for m in MODELS
    ):
        no_evidence.append({
            **base,
            "agreement_type": "no_filtered_tags",
            "genre_paths": [],
            "metadata_paths": [],
        })
        continue

    if n == 0:
        conflicts.append({
            **base,
            "agreement_type": "no_successful_original_model",
            "genre_paths": [],
            "metadata_paths": [],
        })
        continue

    sigs = {m: signature(a) for m, a in successful.items()}
    counts = Counter(sigs.values())
    best_sig, best_votes = counts.most_common(1)[0]

    genres, metadata = best_sig

    if n == 3 and best_votes == 3:
        perfect.append({
            **base,
            "agreement_type": "perfect_3_of_3",
            "genre_paths": list(genres),
            "metadata_paths": list(metadata),
        })

    elif n >= 2 and best_votes >= 2:
        partial.append({
            **base,
            "agreement_type": f"agreement_{best_votes}_of_{n}",
            "genre_paths": list(genres),
            "metadata_paths": list(metadata),
        })

    else:
        conflicts.append({
            **base,
            "agreement_type": f"conflict_{n}_original_models",
            "genre_paths": [],
            "metadata_paths": [],
        })


OUT_DIR.mkdir(exist_ok=True)

(OUT_DIR / "perfect_consensus.json").write_text(
    json.dumps(perfect, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

(OUT_DIR / "partial_agreement.json").write_text(
    json.dumps(partial, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

(OUT_DIR / "conflicting_annotations.json").write_text(
    json.dumps(conflicts, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

(OUT_DIR / "no_evidence.json").write_text(
    json.dumps(no_evidence, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

save_csv(OUT_DIR / "perfect_consensus.csv", perfect)
save_csv(OUT_DIR / "partial_agreement.csv", partial)
save_csv(OUT_DIR / "conflicting_annotations.csv", conflicts)
save_csv(OUT_DIR / "no_evidence.csv", no_evidence)

print("\n===== CONSENSUS SUMMARY =====")
print("Books:", len(data))
print("Original model availability:", dict(sorted(availability.items())))
print("Perfect 3/3 consensus:", len(perfect))
print("Partial agreement:", len(partial))
print("Conflicts / unresolved:", len(conflicts))
print("No filtered evidence:", len(no_evidence))

assert (
    len(perfect)
    + len(partial)
    + len(conflicts)
    + len(no_evidence)
    == len(data)
)

print(f"\n✅ All {len(data)} input books accounted for")
print("results/consensus/perfect_consensus.csv")
print("results/consensus/partial_agreement.csv")
print("results/consensus/conflicting_annotations.csv")
print("results/consensus/no_evidence.csv")
