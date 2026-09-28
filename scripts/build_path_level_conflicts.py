import csv
import json
from pathlib import Path

INPUT = Path(
    "results/annotations/complete_397_snapshot/"
    "multi_llm_annotations_397.json"
)

OUT_DIR = Path("results/path_debate_v2")

MODELS = [
    "qwen_groq",
    "gpt_oss_groq",
    "gpt_oss_20b",
]


def main():
    records = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    conflicts = []
    unanimous = []

    for book in records:
        isbn = str(book["isbn13"])
        title = book.get("title", "")
        tags = book.get("filtered_tags", [])
        annotations = book.get("annotations", {})

        successful = [
            model
            for model in MODELS
            if annotations.get(model, {}).get("status") == "success"
        ]

        if len(successful) != 3:
            continue

        for annotation_type, field in [
            ("Genre", "genre_paths"),
            ("Metadata", "metadata_paths"),
        ]:
            model_sets = {
                model: set(
                    annotations[model].get(field, [])
                )
                for model in MODELS
            }

            all_paths = set().union(*model_sets.values())

            for path in sorted(all_paths):
                models_for = [
                    model
                    for model in MODELS
                    if path in model_sets[model]
                ]

                models_against = [
                    model
                    for model in MODELS
                    if path not in model_sets[model]
                ]

                row = {
                    "debate_id": (
                        f"{isbn}__{annotation_type.lower()}__{path}"
                    ),
                    "isbn13": isbn,
                    "title": title,
                    "annotation_type": annotation_type,
                    "disputed_path": path,
                    "support_count": len(models_for),
                    "models_for": models_for,
                    "models_against": models_against,
                    "filtered_tags": tags,
                }

                if len(models_for) == 3:
                    unanimous.append(row)
                else:
                    conflicts.append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "path_conflicts.json").write_text(
        json.dumps(
            conflicts,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (OUT_DIR / "unanimous_paths.json").write_text(
        json.dumps(
            unanimous,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    csv_path = OUT_DIR / "path_conflicts.csv"

    fields = [
        "debate_id",
        "isbn13",
        "title",
        "annotation_type",
        "disputed_path",
        "support_count",
        "models_for",
        "models_against",
        "filtered_tags",
    ]

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )
        writer.writeheader()

        for row in conflicts:
            out = dict(row)
            out["models_for"] = json.dumps(
                row["models_for"],
                ensure_ascii=False,
            )
            out["models_against"] = json.dumps(
                row["models_against"],
                ensure_ascii=False,
            )
            out["filtered_tags"] = json.dumps(
                row["filtered_tags"],
                ensure_ascii=False,
            )
            writer.writerow(out)

    genre = [
        x for x in conflicts
        if x["annotation_type"] == "Genre"
    ]

    metadata = [
        x for x in conflicts
        if x["annotation_type"] == "Metadata"
    ]

    print("===== PATH-LEVEL CONFLICT BUILD =====")
    print("Input records       :", len(records))
    print("Unanimous paths     :", len(unanimous))
    print("Disputed paths      :", len(conflicts))
    print("Genre disputes      :", len(genre))
    print("Metadata disputes   :", len(metadata))
    print(
        "1/3 disputes        :",
        sum(x["support_count"] == 1 for x in conflicts),
    )
    print(
        "2/3 disputes        :",
        sum(x["support_count"] == 2 for x in conflicts),
    )
    print(
        "Unique books        :",
        len({x["isbn13"] for x in conflicts}),
    )

    assert len(unanimous) == 587
    assert len(conflicts) == 892
    assert len(genre) == 588
    assert len(metadata) == 304

    print("Integrity checks     : PASS")
    print("JSON                 :", OUT_DIR / "path_conflicts.json")
    print("CSV                  :", csv_path)


if __name__ == "__main__":
    main()
