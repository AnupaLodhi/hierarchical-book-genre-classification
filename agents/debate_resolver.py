import json

from agents.annotation_agent import (
    retrieve_candidate_paths,
    validate_annotation,
)
from agents.llm_providers import query_model
from scripts.run_annotations import parse_annotation_json_strict

DEFAULT_RESOLVER = {
    "provider": "groq",
    "model": "openai/gpt-oss-120b",
    "max_tokens": 700,
}


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

PATH-LEVEL AGREEMENT ANALYSIS

SHARED GENRE PATHS
{json.dumps(book.get("shared_genre_paths", []), indent=2, ensure_ascii=False)}

SHARED METADATA PATHS
{json.dumps(book.get("shared_metadata_paths", []), indent=2, ensure_ascii=False)}

DISPUTED GENRE PATHS
{json.dumps(book.get("disputed_genre_paths", []), indent=2, ensure_ascii=False)}

DISPUTED METADATA PATHS
{json.dumps(book.get("disputed_metadata_paths", []), indent=2, ensure_ascii=False)}

MODEL-SPECIFIC PATHS
{json.dumps(book.get("model_only_paths", {}), indent=2, ensure_ascii=False)}

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
10. Shared paths represent agreement among the available original
    annotators, but they are not automatically ground truth. Preserve a
    shared path only when it is supported by the filtered source evidence.
11. Disputed paths are the primary adjudication targets. Evaluate each
    disputed path independently against the filtered source evidence.
12. Do not reject a supported shared path merely because other paths are
    disputed, and do not accept a disputed path merely because one model
    proposed it.
13. Return the COMPLETE final annotation, including every supported shared
    or disputed path that should remain after adjudication.
14. Prefer fewer strongly supported paths over speculative annotations.
15. If no candidate is adequately supported, return an empty list for
    that category.
16. Geographical Context means the geographical SETTING or place of the
    story/content. Do NOT infer it from author nationality, publication
    country, publisher, ISBN origin, language, or labels such as
    "American Short stories" or "English Short stories" unless the
    filtered evidence explicitly describes the story/content setting.
17. Role_Profile refers specifically to roles of characters in the story.
18. Group_Profile refers specifically to groups of characters represented
    in the text.
19. Temporal metadata must be supported by explicit temporal evidence.
    Do not infer a historical era merely because a genre annotation is
    Historical Fiction.
20. Return JSON only.

Required format:
{{
  "genre_paths": [],
  "metadata_paths": []
}}
""".strip()


def resolve_debate(
    book,
    taxonomies,
    resolver=None,
):
    config = resolver or DEFAULT_RESOLVER

    tags = book.get("filtered_tags", [])

    candidates = retrieve_candidate_paths(
        tags,
        taxonomies,
    )

    prompt = build_debate_prompt(
        book,
        candidates,
    )

    raw = query_model(
        prompt,
        provider=config["provider"],
        model=config["model"],
        max_tokens=config.get("max_tokens", 700),
    )

    parsed = parse_annotation_json_strict(raw)

    validated = validate_annotation(
        parsed,
        taxonomies,
        candidate_paths=candidates,
    )

    return {
        "provider": config["provider"],
        "model": config["model"],
        "genre_paths": validated["genre_paths"],
        "metadata_paths": validated["metadata_paths"],
        "candidate_genre_paths": candidates["genre_paths"],
        "candidate_metadata_paths": candidates["metadata_paths"],
    }
