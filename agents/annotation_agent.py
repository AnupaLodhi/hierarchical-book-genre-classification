import json
from pathlib import Path


GENRE_TAXONOMY = Path("taxonomy/genre_hierarchy.json")
METADATA_TAXONOMY = Path("taxonomy/metadata_hierarchy.json")


def build_paths(tree, prefix=None):
    """Convert nested taxonomy JSON into valid slash-separated paths."""

    prefix = prefix or []
    paths = []

    if isinstance(tree, dict):
        for name, children in tree.items():
            current = prefix + [name]
            paths.append(" / ".join(current))
            paths.extend(build_paths(children, current))

    elif isinstance(tree, list):
        for name in tree:
            current = prefix + [str(name)]
            paths.append(" / ".join(current))

    return paths


def load_taxonomies():
    genre = json.loads(
        GENRE_TAXONOMY.read_text(encoding="utf-8")
    )

    metadata = json.loads(
        METADATA_TAXONOMY.read_text(encoding="utf-8")
    )

    genre_paths = build_paths(genre)

    metadata_paths_all = build_paths(metadata)

    # Agent output should omit the metadata root.
    metadata_paths = []

    root = "Book_Metadata_Hierarchy"

    for path in metadata_paths_all:
        if path == root:
            continue

        prefix = root + " / "

        if path.startswith(prefix):
            path = path[len(prefix):]

        metadata_paths.append(path)

    return {
        "genre_tree": genre,
        "metadata_tree": metadata,
        "genre_paths": genre_paths,
        "metadata_paths": metadata_paths,
    }


def validate_annotation(result, taxonomies, candidate_paths=None):
    """Reject invented taxonomy paths and invalid root combinations."""

    if not isinstance(result, dict):
        raise ValueError("Annotation must be a JSON object")

    valid_genres = set(taxonomies["genre_paths"])
    valid_metadata = set(taxonomies["metadata_paths"])

    genres = result.get("genre_paths") or []
    metadata = result.get("metadata_paths") or []

    if not isinstance(genres, list):
        raise ValueError("genre_paths must be a list")

    if not isinstance(metadata, list):
        raise ValueError("metadata_paths must be a list")

    genres = list(dict.fromkeys(
        x.strip()
        for x in genres
        if isinstance(x, str) and x.strip()
    ))

    metadata = list(dict.fromkeys(
        x.strip()
        for x in metadata
        if isinstance(x, str) and x.strip()
    ))

    invalid_genres = [
        x for x in genres
        if x not in valid_genres
    ]

    invalid_metadata = [
        x for x in metadata
        if x not in valid_metadata
    ]

    if invalid_genres:
        raise ValueError(
            f"Invalid genre paths: {invalid_genres}"
        )

    if invalid_metadata:
        raise ValueError(
            f"Invalid metadata paths: {invalid_metadata}"
        )

    # The model may select only paths that were actually
    # supplied to it during candidate retrieval.
    if candidate_paths is not None:
        allowed_genres = set(
            candidate_paths["genre_paths"]
        )
        allowed_metadata = set(
            candidate_paths["metadata_paths"]
        )

        outside_genres = [
            x for x in genres
            if x not in allowed_genres
        ]

        outside_metadata = [
            x for x in metadata
            if x not in allowed_metadata
        ]

        if outside_genres:
            raise ValueError(
                f"Genre paths outside candidate set: "
                f"{outside_genres}"
            )

        if outside_metadata:
            raise ValueError(
                f"Metadata paths outside candidate set: "
                f"{outside_metadata}"
            )

    roots = set()

    for path in genres:
        if path == "Fiction" or path.startswith("Fiction /"):
            roots.add("Fiction")

        if path == "Nonfiction" or path.startswith("Nonfiction /"):
            roots.add("Nonfiction")

    if len(roots) > 1:
        raise ValueError(
            "Book cannot be both Fiction and Nonfiction"
        )

    return {
        "genre_paths": genres,
        "metadata_paths": metadata,
    }


def build_annotation_prompt(
    book,
    filtered_tags,
    genre_paths,
    metadata_paths,
):
    """Build closed-taxonomy annotation prompt."""

    title = str(book.get("title", "")).strip()

    return f"""
You are a hierarchical book taxonomy annotation agent.

BOOK
ISBN: {book.get("isbn13", "")}
Title: {title}

FILTERED SOURCE TAGS
{json.dumps(filtered_tags, ensure_ascii=False, indent=2)}

TASK

Map the supplied filtered tags to the most appropriate paths from
the controlled taxonomies below.

This is taxonomy annotation, NOT free-form classification.

STRICT RULES

1. Use ONLY paths appearing exactly in the supplied taxonomies.
2. Never invent, rename, shorten, combine, or modify a taxonomy path.
3. A book must belong to either Fiction OR Nonfiction, never both.
4. Select the most specific supported genre paths.
5. Do not select a specific path merely because it sounds plausible.
6. Metadata such as audience, format, language, geographic/cultural
   context, time period, style, or similar attributes belongs in
   metadata_paths, not genre_paths.
7. Genre concepts belong in genre_paths, not metadata_paths.
8. The metadata root "Book_Metadata_Hierarchy" must NOT appear.
9. Multiple paths are allowed when independently supported.
10. Do not force an annotation when evidence is insufficient.
11. Use ONLY the supplied filtered tags as evidence.
12. Candidate taxonomy paths are OPTIONS, not evidence.
13. Every selected path must be directly supported by at least one supplied filtered tag.
14. Do NOT infer themes, relationships, protagonist traits, geography, language, audience, setting, or other attributes merely because a candidate path is available.
15. Do NOT infer information from the title alone.
16. Prefer fewer strongly supported paths over many speculative paths.
17. Geographical Context means the geographical SETTING or place of the story/content.
    Do NOT infer geographical context from author nationality, publication country,
    publisher, ISBN origin, language, or labels such as "American Short stories"
    or "English Short stories" unless the supplied evidence explicitly describes
    the story/content setting.
18. Role_Profile refers specifically to roles of characters in the story.
19. Group_Profile refers specifically to groups of characters represented in the text.
20. Temporal metadata must be supported by explicit temporal evidence. Do not infer
    a historical era merely because the book belongs to Historical Fiction.
21. Return ONLY valid JSON. No markdown and no explanation outside JSON.

VALID GENRE PATHS
{json.dumps(genre_paths, ensure_ascii=False)}

VALID METADATA PATHS
{json.dumps(metadata_paths, ensure_ascii=False)}

RETURN EXACTLY

{{
  "genre_paths": [
    "exact taxonomy path"
  ],
  "metadata_paths": [
    "exact taxonomy path"
  ]
}}
""".strip()


import re
from difflib import SequenceMatcher


def _tokens(text):
    return set(
        re.findall(
            r"[a-z0-9]+",
            str(text).casefold(),
        )
    )


def _path_score(path, tags):
    """
    Score taxonomy paths using specific concept words.

    Generic taxonomy words such as fiction, nonfiction,
    book, story, form, audience, etc. cannot by themselves
    justify a descendant path.
    """
    parts = [
        x.strip()
        for x in str(path).split("/")
        if x.strip()
    ]

    leaf = parts[-1] if parts else str(path)

    # Exact source-tag -> taxonomy-label match is always valid.
    for tag in tags:
        if str(tag).strip().casefold() == leaf.casefold():
            return 1.0

    stopwords = {
        "fiction",
        "nonfiction",
        "book",
        "books",
        "story",
        "stories",
        "form",
        "general",
        "context",
        "metadata",
        "audience",
        "textual",
        "narrative",
        "thematic",
    }

    leaf_tokens = _tokens(leaf) - stopwords

    if not leaf_tokens:
        return 0.0

    best = 0.0

    for tag in tags:
        tag_tokens = _tokens(tag) - stopwords

        if not tag_tokens:
            continue

        overlap = len(
            leaf_tokens & tag_tokens
        )

        if overlap == 0:
            continue

        precision = overlap / len(leaf_tokens)
        recall = overlap / len(tag_tokens)

        token_score = (
            2 * precision * recall
            / max(precision + recall, 1e-9)
        )

        best = max(best, token_score)

    return best


def retrieve_candidate_paths(
    filtered_tags,
    taxonomies,
    genre_limit=80,
    metadata_limit=60,
):
    """
    Retrieve likely taxonomy paths without modifying
    or inventing taxonomy labels.
    """

    genre_paths = taxonomies["genre_paths"]
    metadata_paths = taxonomies["metadata_paths"]

    genre_scored = sorted(
        (
            (_path_score(path, filtered_tags), path)
            for path in genre_paths
        ),
        reverse=True,
    )

    metadata_scored = sorted(
        (
            (_path_score(path, filtered_tags), path)
            for path in metadata_paths
        ),
        reverse=True,
    )

    # Require substantial lexical support.
    # Weak one-word coincidences must not become LLM options.
    MIN_SCORE = 0.48

    genres = [
        path
        for score, path in genre_scored
        if score >= MIN_SCORE
    ][:genre_limit]

    metadata = [
        path
        for score, path in metadata_scored
        if score >= MIN_SCORE
    ][:metadata_limit]

    # Expose top-level roots only when supported by filtered evidence.
    tag_tokens = set()
    for tag in filtered_tags:
        tag_tokens.update(_tokens(tag))

    root_evidence = []

    if "fiction" in tag_tokens:
        root_evidence.append("Fiction")

    if "nonfiction" in tag_tokens or (
        "non" in tag_tokens and "fiction" in tag_tokens
    ):
        root_evidence.append("Nonfiction")

    # If lexical evidence cannot determine the root, retain both roots
    # so the annotation agent is not forced into an unsupported class.
    if not root_evidence:
        root_evidence = ["Fiction", "Nonfiction"]

    for root in ("Fiction", "Nonfiction"):
        if root not in root_evidence:
            genres = [
                path for path in genres
                if path != root
                and not path.startswith(root + " /")
            ]

    for root in root_evidence:
        if root not in genres:
            genres.append(root)

    return {
        "genre_paths": genres,
        "metadata_paths": metadata,
    }
