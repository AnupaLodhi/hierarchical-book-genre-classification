import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def test_final_dataset_routing():
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        consensus = work / "results/consensus"
        resolution = work / "results/resolution"

        write_json(
            consensus / "perfect_consensus.json",
            [{
                "isbn13": "P1",
                "title": "Perfect",
                "genre_paths": ["GENRE-P"],
                "metadata_paths": ["META-P"],
            }],
        )

        write_json(
            consensus / "partial_agreement.json",
            [{
                "isbn13": "P2",
                "title": "Partial",
                "agreement_type": "agreement_2_of_3",
                "genre_paths": ["GENRE-PARTIAL"],
                "metadata_paths": [],
            }],
        )

        debate_inputs = []

        for isbn in ["D1", "D2", "D3", "D4"]:
            debate_inputs.append({
                "isbn13": isbn,
                "title": isbn,
                "filtered_tags": ["Fiction"],
                "available_count": 3,
                "original_annotations": {},
            })

        write_json(
            resolution / "debate_inputs.json",
            debate_inputs,
        )

        write_json(
            resolution / "debate_resolutions.json",
            [
                {
                    "isbn13": "D1",
                    "status": "success",
                    "provider": "groq",
                    "model": "openai/gpt-oss-120b",
                    "genre_paths": ["GENRE-D"],
                    "metadata_paths": ["META-D"],
                },
                {
                    "isbn13": "D2",
                    "status": "error",
                    "error": "synthetic API failure",
                },
                {
                    "isbn13": "D3",
                    "status": "success",
                    "provider": "groq",
                    "model": "openai/gpt-oss-120b",
                    "genre_paths": [],
                    "metadata_paths": [],
                },
            ],
        )

        write_json(
            resolution / "incomplete_annotations.json",
            [{
                "isbn13": "I1",
                "title": "Incomplete",
                "available_count": 1,
            }],
        )

        write_json(
            consensus / "no_evidence.json",
            [{
                "isbn13": "N1",
                "title": "No Evidence",
            }],
        )

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/build_final_dataset.py"),
            ],
            cwd=work,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            result.stdout + "\n" + result.stderr
        )

        final = json.loads(
            (work / "results/final/final_output.json")
            .read_text(encoding="utf-8")
        )

        manual = json.loads(
            (work / "results/final/manual_review.json")
            .read_text(encoding="utf-8")
        )

        final_by_isbn = {
            x["isbn13"]: x for x in final
        }

        manual_by_isbn = {
            x["isbn13"]: x for x in manual
        }

        assert set(final_by_isbn) == {
            "P1", "P2", "D1"
        }

        assert final_by_isbn["P1"]["resolution_method"] == (
            "perfect_3_of_3_consensus"
        )

        assert final_by_isbn["P2"]["resolution_method"] == (
            "agreement_2_of_3"
        )

        assert final_by_isbn["D1"]["resolution_method"] == (
            "debate_resolver"
        )

        assert final_by_isbn["D1"]["resolver_provider"] == "groq"
        assert final_by_isbn["D1"]["resolver_model"] == (
            "openai/gpt-oss-120b"
        )

        assert manual_by_isbn["D4"]["review_reason"] == (
            "debate_not_run"
        )

        assert manual_by_isbn["D2"]["review_reason"] == (
            "debate_api_error"
        )

        assert manual_by_isbn["D3"]["review_reason"] == (
            "resolver_returned_empty"
        )

        assert manual_by_isbn["I1"]["review_reason"] == (
            "insufficient_original_annotations"
        )

        assert manual_by_isbn["N1"]["review_reason"] == (
            "no_filtered_tags"
        )

        all_isbns = [
            x["isbn13"] for x in final + manual
        ]

        assert len(all_isbns) == 8
        assert len(all_isbns) == len(set(all_isbns))

        print("Perfect consensus -> final ✓")
        print("Partial agreement -> final ✓")
        print("Successful debate -> final ✓")
        print("Debate not run -> manual ✓")
        print("Debate API error -> manual ✓")
        print("Empty debate result -> manual ✓")
        print("Incomplete annotation -> manual ✓")
        print("No evidence -> manual ✓")
        print("All ISBNs accounted exactly once ✓")
        print("FINAL DATASET ROUTING TEST PASSED ✓")


if __name__ == "__main__":
    test_final_dataset_routing()
