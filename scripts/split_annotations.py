import json
from pathlib import Path

INPUT = Path("results/annotations/multi_llm_annotations.json")
OUTPUT_DIR = Path("results/annotations")

MODELS = ("qwen_groq", "gpt_oss_groq", "gpt_oss_20b")


def main():
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)

    records = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for model in MODELS:
        output = []

        for record in records:
            annotation = record.get(
                "annotations", {}
            ).get(model, {})

            output.append({
                "isbn13": record.get("isbn13"),
                "title": record.get("title", ""),
                "filtered_tags": record.get(
                    "filtered_tags", []
                ),
                "status": annotation.get(
                    "status", "missing"
                ),
                "model": annotation.get(
                    "model", ""
                ),
                "genre_paths": annotation.get(
                    "genre_paths", []
                ),
                "metadata_paths": annotation.get(
                    "metadata_paths", []
                ),
                "error": annotation.get(
                    "error", ""
                ),
            })

        path = OUTPUT_DIR / f"{model}_annotations.json"

        path.write_text(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        success = sum(
            x["status"] == "success"
            for x in output
        )

        print(
            f"{model:8s} records={len(output)} "
            f"success={success} -> {path}"
        )


if __name__ == "__main__":
    main()
