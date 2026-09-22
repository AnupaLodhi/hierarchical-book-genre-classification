import json
from collections import Counter
from itertools import combinations
from pathlib import Path

INPUT = Path("results/annotations/multi_llm_annotations.json")
OUTPUT = Path("results/evaluation/path_agreement_analysis.json")

MODELS = ["qwen_groq", "gpt_oss_groq", "gemini_google"]


def get_paths(annotation, field):
    return set(annotation.get(field, []) or [])


def is_ancestor(path_a, path_b):
    """True only when path_a is a strict taxonomy ancestor of path_b."""
    a = [x.strip() for x in path_a.split(" / ")]
    b = [x.strip() for x in path_b.split(" / ")]

    return len(a) < len(b) and b[:len(a)] == a


def hierarchical_relationships(paths_a, paths_b):
    relationships = []

    for a in sorted(paths_a):
        for b in sorted(paths_b):
            if is_ancestor(a, b):
                relationships.append({
                    "ancestor": a,
                    "descendant": b,
                })
            elif is_ancestor(b, a):
                relationships.append({
                    "ancestor": b,
                    "descendant": a,
                })

    return relationships


def support_counts(successful, field):
    counts = Counter()

    for annotation in successful.values():
        for path in get_paths(annotation, field):
            counts[path] += 1

    return counts


data = json.loads(INPUT.read_text(encoding="utf-8"))

books = []

global_genre_support = Counter()
global_metadata_support = Counter()

hierarchical_genre_pairs = 0
hierarchical_metadata_pairs = 0

pairwise_hierarchy = {
    f"{a}_vs_{b}": {
        "books_compared": 0,
        "genre_books_with_hierarchical_overlap": 0,
        "metadata_books_with_hierarchical_overlap": 0,
    }
    for a, b in combinations(MODELS, 2)
}

for book in data:
    anns = book.get("annotations", {})

    successful = {
        model: anns[model]
        for model in MODELS
        if anns.get(model, {}).get("status") == "success"
    }

    n = len(successful)

    genre_support = support_counts(successful, "genre_paths")
    metadata_support = support_counts(successful, "metadata_paths")

    global_genre_support.update(genre_support)
    global_metadata_support.update(metadata_support)

    pair_details = []

    for a, b in combinations(MODELS, 2):
        if a not in successful or b not in successful:
            continue

        ga = get_paths(successful[a], "genre_paths")
        gb = get_paths(successful[b], "genre_paths")

        ma = get_paths(successful[a], "metadata_paths")
        mb = get_paths(successful[b], "metadata_paths")

        genre_rel = hierarchical_relationships(ga, gb)
        metadata_rel = hierarchical_relationships(ma, mb)

        key = f"{a}_vs_{b}"
        pairwise_hierarchy[key]["books_compared"] += 1

        if genre_rel:
            pairwise_hierarchy[key][
                "genre_books_with_hierarchical_overlap"
            ] += 1
            hierarchical_genre_pairs += len(genre_rel)

        if metadata_rel:
            pairwise_hierarchy[key][
                "metadata_books_with_hierarchical_overlap"
            ] += 1
            hierarchical_metadata_pairs += len(metadata_rel)

        pair_details.append({
            "models": [a, b],
            "genre_ancestor_descendant": genre_rel,
            "metadata_ancestor_descendant": metadata_rel,
        })

    books.append({
        "isbn13": book["isbn13"],
        "title": book.get("title", ""),
        "available_models": list(successful),
        "available_count": n,
        "genre_path_support": dict(
            sorted(
                genre_support.items(),
                key=lambda x: (-x[1], x[0]),
            )
        ),
        "metadata_path_support": dict(
            sorted(
                metadata_support.items(),
                key=lambda x: (-x[1], x[0]),
            )
        ),
        "genre_support_groups": {
            str(k): sorted(
                path
                for path, count in genre_support.items()
                if count == k
            )
            for k in range(n, 0, -1)
        },
        "metadata_support_groups": {
            str(k): sorted(
                path
                for path, count in metadata_support.items()
                if count == k
            )
            for k in range(n, 0, -1)
        },
        "pairwise_hierarchical_relationships": pair_details,
    })


summary = {
    "total_books": len(data),
    "methodology": {
        "exact_path_support": (
            "Counts how many successful independent annotators selected "
            "each exact taxonomy path."
        ),
        "hierarchical_relationship": (
            "Ancestor/descendant relationships are reported separately "
            "and are NOT counted as exact agreement."
        ),
        "provider_failures": (
            "Failed or unavailable annotators are excluded from "
            "agreement calculations."
        ),
    },
    "hierarchical_genre_relationships_found": hierarchical_genre_pairs,
    "hierarchical_metadata_relationships_found": hierarchical_metadata_pairs,
    "pairwise_hierarchy": pairwise_hierarchy,
    "books": books,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

OUTPUT.write_text(
    json.dumps(summary, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("===== PATH-LEVEL AGREEMENT ANALYSIS =====")
print("Books:", len(data))
print(
    "Genre ancestor/descendant relationships:",
    hierarchical_genre_pairs,
)
print(
    "Metadata ancestor/descendant relationships:",
    hierarchical_metadata_pairs,
)

print("\nPairwise hierarchy:")

for pair, values in pairwise_hierarchy.items():
    if values["books_compared"]:
        print(pair, values)

print("\nSaved:", OUTPUT)
print("✅ PATH AGREEMENT ANALYSIS PASSED")
