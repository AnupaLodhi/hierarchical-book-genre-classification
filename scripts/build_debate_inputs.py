import json
from pathlib import Path
from collections import Counter

ANNOTATIONS = Path(
    "results/annotations/multi_llm_annotations.json"
)
CONFLICTS = Path(
    "results/consensus/conflicting_annotations.json"
)
OUT_DIR = Path("results/resolution")

MODELS = ["qwen_groq", "gpt_oss_groq", "gpt_oss_20b"]


def main():
    annotations = json.loads(
        ANNOTATIONS.read_text(encoding="utf-8")
    )

    conflicts = json.loads(
        CONFLICTS.read_text(encoding="utf-8")
    )

    annotation_by_isbn = {
        str(x["isbn13"]): x
        for x in annotations
    }

    debate_inputs = []
    incomplete = []

    for conflict in conflicts:
        isbn = str(conflict["isbn13"])
        book = annotation_by_isbn[isbn]

        anns = book.get("annotations", {})

        successful = {
            model: anns[model]
            for model in MODELS
            if anns.get(model, {}).get("status") == "success"
        }

        available_count = len(successful)

        record = {
            "isbn13": isbn,
            "title": book.get("title", ""),
            "filtered_tags": book.get("filtered_tags", []),
            "available_models": list(successful),
            "available_count": available_count,
            "agreement_type": conflict.get(
                "agreement_type", ""
            ),
            "shared_genre_paths": conflict.get(
                "shared_genre_paths", []
            ),
            "shared_metadata_paths": conflict.get(
                "shared_metadata_paths", []
            ),
            "disputed_genre_paths": conflict.get(
                "disputed_genre_paths", []
            ),
            "disputed_metadata_paths": conflict.get(
                "disputed_metadata_paths", []
            ),
            "model_only_paths": conflict.get(
                "model_only_paths", {}
            ),
            "original_annotations": successful,
        }

        # Debate requires at least two independent
        # successful model annotations.
        if available_count >= 2:
            debate_inputs.append(record)
        else:
            statuses = {
                model: anns.get(model, {}).get(
                    "status", "missing"
                )
                for model in MODELS
            }

            record["model_statuses"] = statuses

            incomplete.append(record)

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    (OUT_DIR / "debate_inputs.json").write_text(
        json.dumps(
            debate_inputs,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (OUT_DIR / "incomplete_annotations.json").write_text(
        json.dumps(
            incomplete,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Compatibility/debug queue.
    (OUT_DIR / "debate_queue.json").write_text(
        json.dumps(
            debate_inputs,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    counts = Counter(
        x["available_count"]
        for x in debate_inputs
    )

    incomplete_counts = Counter(
        x["available_count"]
        for x in incomplete
    )

    print("===== DEBATE INPUT BUILD =====")
    print("Consensus conflicts:", len(conflicts))
    print("Debate inputs:", len(debate_inputs))
    print("Incomplete annotations:", len(incomplete))

    print(
        "Debate availability:",
        dict(sorted(counts.items())),
    )

    print(
        "Incomplete availability:",
        dict(sorted(incomplete_counts.items())),
    )

    assert (
        len(debate_inputs) + len(incomplete)
        == len(conflicts)
    )

    assert all(
        x["available_count"] >= 2
        for x in debate_inputs
    )

    assert all(
        x["available_count"] < 2
        for x in incomplete
    )

    print(
        "✅ API-incomplete cases are separated "
        "from genuine model disagreements."
    )


if __name__ == "__main__":
    main()
