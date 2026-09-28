import csv
import json
from collections import defaultdict
from pathlib import Path


SOURCE = Path(
    "results/annotations/complete_397_snapshot/"
    "multi_llm_annotations_397.json"
)

UNANIMOUS = Path(
    "results/path_debate_v2/unanimous_paths.json"
)

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

FINAL = Path(
    "results/path_debate_v2/frozen_final/"
    "final_adjudication_892_complete.json"
)

OUTPUT_DIR = Path(
    "results/final_outputs"
)


MODEL_ORDER = [
    "qwen_groq",
    "gpt_oss_groq",
    "gpt_oss_20b",
]


def load_json(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def json_cell(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def write_csv(path, rows, fieldnames):
    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    source = load_json(SOURCE)
    unanimous = load_json(UNANIMOUS)
    conflicts = load_json(CONFLICTS)
    round1 = load_json(ROUND1)
    round2 = load_json(ROUND2)
    final = load_json(FINAL)

    annotatable = [
        record
        for record in source
        if record.get("filtered_tags")
    ]

    assert len(source) == 400
    assert len(annotatable) == 397
    assert len(unanimous) == 587
    assert len(conflicts) == 892
    assert len(round1) == 1259
    assert len(round2) == 963
    assert len(final) == 892

    assert all(
        row["status"] == "success"
        for row in round1
    )

    assert all(
        row["status"] == "success"
        for row in round2
    )

    source_by_isbn = {
        record["isbn13"]: record
        for record in annotatable
    }

    conflict_by_id = {
        row["debate_id"]: row
        for row in conflicts
    }

    final_by_id = {
        row["debate_id"]: row
        for row in final
    }

    r1_by_id = defaultdict(list)
    for row in round1:
        r1_by_id[row["debate_id"]].append(
            row
        )

    r2_by_id = defaultdict(list)
    for row in round2:
        r2_by_id[row["debate_id"]].append(
            row
        )

    assert len(conflict_by_id) == 892
    assert len(final_by_id) == 892
    assert set(conflict_by_id) == set(final_by_id)

    verdict_counts = defaultdict(int)

    for row in final:
        verdict_counts[
            row["final_verdict"]
        ] += 1

    assert verdict_counts["ACCEPT"] == 476
    assert verdict_counts["REJECT"] == 248
    assert verdict_counts["MANUAL"] == 168

    accepted_paths = defaultdict(
        lambda: {
            "Genre": set(),
            "Metadata": set(),
        }
    )

    for row in unanimous:
        accepted_paths[
            row["isbn13"]
        ][
            row["annotation_type"]
        ].add(
            row["disputed_path"]
        )

    for row in final:
        if row["final_verdict"] == "ACCEPT":
            accepted_paths[
                row["isbn13"]
            ][
                row["annotation_type"]
            ].add(
                row["disputed_path"]
            )

    perfect_rows = []

    for row in sorted(
        unanimous,
        key=lambda x: (
            x["isbn13"],
            x["annotation_type"],
            x["disputed_path"],
        ),
    ):
        perfect_rows.append({
            "Debate_ID":
                row["debate_id"],
            "ISBN-13":
                row["isbn13"],
            "Title":
                row.get("title", ""),
            "Annotation_Type":
                row["annotation_type"],
            "Consensus_Path":
                row["disputed_path"],
            "Support_Count":
                row["support_count"],
            "Models_For":
                json_cell(
                    row["models_for"]
                ),
            "Filtered_Tags":
                json_cell(
                    row.get(
                        "filtered_tags",
                        [],
                    )
                ),
        })

    conflicting_rows = []

    for row in sorted(
        conflicts,
        key=lambda x: (
            x["isbn13"],
            x["annotation_type"],
            x["disputed_path"],
        ),
    ):
        conflicting_rows.append({
            "Debate_ID":
                row["debate_id"],
            "ISBN-13":
                row["isbn13"],
            "Title":
                row.get("title", ""),
            "Annotation_Type":
                row["annotation_type"],
            "Disputed_Path":
                row["disputed_path"],
            "Support_Count":
                row["support_count"],
            "Models_For":
                json_cell(
                    row["models_for"]
                ),
            "Models_Against":
                json_cell(
                    row["models_against"]
                ),
            "Filtered_Tags":
                json_cell(
                    row.get(
                        "filtered_tags",
                        [],
                    )
                ),
        })

    debate_rows = []

    for result in sorted(
        final,
        key=lambda x: (
            x["isbn13"],
            x["annotation_type"],
            x["disputed_path"],
        ),
    ):
        debate_id = result["debate_id"]

        conflict = conflict_by_id[
            debate_id
        ]

        r1_records = sorted(
            r1_by_id.get(
                debate_id,
                [],
            ),
            key=lambda x: MODEL_ORDER.index(
                x["supporter_model"]
            ),
        )

        r2_records = sorted(
            r2_by_id.get(
                debate_id,
                [],
            ),
            key=lambda x: MODEL_ORDER.index(
                x["opponent_model"]
            ),
        )

        r1_detail = [
            {
                "model":
                    item["supporter_model"],
                "decision":
                    item["decision"],
                "evidence_tags":
                    item["evidence_tags"],
                "justification":
                    item["justification"],
            }
            for item in r1_records
        ]

        r2_detail = [
            {
                "model":
                    item["opponent_model"],
                "decision":
                    item["decision"],
                "evidence_tags":
                    item["evidence_tags"],
                "justification":
                    item["justification"],
            }
            for item in r2_records
        ]

        decisions = {}

        for model in MODEL_ORDER:
            if model in result[
                "round1_decisions"
            ]:
                decisions[model] = (
                    result[
                        "round1_decisions"
                    ][model]
                )

            if model in result[
                "round2_decisions"
            ]:
                decisions[model] = (
                    result[
                        "round2_decisions"
                    ][model]
                )

        debate_rows.append({
            "Debate_ID":
                debate_id,
            "ISBN-13":
                result["isbn13"],
            "Title":
                result.get("title", ""),
            "Annotation_Type":
                result["annotation_type"],
            "Disputed_Path":
                result["disputed_path"],
            "Support_Count":
                result["support_count"],
            "Models_For":
                json_cell(
                    result["models_for"]
                ),
            "Models_Against":
                json_cell(
                    result["models_against"]
                ),
            "Filtered_Tags":
                json_cell(
                    conflict.get(
                        "filtered_tags",
                        [],
                    )
                ),
            "Round1_Detail":
                json_cell(r1_detail),
            "Round2_Detail":
                json_cell(r2_detail),
            "Qwen_Decision":
                decisions.get(
                    "qwen_groq",
                    "",
                ),
            "GPT_OSS_120B_Decision":
                decisions.get(
                    "gpt_oss_groq",
                    "",
                ),
            "GPT_OSS_20B_Decision":
                decisions.get(
                    "gpt_oss_20b",
                    "",
                ),
            "Adjudication_Reason":
                result[
                    "adjudication_reason"
                ],
            "Final_Verdict":
                result[
                    "final_verdict"
                ],
        })

    resolved_rows = [
        row
        for row in debate_rows
        if row["Final_Verdict"] == "ACCEPT"
    ]

    manual_rows = [
        row
        for row in debate_rows
        if row["Final_Verdict"] == "MANUAL"
    ]

    full_rows = []

    for record in sorted(
        annotatable,
        key=lambda x: x["isbn13"],
    ):
        isbn = record["isbn13"]

        genre_paths = sorted(
            accepted_paths[
                isbn
            ]["Genre"]
        )

        metadata_paths = sorted(
            accepted_paths[
                isbn
            ]["Metadata"]
        )

        manual_for_book = [
            row
            for row in final
            if (
                row["isbn13"] == isbn
                and row[
                    "final_verdict"
                ] == "MANUAL"
            )
        ]

        rejected_for_book = [
            row
            for row in final
            if (
                row["isbn13"] == isbn
                and row[
                    "final_verdict"
                ] == "REJECT"
            )
        ]

        annotations = record[
            "annotations"
        ]

        full_rows.append({
            "ISBN-13":
                isbn,
            "Title":
                record.get("title", ""),
            "Filtered_Tags":
                json_cell(
                    record.get(
                        "filtered_tags",
                        [],
                    )
                ),
            "Qwen_Genre_Paths":
                json_cell(
                    annotations[
                        "qwen_groq"
                    ].get(
                        "genre_paths",
                        [],
                    )
                ),
            "Qwen_Metadata_Paths":
                json_cell(
                    annotations[
                        "qwen_groq"
                    ].get(
                        "metadata_paths",
                        [],
                    )
                ),
            "GPT_OSS_120B_Genre_Paths":
                json_cell(
                    annotations[
                        "gpt_oss_groq"
                    ].get(
                        "genre_paths",
                        [],
                    )
                ),
            "GPT_OSS_120B_Metadata_Paths":
                json_cell(
                    annotations[
                        "gpt_oss_groq"
                    ].get(
                        "metadata_paths",
                        [],
                    )
                ),
            "GPT_OSS_20B_Genre_Paths":
                json_cell(
                    annotations[
                        "gpt_oss_20b"
                    ].get(
                        "genre_paths",
                        [],
                    )
                ),
            "GPT_OSS_20B_Metadata_Paths":
                json_cell(
                    annotations[
                        "gpt_oss_20b"
                    ].get(
                        "metadata_paths",
                        [],
                    )
                ),
            "Final_Genre_Paths":
                json_cell(
                    genre_paths
                ),
            "Final_Metadata_Paths":
                json_cell(
                    metadata_paths
                ),
            "Accepted_Path_Count":
                (
                    len(genre_paths)
                    + len(metadata_paths)
                ),
            "Manual_Path_Count":
                len(manual_for_book),
            "Rejected_Path_Count":
                len(rejected_for_book),
            "Has_Manual_Review":
                (
                    "YES"
                    if manual_for_book
                    else "NO"
                ),
        })

    debate_fields = [
        "Debate_ID",
        "ISBN-13",
        "Title",
        "Annotation_Type",
        "Disputed_Path",
        "Support_Count",
        "Models_For",
        "Models_Against",
        "Filtered_Tags",
        "Round1_Detail",
        "Round2_Detail",
        "Qwen_Decision",
        "GPT_OSS_120B_Decision",
        "GPT_OSS_20B_Decision",
        "Adjudication_Reason",
        "Final_Verdict",
    ]

    write_csv(
        OUTPUT_DIR
        / "New_conflicting_genres.csv",
        conflicting_rows,
        list(
            conflicting_rows[0].keys()
        ),
    )

    write_csv(
        OUTPUT_DIR
        / "New_perfect_consensus.csv",
        perfect_rows,
        list(
            perfect_rows[0].keys()
        ),
    )

    write_csv(
        OUTPUT_DIR
        / "New_resolved_accepts.csv",
        resolved_rows,
        debate_fields,
    )

    write_csv(
        OUTPUT_DIR
        / "New_manual_review.csv",
        manual_rows,
        debate_fields,
    )

    write_csv(
        OUTPUT_DIR
        / "New_full_output.csv",
        full_rows,
        list(
            full_rows[0].keys()
        ),
    )

    total_accepted = sum(
        row["Accepted_Path_Count"]
        for row in full_rows
    )

    zero_accepted = sum(
        row["Accepted_Path_Count"] == 0
        for row in full_rows
    )

    manual_books = sum(
        row["Has_Manual_Review"] == "YES"
        for row in full_rows
    )

    assert len(conflicting_rows) == 892
    assert len(perfect_rows) == 587
    assert len(resolved_rows) == 476
    assert len(manual_rows) == 168
    assert len(full_rows) == 397

    assert total_accepted == 1063
    assert zero_accepted == 11
    assert manual_books == 126

    print(
        "===== FINAL OUTPUT BUILD ====="
    )
    print(
        "Conflicting paths :",
        len(conflicting_rows),
    )
    print(
        "Perfect consensus :",
        len(perfect_rows),
    )
    print(
        "Resolved ACCEPT   :",
        len(resolved_rows),
    )
    print(
        "Manual review     :",
        len(manual_rows),
    )
    print(
        "Full output books :",
        len(full_rows),
    )
    print(
        "Accepted paths    :",
        total_accepted,
    )
    print(
        "Zero-path books   :",
        zero_accepted,
    )
    print(
        "Manual books      :",
        manual_books,
    )
    print(
        "VERDICT           : PASS"
    )


if __name__ == "__main__":
    main()

