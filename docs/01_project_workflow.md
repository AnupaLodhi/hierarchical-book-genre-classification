# Project Workflow

## Hierarchical Book Genre Classification

This project constructs a hierarchical Genre and Metadata dataset for books by combining evidence from Amazon, Goodreads, and Open Library.

## Pipeline

ISBN Input
→ Multi-source Metadata Collection
→ Master Book Record
→ Genre Union and Text Evidence
→ Genre Filtering Agent
→ Candidate Taxonomy Path Retrieval
→ Multi-LLM Annotation
→ Inter-Annotator Agreement Analysis
→ Consensus / Conflict Detection
→ Debate Adjudication
→ Final Hierarchical Dataset
→ Integrity Audit

## 1. Multi-Source Data Collection

Each ISBN is searched across three sources:

- Amazon
- Goodreads
- Open Library

Source-specific information is preserved instead of treating one source as ground truth.

Collected information may include:

- ISBN
- title
- authors
- publisher
- publication country/place
- publication date
- language
- genres/tags
- page count
- physical format
- blurb
- reviews
- cover image
- source URL

Publication country is not inferred from author nationality, website domain, language, publisher, or ISBN prefix.

## 2. Master Book Record

Records belonging to the same ISBN are merged into a master representation.

The master record preserves:

- cleaned metadata
- source availability
- source-specific genre evidence
- source-specific text evidence
- source-specific metadata

This preserves provenance for later stages.

## 3. Genre Union

Genre labels from available sources are combined while retaining their source provenance.

The union is evidence collection, not the final classification.

## 4. Genre Filtering Agent

The filtering agent evaluates source-provided tags against available textual evidence such as blurbs and reviews.

The agent may retain or reject source tags but must not invent unsupported new tags.

Books without usable genre evidence are explicitly represented as no-filtered-tags cases instead of receiving forced annotations.

## 5. Controlled Hierarchies

Two controlled taxonomies are used:

- taxonomy/genre_hierarchy.json
- taxonomy/metadata_hierarchy.json

Genre and Metadata are kept separate.

Genre represents literary/content classification.

Metadata represents contextual properties such as audience, geography, temporal context, textual form, themes, representation, narrative characteristics, content suitability, and publication context.

## 6. Candidate Path Retrieval

Relevant Genre and Metadata taxonomy paths are retrieved from the controlled hierarchies using the filtered evidence.

Candidate paths are possible annotation choices. Their presence is not itself evidence that they apply to the book.

## 7. Multi-LLM Annotation

The current experiment uses three annotation configurations:

- Qwen 3.8 27B
- GPT-OSS 120B
- GPT-OSS 20B

Each annotator independently receives the book evidence and candidate taxonomy paths.

Outputs are validated against the controlled taxonomies.

Invalid JSON, nonexistent taxonomy paths, invalid candidate selections, contradictory Fiction/Nonfiction assignments, and malformed responses are rejected.

## 8. Agreement Analysis

Successful annotations are compared using:

- exact Genre agreement
- exact Metadata agreement
- exact combined agreement
- pairwise agreement
- Jaccard similarity
- path-level shared and disputed annotations
- hierarchy-aware ancestor/descendant relationships

Provider/API failures are treated as availability failures, not model disagreement.

## 9. Consensus and Conflict Routing

Exact consensus and partial consensus are recorded separately.

Agreement among two available successful annotators is reported as 2-of-2, not 2-of-3.

Cases with genuine disagreement and sufficient successful annotations are routed to the debate stage.

## 10. Debate Adjudication

The debate resolver examines:

- original model annotations
- shared paths
- disputed paths
- model-specific paths
- filtered book evidence
- controlled taxonomy candidates

The resolver acts as an adjudicator for disputed cases. It is not counted as an additional independent annotator.

## 11. Final Dataset

The final dataset combines:

- perfect consensus
- valid partial consensus
- debate-resolved conflicts

Cases that cannot be safely resolved remain eligible for manual review rather than receiving fabricated labels.

## 12. Integrity Audit

The final output is checked for:

- duplicate ISBNs
- invalid Genre paths
- invalid Metadata paths
- empty resolved annotations
- Fiction/Nonfiction contradictions
- overlap between resolved and manual-review records

## Current Experiment Status

The full experiment contains 400 books.

Genre filtering is complete.

The full multi-LLM annotation run is still in progress because of external API quota limits. Final 400-book agreement, consensus, debate, and final-dataset statistics must not be reported until annotation is complete.

The previously completed 25-book run is a pipeline validation experiment and must not be presented as the final 400-book result.
