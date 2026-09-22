import json
import subprocess
import sys
import tempfile
from pathlib import Path

from agents.annotation_agent import load_taxonomies


ROOT = Path(__file__).resolve().parents[1]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def run_audit(final, manual):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        taxonomy_dir = work / "taxonomy"
        taxonomy_dir.mkdir(parents=True, exist_ok=True)

        for name in [
            "genre_hierarchy.json",
            "metadata_hierarchy.json",
        ]:
            source = ROOT / "taxonomy" / name
            target = taxonomy_dir / name
            target.write_text(
                source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        write_json(
            work / "results/final/final_output.json",
            final,
        )
        write_json(
            work / "results/final/manual_review.json",
            manual,
        )

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/audit_final_output.py"),
            ],
            cwd=work,
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "PYTHONPATH": str(ROOT),
            },
        )

        return result, work


def test_integrity_audit():
    tax = load_taxonomies()

    valid_genre = tax["genre_paths"][0]
    valid_metadata = tax["metadata_paths"][0]

    valid_final = [{
        "isbn13": "VALID-1",
        "title": "Valid",
        "resolution_method": "synthetic_test",
        "genre_paths": [valid_genre],
        "metadata_paths": [valid_metadata],
    }]

    result, _ = run_audit(valid_final, [])

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )
    assert "FINAL INTEGRITY AUDIT PASSED" in result.stdout

    bad_genre = [{
        "isbn13": "BAD-GENRE",
        "title": "Bad Genre",
        "resolution_method": "synthetic_test",
        "genre_paths": [
            "Fiction / Completely Invented Genre"
        ],
        "metadata_paths": [],
    }]

    result, _ = run_audit(bad_genre, [])
    assert result.returncode != 0
    assert "Invalid genre taxonomy path detected" in (
        result.stdout + result.stderr
    )

    empty = [{
        "isbn13": "EMPTY",
        "title": "Empty",
        "resolution_method": "synthetic_test",
        "genre_paths": [],
        "metadata_paths": [],
    }]

    result, _ = run_audit(empty, [])
    assert result.returncode != 0
    assert "Empty resolved annotation detected" in (
        result.stdout + result.stderr
    )

    duplicate_final = [
        {
            "isbn13": "DUP",
            "title": "One",
            "resolution_method": "synthetic_test",
            "genre_paths": [valid_genre],
            "metadata_paths": [],
        },
        {
            "isbn13": "DUP",
            "title": "Two",
            "resolution_method": "synthetic_test",
            "genre_paths": [valid_genre],
            "metadata_paths": [],
        },
    ]

    result, _ = run_audit(duplicate_final, [])
    assert result.returncode != 0
    assert "ISBN duplication detected" in (
        result.stdout + result.stderr
    )

    manual = [{
        "isbn13": "OVERLAP",
        "review_reason": "synthetic",
    }]

    overlap_final = [{
        "isbn13": "OVERLAP",
        "title": "Overlap",
        "resolution_method": "synthetic_test",
        "genre_paths": [valid_genre],
        "metadata_paths": [],
    }]

    result, _ = run_audit(overlap_final, manual)
    assert result.returncode != 0

    bad_metadata = [{
        "isbn13": "BAD-META",
        "title": "Bad Metadata",
        "resolution_method": "synthetic_test",
        "genre_paths": [valid_genre],
        "metadata_paths": [
            "Completely / Invented / Metadata"
        ],
    }]

    result, _ = run_audit(bad_metadata, [])
    assert result.returncode != 0
    assert "Invalid metadata taxonomy path detected" in (
        result.stdout + result.stderr
    )

    fiction_path = next(
        x for x in tax["genre_paths"]
        if x.split(" / ")[0] == "Fiction"
    )

    nonfiction_path = next(
        x for x in tax["genre_paths"]
        if x.split(" / ")[0] == "Nonfiction"
    )

    fiction_nonfiction = [{
        "isbn13": "ROOT-CONFLICT",
        "title": "Root Conflict",
        "resolution_method": "synthetic_test",
        "genre_paths": [
            fiction_path,
            nonfiction_path,
        ],
        "metadata_paths": [],
    }]

    result, _ = run_audit(fiction_nonfiction, [])
    assert result.returncode != 0
    assert "Book classified as both Fiction and Nonfiction" in (
        result.stdout + result.stderr
    )

    print("Valid final record -> audit passes ✓")
    print("Invented genre path -> rejected ✓")
    print("Invented metadata path -> rejected ✓")
    print("Fiction + Nonfiction -> rejected ✓")
    print("Empty resolved record -> rejected ✓")
    print("Duplicate ISBN -> rejected ✓")
    print("Final/manual overlap -> rejected ✓")
    print("FINAL INTEGRITY TEST PASSED ✓")


if __name__ == "__main__":
    test_integrity_audit()
