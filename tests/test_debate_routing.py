from scripts.build_debate_inputs import MODELS


def route_conflict(book, conflict):
    anns = book.get("annotations", {})

    successful = {
        model: anns[model]
        for model in MODELS
        if anns.get(model, {}).get("status") == "success"
    }

    record = {
        "isbn13": str(book["isbn13"]),
        "title": book.get("title", ""),
        "filtered_tags": book.get("filtered_tags", []),
        "available_models": list(successful),
        "available_count": len(successful),
        "agreement_type": conflict.get("agreement_type", ""),
        "original_annotations": successful,
    }

    if len(successful) >= 2:
        return "debate", record

    record["model_statuses"] = {
        model: anns.get(model, {}).get("status", "missing")
        for model in MODELS
    }

    return "incomplete", record


def ann(status, genre=None, metadata=None):
    return {
        "status": status,
        "genre_paths": genre or [],
        "metadata_paths": metadata or [],
    }


def test_routing():
    conflict = {
        "isbn13": "TEST-1",
        "agreement_type": "conflict_3_original_models",
    }

    two_success = {
        "isbn13": "TEST-1",
        "title": "Two Successful Models",
        "filtered_tags": ["Fiction"],
        "annotations": {
            "qwen_groq": ann("success", ["A"]),
            "gpt_oss_groq": ann("success", ["B"]),
            "gemini_google": ann("error"),
        },
    }

    bucket, record = route_conflict(two_success, conflict)

    assert bucket == "debate"
    assert record["available_count"] == 2
    assert set(record["available_models"]) == {
        "qwen_groq",
        "gpt_oss_groq",
    }
    assert len(record["original_annotations"]) == 2

    one_success = {
        "isbn13": "TEST-2",
        "title": "One Successful Model",
        "filtered_tags": ["Fiction"],
        "annotations": {
            "qwen_groq": ann("success", ["A"]),
            "gpt_oss_groq": ann("error"),
            "gemini_google": ann("error"),
        },
    }

    bucket, record = route_conflict(
        one_success,
        {
            "isbn13": "TEST-2",
            "agreement_type": "insufficient_models",
        },
    )

    assert bucket == "incomplete"
    assert record["available_count"] == 1
    assert record["model_statuses"]["qwen_groq"] == "success"
    assert record["model_statuses"]["gpt_oss_groq"] == "error"
    assert record["model_statuses"]["gemini_google"] == "error"

    zero_success = {
        "isbn13": "TEST-3",
        "annotations": {
            "qwen_groq": ann("error"),
            "gpt_oss_groq": ann("error"),
            "gemini_google": ann("error"),
        },
    }

    bucket, record = route_conflict(
        zero_success,
        {
            "isbn13": "TEST-3",
            "agreement_type": "insufficient_models",
        },
    )

    assert bucket == "incomplete"
    assert record["available_count"] == 0

    print("2 successful models -> debate ✓")
    print("1 successful model -> incomplete ✓")
    print("0 successful models -> incomplete ✓")
    print("Provider failures are not treated as disagreement ✓")
    print("DEBATE ROUTING TEST PASSED ✓")


if __name__ == "__main__":
    test_routing()
