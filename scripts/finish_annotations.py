import json
import subprocess
import sys
import time
from pathlib import Path

ANNOTATIONS = Path(
    "results/annotations/multi_llm_annotations.json"
)

MODELS = [
    "qwen_groq",
    "gpt_oss_groq",
    "gpt_oss_20b",
]

TARGET = 397

WAIT_SECONDS = 60
MAX_ROUNDS = 30


def counts():
    data = json.loads(
        ANNOTATIONS.read_text(encoding="utf-8")
    )

    result = {}

    for model in MODELS:
        success = 0

        for record in data:
            annotation = (
                record
                .get("annotations", {})
                .get(model, {})
            )

            if annotation.get("status") == "success":
                success += 1

        result[model] = success

    return result


def remaining_total(stats):
    return sum(
        max(0, TARGET - stats[model])
        for model in MODELS
    )


print("========================================")
print("AUTOMATIC ANNOTATION COMPLETION")
print("========================================")

previous_remaining = None
no_progress_rounds = 0

for round_number in range(1, MAX_ROUNDS + 1):

    before = counts()
    remaining = remaining_total(before)

    print()
    print(f"===== ROUND {round_number} =====")
    print("Before:")
    print(before)
    print("Remaining:", remaining)

    if remaining == 0:
        print()
        print("ALL ANNOTATIONS COMPLETE")
        sys.exit(0)

    subprocess.run(
        [
            sys.executable,
            "scripts/run_annotations.py",
            "--delay",
            "0.5",
        ],
        env={
            **__import__("os").environ,
            "PYTHONPATH": ".",
        },
        check=False,
    )

    after = counts()
    new_remaining = remaining_total(after)

    gained = remaining - new_remaining

    print()
    print("After:")
    print(after)
    print("Remaining:", new_remaining)
    print("New successes:", gained)

    if new_remaining == 0:
        print()
        print("========================================")
        print("ALL 3-MODEL ANNOTATIONS COMPLETE")
        print("========================================")
        sys.exit(0)

    if gained == 0:
        no_progress_rounds += 1
    else:
        no_progress_rounds = 0

    if no_progress_rounds >= 3:
        print()
        print(
            "No progress for 3 consecutive rounds."
        )
        print(
            "Stopping to avoid hammering the API."
        )
        print(
            "Daily quota probably needs to reset."
        )
        sys.exit(0)

    previous_remaining = new_remaining

    print()
    print(
        f"Waiting {WAIT_SECONDS} seconds "
        "before next round..."
    )

    time.sleep(WAIT_SECONDS)

print()
print("Reached maximum automatic rounds.")
print("Run this script again after quota reset.")
