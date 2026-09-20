import json

from agents.annotation_agent import (
    retrieve_candidate_paths,
    validate_annotation,
)
from agents.genre_filtering_agent import (
    query_openrouter,
    extract_json,
)

DEFAULT_RESOLVER_MODEL = "nex-agi/nex-n2.5-pro:free"


def build_debate_prompt(book, candidates):
    original = book["original_annotations"]

    model_outputs = {}
    for model, ann in original.items():
        model_outputs[model] = {
            "genre_paths": ann.get("genre_paths", []),
            "metadata_paths": ann.get("metadata_paths", []),
        }

    return f"""
You are the final debate resolver for a hierarchical book genre
classification system.

BOOK
ISBN: {book["isbn13"]}
Title: {book.get("title", "")}

FILTERED SOURCE-EVIDENCE TAGS
{json.dumps(book.get("filtered_tags", []), ensure_ascii=False)}

ORIGINAL INDEPENDENT MODEL ANNOTATIONS
{json.dumps(model_outputs, indent=2, ensure_ascii=False)}

VALID GENRE CANDIDATE PATHS
{json.dumps(candidates["genre_paths"], indent=2, ensure_ascii=False)}

VALID METADATA CANDIDATE PATHS
{json.dumps(candidates["metadata_paths"], indent=2, ensure_ascii=False)}

Resolve the disagreement using the following rules:

1. Filtered source tags are the primary evidence.
2. Original model annotations are proposals, not ground truth.
3. Select only paths directly supported by the filtered tags.
4. Use ONLY exact paths from the supplied candidate lists.
5. Never invent, rename, shorten, or combine taxonomy paths.
6. A book may belong to Fiction OR Nonfiction, never both.
7. Prefer specific supported paths over unnecessarily broad paths.
8. Do not infer attributes merely from the title.
9. Do not infer themes, geography, language, audience, relationships,
   setting, or other attributes unless directly supported by a filtered tag.
10. Agreement between models is useful evidence, but it does not override
    the source tags.
11. Prefer fewer strongly supported paths over speculative annotations.
12. If no candidate is adequately supported, return an empty list for
    that category.
13. Return JSON only.

Required format:
{{
  "genre_paths": [],
  "metadata_paths": []
}}
""".strip()


def resolve_debate(book, taxonomies, model=DEFAULT_RESOLVER_MODEL):
    tags = book.get("filtered_tags", [])

    candidates = retrieve_candidate_paths(
        tags,
        taxonomies,
    )

    prompt = build_debate_prompt(
        book,
        candidates,
    )

    raw = query_openrouter(
        prompt,
        model,
    )

    parsed = extract_json(raw)

    validated = validate_annotation(
        parsed,
        taxonomies,
        candidate_paths=candidates,
    )

    return {
        "model": model,
        "genre_paths": validated["genre_paths"],
        "metadata_paths": validated["metadata_paths"],
        "candidate_genre_paths": candidates["genre_paths"],
        "candidate_metadata_paths": candidates["metadata_paths"],
    }
