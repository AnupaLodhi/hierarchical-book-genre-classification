# Data Contract and JSON Flow

## Purpose

This document defines how data moves through the Hierarchical Book Genre Classification pipeline, from the original ISBN input to the final hierarchical Genre and Metadata annotation.

The ISBN-13 is used as the primary identifier for matching the same book across multiple data sources.

The pipeline preserves source provenance so that collected evidence can be traced back to Amazon, Goodreads, or Open Library.

---

# 1. Initial Input

The pipeline begins with a list of ISBN-13 identifiers.

**Input file:**

`input/isbns.csv`

Example:

```csv
Isbn-13
9780060269364
```

The ISBN-13 is used to search for the corresponding book across:

- Amazon
- Goodreads
- Open Library

Each source is collected independently before records are merged.

Missing information is preserved as missing rather than guessed or inferred.

---

# 2. Source-Level Book Records

Data collected from each source is normalized into a common structure.

A normalized source record follows a structure similar to:

```json
{
  "isbn13": "9780060269364",
  "title": "Book title",
  "authors": ["Author name"],
  "publisher": "Publisher",
  "country": null,
  "publication_place": null,
  "date_of_publication": null,
  "language": "English",
  "Genre": [
    "Fiction",
    "Short stories"
  ],
  "number_of_pages": null,
  "physical_format": null,
  "source_url": "source page URL",
  "sources": [
    "SourceName"
  ],
  "_cover_url": null,
  "_blurb": "Book description",
  "_reviews": []
}
```

The same normalized structure allows records from different websites to be processed consistently.

## Important Country Rule

`country` represents publication country.

The system must not infer publication country from:

- author nationality
- Amazon domain
- Goodreads locale
- language
- publisher name
- ISBN prefix

If publication country cannot be supported by the collected source data, it remains `null`.

---

# 3. Source-Specific Evidence Files

The pipeline preserves evidence collected for individual books.

Evidence directories include:

```text
data/book coverpage/
data/book blurb/
data/book reviews/
data/genre union/
```

These files allow later stages to trace information back to the original source.

The system therefore does not reduce all source information into one untraceable string.

---

# 4. Master Book Record

Records belonging to the same ISBN are merged into a master representation.

Primary master data:

```text
data/master_data.json
```

A master record conceptually contains:

```json
{
  "isbn13": "9780060269364",
  "available_sources": [
    "Open Library",
    "Goodreads",
    "Amazon"
  ],
  "source_count": 3,
  "cleaned_metadata": {},
  "genre_evidence": {},
  "text_evidence": {},
  "source_metadata": {}
}
```

The important components are:

### `cleaned_metadata`

Contains normalized bibliographic information selected from the collected source records.

### `genre_evidence`

Preserves genre/tag information together with its source.

### `text_evidence`

Contains textual evidence such as blurbs and reviews.

### `source_metadata`

Preserves normalized source-specific information rather than destroying provenance during merging.

---

# 5. Genre Union

Genre and category labels collected from all available sources are combined for each ISBN.

The union stage conceptually produces:

```json
{
  "isbn13": "9780060269364",
  "source_genres": {
    "amazon": [],
    "goodreads": [],
    "openlibrary": []
  },
  "merged_genres": []
}
```

The genre union is an evidence-collection stage.

It is **not** considered the final classification.

A label appearing on one source does not automatically become a final Genre or Metadata annotation.

---

# 6. Genre Filtering Agent Input

The Genre Filtering Agent receives source-derived candidate tags together with textual evidence.

Conceptually:

```json
{
  "isbn13": "9780060269364",
  "source_tags": [],
  "source_provenance": {},
  "blurb_evidence": [],
  "review_evidence": []
}
```

The purpose of this stage is to determine which source-provided tags are supported by the available evidence.

The filtering agent may:

- retain supported tags
- reject irrelevant tags
- reject noisy categories
- abstain when usable evidence is unavailable

The filtering agent must not invent arbitrary replacement labels.

---

# 7. Genre Filtering Output

Primary output:

```text
results/filtering/processed_book_genres.json
```

CSV representation:

```text
results/filtering/processed_book_genres.csv
```

A filtering result conceptually contains:

```json
{
  "isbn13": "9780060269364",
  "source_tags": [],
  "source_provenance": {},
  "raw_merged_tags": [],
  "final_valid_tags": [],
  "removed_tags": []
}
```

### `raw_merged_tags`

Contains source-derived tags before final evidence filtering.

### `final_valid_tags`

Contains tags retained after filtering.

### `removed_tags`

Records rejected tags and associated filtering information where available.

Books without usable candidate tags remain explicit no-filtered-tag cases.

They are not assigned fabricated annotations.

---

# 8. Controlled Genre Taxonomy

The controlled Genre hierarchy is stored in:

```text
taxonomy/genre_hierarchy.json
```

An example hierarchical Genre path is:

```text
Fiction / Literary Fiction / Short Form Literary Fiction / Short Fiction
```

Only valid paths from the controlled Genre taxonomy may be accepted as final Genre annotations.

---

# 9. Controlled Metadata Taxonomy

The controlled Metadata hierarchy is stored in:

```text
taxonomy/metadata_hierarchy.json
```

Metadata is maintained separately from Genre.

Metadata branches include contextual dimensions such as:

- audience
- geographical context
- language and textual context
- book format and form
- temporal context
- thematic metadata
- character and representation metadata
- narrative and stylistic metadata
- content suitability metadata
- series and publication metadata

An example Metadata path is:

```text
Audience / Age_Group / Young_Adult / Young Adult Audience
```

Separating Genre from Metadata prevents contextual properties from being incorrectly treated as literary genres.

---

# 10. Candidate Taxonomy Path Retrieval

The complete taxonomies contain many possible hierarchical paths.

Instead of sending every taxonomy path to every annotation request, the system retrieves paths relevant to the filtered evidence.

Conceptually:

```json
{
  "genre_paths": [
    "Fiction / Literary Fiction / Short Form Literary Fiction / Short Fiction"
  ],
  "metadata_paths": [
    "Audience / Age_Group / Young_Adult / Young Adult Audience"
  ]
}
```

Candidate paths are possible annotation choices.

**Candidate presence is not evidence.**

An annotator should select a path only when it is supported by the book evidence.

---

# 11. Multi-LLM Annotation Input

Each annotation configuration receives the same core book evidence and controlled candidate paths.

Conceptually:

```json
{
  "isbn13": "9780060269364",
  "filtered_tags": [],
  "genre_candidate_paths": [],
  "metadata_candidate_paths": [],
  "book_evidence": {}
}
```

The same controlled annotation task is independently presented to each configured annotator.

---

# 12. Annotation Configurations

The current full experiment uses:

```text
qwen_groq
→ qwen/qwen3.8-27b

gpt_oss_groq
→ openai/gpt-oss-120b

gpt_oss_20b
→ openai/gpt-oss-20b
```

These represent three annotation configurations.

However, they represent two model families:

```text
Qwen family
GPT-OSS family
```

This distinction must be preserved when reporting the methodology.

---

# 13. Required LLM Annotation Output

Each successful annotator must return a structured object containing:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

Example:

```json
{
  "genre_paths": [
    "Fiction / Literary Fiction / Short Form Literary Fiction / Short Fiction"
  ],
  "metadata_paths": [
    "Audience / Age_Group / Young_Adult / Young Adult Audience",
    "Language_and_Textual_Context / Language / Single_Language / English"
  ]
}
```

An explicit abstention is also valid:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

Empty arrays are therefore different from malformed output or provider failure.

---

# 14. Annotation Validation

LLM output is not accepted blindly.

The annotation pipeline checks:

1. whether the response contains valid JSON
2. whether required keys exist
3. whether `genre_paths` is a list
4. whether `metadata_paths` is a list
5. whether selected Genre paths exist in the Genre taxonomy
6. whether selected Metadata paths exist in the Metadata taxonomy
7. whether selected paths belong to the allowed candidate set
8. whether contradictory Fiction and Nonfiction assignments occur

Malformed or truncated responses are recorded as errors.

They are not silently converted into successful annotations.

---

# 15. Multi-LLM Annotation Checkpoint

The main annotation checkpoint is:

```text
results/annotations/multi_llm_annotations.json
```

Conceptually, a book contains independent annotation states:

```json
{
  "isbn13": "9780060269364",
  "annotations": {
    "qwen_groq": {
      "status": "success",
      "provider": "groq",
      "model": "qwen/qwen3.8-27b",
      "genre_paths": [],
      "metadata_paths": []
    },
    "gpt_oss_groq": {
      "status": "success",
      "provider": "groq",
      "model": "openai/gpt-oss-120b",
      "genre_paths": [],
      "metadata_paths": []
    },
    "gpt_oss_20b": {
      "status": "success",
      "provider": "groq",
      "model": "openai/gpt-oss-20b",
      "genre_paths": [],
      "metadata_paths": []
    }
  }
}
```

Checkpointing allows successful annotations to be preserved while failed API calls can be retried later.

---

# 16. Annotation Status Semantics

Different annotation states must not be mixed.

### Successful annotation

The model returned valid structured output that passed validation.

### Valid abstention

The model successfully returned:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

### No filtered tags

The upstream filtering stage did not provide usable evidence for annotation.

### API/provider error

The annotation request could not be completed because of infrastructure or provider failure.

### Invalid model output

The model returned malformed, incomplete, or invalid structured output.

These states have different meanings and must remain distinguishable in the dataset.

---

# 17. Inter-Annotator Input

Only successful annotations are used when measuring model agreement.

For one book, the comparison conceptually looks like:

```json
{
  "isbn13": "9780060269364",
  "successful_annotations": {
    "qwen_groq": {
      "genre_paths": [],
      "metadata_paths": []
    },
    "gpt_oss_groq": {
      "genre_paths": [],
      "metadata_paths": []
    },
    "gpt_oss_20b": {
      "genre_paths": [],
      "metadata_paths": []
    }
  }
}
```

API failures are excluded from disagreement calculations.

A provider failure does not mean that a model disagreed with another model.

---

# 18. Inter-Annotator Agreement Outputs

The project evaluates agreement using multiple views.

These include:

- exact Genre agreement
- exact Metadata agreement
- exact combined agreement
- pairwise exact agreement
- Genre Jaccard similarity
- Metadata Jaccard similarity
- shared hierarchical paths
- disputed hierarchical paths
- model-specific paths
- hierarchy-aware ancestor/descendant relationships

Availability is recorded separately from agreement.

For example:

```text
3 successful annotators
→ 3-model comparison

2 successful annotators
→ 2-model comparison

1 successful annotator
→ insufficient for inter-annotator agreement

API failure
→ availability failure, not disagreement
```

Agreement between two available models is reported as **2-of-2**, not 2-of-3.

---

# 19. Path-Level Agreement Representation

Exact annotation sets can differ even when models agree on part of the hierarchy.

Therefore the pipeline also produces path-level analysis.

Conceptually:

```json
{
  "shared_genre_paths": [],
  "shared_metadata_paths": [],
  "disputed_genre_paths": [],
  "disputed_metadata_paths": [],
  "model_only_paths": {}
}
```

### Shared paths

Paths selected by all successful annotators for that book.

### Disputed paths

Paths appearing in the union of annotations but not shared by all successful annotators.

### Model-only paths

Paths uniquely selected by an individual annotator.

This representation prevents partial semantic agreement from being hidden by a simple exact-match metric.

---

# 20. Hierarchy-Aware Comparison

Two annotations may not be exactly equal but may have a parent-child relationship in the taxonomy.

For example:

```text
Fiction / Thriller
```

and:

```text
Fiction / Thriller / Political Thriller
```

are not exact matches.

However, they are hierarchically related.

The pipeline records ancestor/descendant relationships separately.

Hierarchy proximity is **not** counted as exact agreement.

---

# 21. Consensus Representation

Successful annotations are routed according to their agreement.

Possible states include:

```text
perfect_3_of_3
agreement_2_of_3
agreement_2_of_2
conflict
no_filtered_tags
insufficient_successful_annotations
```

The exact stored terminology is determined by the consensus-generation scripts.

The important methodological rule is that model availability and model agreement remain separate concepts.

---

# 22. Conflict Representation

A conflict record retains information needed for later adjudication.

Conceptually:

```json
{
  "isbn13": "...",
  "available_models": [],
  "available_count": 3,
  "shared_genre_paths": [],
  "shared_metadata_paths": [],
  "disputed_genre_paths": [],
  "disputed_metadata_paths": [],
  "model_only_paths": {},
  "original_annotations": {}
}
```

The original annotations are preserved rather than replaced when conflict is detected.

---

# 23. Debate Input

Cases with genuine disagreement and sufficient successful annotations are routed to the debate/adjudication stage.

Conceptually:

```json
{
  "isbn13": "...",
  "filtered_tags": [],
  "shared_genre_paths": [],
  "shared_metadata_paths": [],
  "disputed_genre_paths": [],
  "disputed_metadata_paths": [],
  "model_only_paths": {},
  "original_annotations": {}
}
```

The adjudicator therefore receives both the disagreement structure and the original book evidence.

---

# 24. Debate Resolution

The debate resolver acts as an adjudicator.

It is **not** counted as a fourth independent annotator.

Its final structured output again uses:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

The resolver may preserve supported shared paths, accept supported disputed paths, or reject unsupported disputed paths.

The complete resolved annotation must still pass taxonomy validation.

---

# 25. Final Dataset

The final dataset combines successfully resolved routes such as:

- perfect consensus
- valid partial consensus
- debate-resolved conflicts

Conceptually:

```json
{
  "isbn13": "...",
  "genre_paths": [],
  "metadata_paths": [],
  "resolution_method": "..."
}
```

Cases that cannot be resolved safely can be separated for manual review.

---

# 26. Final Integrity Audit

The final output is checked for structural and taxonomy integrity.

The audit checks for issues including:

- duplicate ISBNs
- invalid Genre paths
- invalid Metadata paths
- empty resolved annotations
- contradictory Fiction/Nonfiction assignments
- overlap between resolved and manual-review records

A successful audit validates structural consistency.

It does not by itself prove semantic ground-truth accuracy.

---

# 27. Complete JSON/Data Flow

```text
input/isbns.csv
        |
        v
+-------------------------------+
| Multi-Source Data Collection  |
| Amazon                        |
| Goodreads                     |
| Open Library                  |
+-------------------------------+
        |
        v
Source-Level Records
        |
        v
data/master_data.json
        |
        +----------------------+
        |                      |
        v                      v
Genre Evidence             Text Evidence
        |                 Blurbs / Reviews
        +----------+-----------+
                   |
                   v
          Genre Filtering Agent
                   |
                   v
results/filtering/processed_book_genres.json
                   |
                   |
        +----------+----------+
        |                     |
        v                     v
Genre Hierarchy       Metadata Hierarchy
        |                     |
        +----------+----------+
                   |
                   v
          Candidate Retrieval
                   |
                   v
       +-----------------------+
       | Multi-LLM Annotation  |
       +-----------------------+
          /        |        \
         /         |         \
        v          v          v
     Qwen       GPT-OSS    GPT-OSS
      27B        120B        20B
        \          |          /
         \         |         /
          +--------+--------+
                   |
                   v
       Inter-Annotator Analysis
                   |
          +--------+--------+
          |                 |
          v                 v
      Consensus          Conflict
          |                 |
          |                 v
          |        Debate Adjudication
          |                 |
          +--------+--------+
                   |
                   v
            Final Dataset
                   |
                   v
             Integrity Audit
```

---

# 28. Core Research Data Rule

The pipeline maintains a distinction between:

```text
Missing evidence
≠ Model abstention
≠ Model disagreement
≠ Invalid model output
≠ API/provider failure
≠ Successful annotation
```

These states must not be collapsed into one category.

This distinction is necessary for meaningful inter-annotator analysis and for preventing infrastructure failures from being incorrectly interpreted as semantic disagreement between models.