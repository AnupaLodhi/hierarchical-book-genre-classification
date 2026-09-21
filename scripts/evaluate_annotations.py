import json
from collections import Counter
from itertools import combinations
from pathlib import Path

INPUT = Path("results/annotations/multi_llm_annotations.json")
OUTPUT = Path("results/evaluation/evaluation_summary.json")
MODELS = ["qwen_groq", "gpt_oss_groq", "gemini_google"]

data = json.loads(INPUT.read_text(encoding="utf-8"))

def paths(ann, field):
    return set(ann.get(field, []) or [])

def jaccard(a, b):
    # Empty-empty contains no positive annotation evidence.
    # Exclude it from mean Jaccard instead of treating it as perfect agreement.
    if not a and not b:
        return None
    return len(a & b) / len(a | b)

availability = Counter()
success_counts = Counter()

pairs = {
    (a, b): {
        "n": 0,
        "genre_exact": 0,
        "metadata_exact": 0,
        "both_exact": 0,
        "genre_jaccard": 0.0,
        "metadata_jaccard": 0.0,
        "genre_jaccard_n": 0,
        "metadata_jaccard_n": 0,
    }
    for a, b in combinations(MODELS, 2)
}

three_n = 0
three_genre = 0
three_metadata = 0
three_both = 0

for book in data:
    anns = book.get("annotations", {})

    good = {
        m: anns[m]
        for m in MODELS
        if anns.get(m, {}).get("status") == "success"
    }

    availability[len(good)] += 1

    for m in good:
        success_counts[m] += 1

    for a, b in combinations(MODELS, 2):
        if a not in good or b not in good:
            continue

        ga = paths(good[a], "genre_paths")
        gb = paths(good[b], "genre_paths")
        ma = paths(good[a], "metadata_paths")
        mb = paths(good[b], "metadata_paths")

        s = pairs[(a, b)]
        s["n"] += 1
        s["genre_exact"] += ga == gb
        s["metadata_exact"] += ma == mb
        s["both_exact"] += ga == gb and ma == mb
        genre_j = jaccard(ga, gb)
        metadata_j = jaccard(ma, mb)

        if genre_j is not None:
            s["genre_jaccard"] += genre_j
            s["genre_jaccard_n"] += 1

        if metadata_j is not None:
            s["metadata_jaccard"] += metadata_j
            s["metadata_jaccard_n"] += 1

    if len(good) == 3:
        three_n += 1

        gs = [paths(good[m], "genre_paths") for m in MODELS]
        ms = [paths(good[m], "metadata_paths") for m in MODELS]

        ge = gs[0] == gs[1] == gs[2]
        me = ms[0] == ms[1] == ms[2]

        three_genre += ge
        three_metadata += me
        three_both += ge and me

print("\n===== ORIGINAL MODEL EVALUATION =====")
print("Total books:", len(data))
print("Availability:", dict(sorted(availability.items())))
print("Success counts:", dict(success_counts))

print("\n===== THREE-MODEL AGREEMENT =====")
print("Books with all 3 models:", three_n)

if three_n:
    print(
        "Exact genre agreement:",
        three_genre,
        f"({three_genre / three_n * 100:.2f}%)"
    )
    print(
        "Exact metadata agreement:",
        three_metadata,
        f"({three_metadata / three_n * 100:.2f}%)"
    )
    print(
        "Exact genre + metadata:",
        three_both,
        f"({three_both / three_n * 100:.2f}%)"
    )

print("\n===== PAIRWISE AGREEMENT =====")

summary = {
    "total_books": len(data),
    "availability": dict(availability),
    "success_counts": dict(success_counts),
    "three_model_books": three_n,
    "three_model_exact_genre": three_genre,
    "three_model_exact_metadata": three_metadata,
    "three_model_exact_both": three_both,
    "pairwise": {},
}

for (a, b), s in pairs.items():
    n = s["n"]

    if not n:
        continue

    result = {
        "books": n,
        "exact_genre_rate": s["genre_exact"] / n,
        "exact_metadata_rate": s["metadata_exact"] / n,
        "exact_both_rate": s["both_exact"] / n,
        "mean_genre_jaccard": (
            s["genre_jaccard"] / s["genre_jaccard_n"]
            if s["genre_jaccard_n"] else None
        ),
        "mean_metadata_jaccard": (
            s["metadata_jaccard"] / s["metadata_jaccard_n"]
            if s["metadata_jaccard_n"] else None
        ),
        "genre_jaccard_books": s["genre_jaccard_n"],
        "metadata_jaccard_books": s["metadata_jaccard_n"],
    }

    summary["pairwise"][f"{a}_vs_{b}"] = result

    print(f"\n{a} vs {b} (n={n})")
    print(f"  Exact genre:    {result['exact_genre_rate']*100:.2f}%")
    print(f"  Exact metadata: {result['exact_metadata_rate']*100:.2f}%")
    print(f"  Exact both:     {result['exact_both_rate']*100:.2f}%")
    gj = result["mean_genre_jaccard"]
    mj = result["mean_metadata_jaccard"]

    print(
        "  Genre Jaccard: ",
        f"{gj:.3f}" if gj is not None else "N/A",
        f"(n={result['genre_jaccard_books']})",
    )
    print(
        "  Metadata Jaccard:",
        f"{mj:.3f}" if mj is not None else "N/A",
        f"(n={result['metadata_jaccard_books']})",
    )

OUTPUT.write_text(
    json.dumps(summary, indent=2),
    encoding="utf-8"
)

print("\nSaved:", OUTPUT)
print("✅ EVALUATION PASSED")
