import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


CONFLICTS = Path(
    "results/path_debate_v2/path_conflicts.json"
)

ROUND1 = Path(
    "results/path_debate_v2/frozen_round1/"
    "round1_supporters_1259_complete.json"
)

ROUND2 = Path(
    "results/path_debate_v2/frozen_round2/"
    "round2_opponents_963_complete.json"
)

OUTPUT_JSON = Path(
    "results/path_debate_v2/final_adjudication.json"
)

OUTPUT_CSV = Path(
    "results/path_debate_v2/final_adjudication.csv"
)


def load_json(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def adjudicate(dispute, round1_records, round2_records):
    support_count = dispute["support_count"]

    r1 = [
        x["decision"]
        for x in round1_records
    ]

    r2 = [
        x["decision"]
        for x in round2_records
    ]

    if support_count == 1:
        if r1 == ["RETRACT"]:
            return "REJECT", "1of3_supporter_retracted"

        if r1 == ["MAINTAIN"]:
            if sorted(r2) == ["ACCEPT", "ACCEPT"]:
                return "ACCEPT", "1of3_both_opponents_accept"

            if sorted(r2) == ["REJECT", "REJECT"]:
                return "REJECT", "1of3_both_opponents_reject"

            if sorted(r2) == ["ACCEPT", "REJECT"]:
                return "MANUAL", "1of3_opponents_split"

        raise ValueError(
            f"Unexpected 1/3 state: R1={r1}, R2={r2}"
        )

    if support_count == 2:
        maintain = r1.count("MAINTAIN")
        retract = r1.count("RETRACT")

        if retract == 2:
            return "REJECT", "2of3_both_supporters_retracted"

        if maintain == 1 and retract == 1:
            return "MANUAL", "2of3_supporters_split"

        if maintain == 2:
            if r2 == ["ACCEPT"]:
                return "ACCEPT", "2of3_opponent_accepts"

            if r2 == ["REJECT"]:
                return "MANUAL", "2of3_opponent_rejects"

        raise ValueError(
            f"Unexpected 2/3 state: R1={r1}, R2={r2}"
        )

    raise ValueError(
        f"Unexpected support_count={support_count}"
    )


def main():
    conflicts = load_json(CONFLICTS)
    round1 = load_json(ROUND1)
    round2 = load_json(ROUND2)

    r1_by_debate = defaultdict(list)
    r2_by_debate = defaultdict(list)

    for record in round1:
        if record.get("status") != "success":
            raise ValueError(
                "Non-success record found in frozen Round 1"
            )

        r1_by_debate[
            record["debate_id"]
        ].append(record)

    for record in round2:
        if record.get("status") != "success":
            raise ValueError(
                "Non-success record found in frozen Round 2"
            )

        r2_by_debate[
            record["debate_id"]
        ].append(record)

    results = []

    for dispute in conflicts:
        debate_id = dispute["debate_id"]

        r1_records = r1_by_debate[debate_id]
        r2_records = r2_by_debate.get(
            debate_id,
            [],
        )

        if len(r1_records) != dispute["support_count"]:
            raise ValueError(
                f"Round 1 count mismatch: {debate_id}"
            )

        verdict, reason = adjudicate(
            dispute,
            r1_records,
            r2_records,
        )

        results.append({
            "debate_id": debate_id,
            "isbn13": dispute["isbn13"],
            "title": dispute.get("title", ""),
            "annotation_type":
                dispute["annotation_type"],
            "disputed_path":
                dispute["disputed_path"],
            "support_count":
                dispute["support_count"],
            "models_for":
                dispute["models_for"],
            "models_against":
                dispute["models_against"],
            "round1_decisions": {
                x["supporter_model"]: x["decision"]
                for x in r1_records
            },
            "round2_decisions": {
                x["opponent_model"]: x["decision"]
                for x in r2_records
            },
            "final_verdict": verdict,
            "adjudication_reason": reason,
        })

    if len(results) != 892:
        raise ValueError(
            f"Expected 892 adjudications, got {len(results)}"
        )

    counts = Counter(
        x["final_verdict"]
        for x in results
    )

    if sum(counts.values()) != 892:
        raise ValueError(
            "Final verdict count integrity failure"
        )

    OUTPUT_JSON.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fieldnames = [
        "debate_id",
        "isbn13",
        "title",
        "annotation_type",
        "disputed_path",
        "support_count",
        "models_for",
        "models_against",
        "round1_decisions",
        "round2_decisions",
        "final_verdict",
        "adjudication_reason",
    ]

    with OUTPUT_CSV.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in results:
            csv_row = row.copy()

            for field in (
                "models_for",
                "models_against",
                "round1_decisions",
                "round2_decisions",
            ):
                csv_row[field] = json.dumps(
                    csv_row[field],
                    ensure_ascii=False,
                )

            writer.writerow(csv_row)

    print("===== FINAL PATH ADJUDICATION =====")
    print("Disputed paths :", len(results))
    print("ACCEPT         :", counts["ACCEPT"])
    print("REJECT         :", counts["REJECT"])
    print("MANUAL         :", counts["MANUAL"])
    print(
        "TOTAL          :",
        counts["ACCEPT"]
        + counts["REJECT"]
        + counts["MANUAL"],
    )
    print("JSON           :", OUTPUT_JSON)
    print("CSV            :", OUTPUT_CSV)
    print("VERDICT        : PASS")


if __name__ == "__main__":
    main()
