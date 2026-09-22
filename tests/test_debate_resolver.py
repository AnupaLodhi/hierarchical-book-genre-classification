from agents.annotation_agent import (
    load_taxonomies,
    retrieve_candidate_paths,
    validate_annotation,
)
from agents.debate_resolver import build_debate_prompt


def test_debate_candidate_and_safety_rules():
    taxonomies = load_taxonomies()

    filtered_tags = [
        "Short stories",
        "Fiction",
        "Teen & Young Adult",
        "English Short stories",
    ]

    candidates = retrieve_candidate_paths(
        filtered_tags,
        taxonomies,
    )

    genre_candidates = candidates["genre_paths"]
    metadata_candidates = candidates["metadata_paths"]

    assert genre_candidates, "No genre candidates retrieved"
    assert metadata_candidates, "No metadata candidates retrieved"

    book = {
        "isbn13": "TEST-ISBN",
        "title": "Synthetic Debate Test",
        "filtered_tags": filtered_tags,
        "original_annotations": {
            "qwen_groq": {
                "status": "success",
                "genre_paths": genre_candidates[:1],
                "metadata_paths": metadata_candidates[:1],
            },
            "gpt_oss_groq": {
                "status": "success",
                "genre_paths": genre_candidates[:2],
                "metadata_paths": metadata_candidates[:2],
            },
        },
    }

    prompt = build_debate_prompt(book, candidates)
    prompt_lower = prompt.lower()

    required_rules = [
        "filtered",
        "candidate",
        "fiction",
        "nonfiction",
        "geograph",
        "temporal",
    ]

    for rule in required_rules:
        assert rule in prompt_lower, f"Missing debate safeguard: {rule}"

    valid = {
        "genre_paths": genre_candidates[:1],
        "metadata_paths": metadata_candidates[:1],
    }

    validate_annotation(
        valid,
        taxonomies,
        candidates,
    )

    invalid = {
        "genre_paths": ["Fiction / Completely Invented Genre"],
        "metadata_paths": [],
    }

    rejected = False

    try:
        validate_annotation(
            invalid,
            taxonomies,
            candidates,
        )
    except (ValueError, AssertionError, TypeError):
        rejected = True

    assert rejected, "Invented taxonomy path was not rejected"

    print("Genre candidates:", len(genre_candidates))
    print("Metadata candidates:", len(metadata_candidates))
    print("Valid candidate accepted ✓")
    print("Invented taxonomy path rejected ✓")
    print("Required debate safeguards present ✓")
    print("DEBATE SAFETY TEST PASSED ✓")


if __name__ == "__main__":
    test_debate_candidate_and_safety_rules()
