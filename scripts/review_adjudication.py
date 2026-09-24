"""
Interactive human adjudication tool.

Reviews isolated singleton candidates created by
prepare_adjudication.py.

Features:
- one case at a time
- ACCEPT / REJECT / UNSURE
- HIGH / MEDIUM / LOW confidence
- rationale
- autosave after every decision
- safe resume
- progress summary
"""

import csv
from pathlib import Path


FILE = Path(
    "results/adjudication/adjudication_interim.csv"
)

VALID_DECISIONS = {
    "A": "ACCEPT",
    "R": "REJECT",
    "U": "UNSURE",
}

VALID_CONFIDENCE = {
    "H": "HIGH",
    "M": "MEDIUM",
    "L": "LOW",
}


def load_rows():
    if not FILE.exists():
        raise FileNotFoundError(
            f"Missing adjudication file: {FILE}"
        )

    with FILE.open(
        encoding="utf-8"
    ) as f:
        rows = list(
            csv.DictReader(f)
        )

    if not rows:
        raise ValueError(
            "Adjudication file is empty."
        )

    return rows


def save_rows(rows):
    temp = FILE.with_suffix(
        ".tmp"
    )

    with temp.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)

    temp.replace(FILE)


def is_complete(row):
    return bool(
        row["decision"].strip()
    )


def show_progress(rows):
    total = len(rows)

    completed = sum(
        is_complete(row)
        for row in rows
    )

    remaining = (
        total - completed
    )

    accepted = sum(
        row["decision"] == "ACCEPT"
        for row in rows
    )

    rejected = sum(
        row["decision"] == "REJECT"
        for row in rows
    )

    unsure = sum(
        row["decision"] == "UNSURE"
        for row in rows
    )

    print()
    print("=" * 72)
    print("ADJUDICATION PROGRESS")
    print("=" * 72)

    print(
        f"Completed : {completed}/{total}"
    )

    print(
        f"Remaining : {remaining}"
    )

    print(
        f"ACCEPT    : {accepted}"
    )

    print(
        f"REJECT    : {rejected}"
    )

    print(
        f"UNSURE    : {unsure}"
    )

    print("=" * 72)


def print_multivalue(
    label,
    value,
):
    print(f"\n{label}:")

    if not value.strip():
        print("  [NONE]")
        return

    parts = [
        x.strip()
        for x in value.split("|")
        if x.strip()
    ]

    for part in parts:
        print(
            "  -",
            part,
        )


def display_case(
    row,
    number,
    total,
):
    print(
        "\n"
        + "=" * 90
    )

    print(
        f"{row['case_id']} "
        f"({number}/{total})"
    )

    print("=" * 90)

    print(
        "TITLE:",
        row["title"],
    )

    print(
        "ISBN:",
        row["isbn13"],
    )

    print(
        "FIELD:",
        row["field"].upper(),
    )

    print()
    print("DISPUTED CANDIDATE:")
    print(
        "  ",
        row["candidate_path"],
    )

    print(
        "\nPROPOSED BY:",
        row["proposed_by"],
    )

    print_multivalue(
        "SOURCE TAGS",
        row["filtered_tags"],
    )

    print_multivalue(
        "CURRENT CANONICAL CONSENSUS",
        row["canonical_paths"],
    )

    print()
    print("-" * 90)

    print(
        "Question: Do the SOURCE TAGS "
        "sufficiently support this exact "
        "candidate path?"
    )

    print()
    print(
        "[A] ACCEPT   "
        "[R] REJECT   "
        "[U] UNSURE   "
        "[Q] QUIT"
    )


def get_decision():
    while True:
        value = input(
            "\nDecision: "
        ).strip().upper()

        if value == "Q":
            return None

        if value in VALID_DECISIONS:
            return VALID_DECISIONS[
                value
            ]

        print(
            "Enter A, R, U, or Q."
        )


def get_confidence():
    while True:
        value = input(
            "Confidence "
            "[H/M/L]: "
        ).strip().upper()

        if value in VALID_CONFIDENCE:
            return VALID_CONFIDENCE[
                value
            ]

        print(
            "Enter H, M, or L."
        )


def get_rationale():
    while True:
        value = input(
            "Short rationale: "
        ).strip()

        if value:
            return value

        print(
            "Please enter a short "
            "evidence-based rationale."
        )


def main():
    rows = load_rows()

    show_progress(rows)

    pending_indices = [
        i
        for i, row in enumerate(rows)
        if not is_complete(row)
    ]

    if not pending_indices:
        print(
            "\nAll adjudication cases "
            "are already complete."
        )
        return

    print()
    print(
        "Starting from first "
        "unfinished case."
    )

    print(
        "Progress is saved after "
        "every decision."
    )

    print(
        "Use Q whenever you want "
        "to stop safely."
    )

    for position, index in enumerate(
        pending_indices,
        start=1,
    ):
        row = rows[index]

        completed_before = (
            len(rows)
            - len(pending_indices)
        )

        overall_number = (
            completed_before
            + position
        )

        display_case(
            row,
            overall_number,
            len(rows),
        )

        decision = get_decision()

        if decision is None:
            print(
                "\nNo changes made to "
                "the current case."
            )

            show_progress(rows)

            print(
                "\nSafe to resume later."
            )
            return

        confidence = (
            get_confidence()
        )

        rationale = (
            get_rationale()
        )

        row["decision"] = decision
        row["confidence"] = confidence
        row["rationale"] = rationale
        row["adjudicator"] = "A1"

        save_rows(rows)

        print(
            "\n✓ Saved",
            row["case_id"],
        )

        # Stop every 10 newly reviewed
        # cases to reduce reviewer fatigue.
        if position % 10 == 0:
            show_progress(rows)

            answer = input(
                "\n10 cases completed. "
                "Continue? [Y/N]: "
            ).strip().upper()

            if answer != "Y":
                print(
                    "\nSaved. Resume "
                    "whenever you're ready."
                )
                return

    show_progress(rows)

    print(
        "\nAll adjudication cases "
        "completed."
    )


if __name__ == "__main__":
    main()
