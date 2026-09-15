# Hierarchical Book Genre Classification

A research-oriented pipeline for hierarchical book genre classification using multi-source bibliographic metadata, textual evidence, hierarchical taxonomies, and multi-LLM consensus.

The project integrates book information from **Open Library, Goodreads, and Amazon** using a common ISBN set while preserving source-level provenance.

## Research Objective

Genre information across book platforms is often incomplete, inconsistent, noisy, or represented at different levels of specificity.

This project investigates a pipeline that:

1. Collects metadata from multiple independent sources.
2. Preserves source-specific metadata and genre evidence.
3. Constructs a canonical book-level dataset.
4. Filters noisy genre/category labels.
5. Maps books to a hierarchical genre taxonomy.
6. Uses multiple LLM annotators for classification.
7. Detects agreement and disagreement.
8. Resolves conflicting predictions through a debate stage.
9. Sends unresolved cases for manual review.

## Current Dataset

The current experiment contains **400 unique ISBN-13 records**.

| Source | Books |
|---|---:|
| Open Library | 400 |
| Goodreads | 395 |
| Amazon | 305 |

Source overlap:

- 301 books have all three sources.
- 98 books have two sources.
- 1 book has one source.

Evidence coverage includes:

- Open Library genre evidence: 394 books
- Goodreads genre evidence: 217 books
- Amazon genre evidence: 269 books
- At least one blurb: 389 books
- Review evidence: 96 books

## Pipeline

```text
400 ISBNs
    |
    v
+-----------------------------+
|      Metadata Collection    |
| Open Library | GR | Amazon  |
+-----------------------------+
              |
              v
       Master Dataset
              |
              v
      Clean Master Data
              |
              v
     Genre Filtering Agent
              |
              v
     Multi-LLM Annotation
              |
              v
        Consensus Check
          /         \
         v           v
 Perfect Consensus  Conflicts
                       |
                       v
                Debate Resolver
                   /       \
                  v         v
              Resolved    Manual
               Accepts     Review
                  \         /
                   \       /
                      v
          Final Hierarchical Dataset

---

## Repository Structure

```text
hierarchical-book-genre-classification/
├── agents/
├── data/
│   └── README.md
├── input/
│   ├── isbns.csv
│   └── isbns_400.csv
├── llms/
├── outputs/
├── scrapers/
│   ├── openlibrary.py
│   ├── goodreads.py
│   └── amazon.py
├── scripts/
│   ├── build_master_data.py
│   └── build_clean_master.py
├── taxonomy/
│   └── README.md
├── .gitignore
├── requirements.txt
└── README.md


## Metadata and Provenance

Raw metadata from Open Library, Goodreads, and Amazon is preserved independently.

Canonical bibliographic metadata generally follows this priority:

Open Library -> Goodreads -> Amazon

Raw source values remain preserved separately so canonical selection does not destroy provenance.

### Country Policy

`country` represents publication country.

It is not inferred from author nationality, Amazon storefront, language, publisher identity, ISBN prefix, or website locale.

Country is retained only when supported by explicit bibliographic publication-place evidence. Unknown or ambiguous values remain missing.


## Genre Evidence

Genre and category labels collected from each source are preserved as source-specific evidence rather than treated as final classifications.

Examples of useful evidence may include Fiction, Science Fiction, Romance, Horror, or Historical Fiction. Source categories may also contain non-genre information such as formats, imprints, franchises, or storefront categories.

The downstream genre-filtering stage is responsible for cleaning this evidence before hierarchical classification.

## Textual Evidence

Where available, the local research dataset preserves book descriptions and genuine review text as additional classification evidence.

Current coverage:

- 389 books contain at least one blurb.
- 96 books contain review evidence.

Raw source-derived textual datasets are excluded from the public repository.

## Local Generated Data

The pipeline generates the following files locally:

- `data/openlibrary_metadata.json`
- `data/goodreads_metadata.json`
- `data/amazon_metadata.json`
- source-specific failure logs
- `data/master_data.json`
- `data/clean_master_data.csv`

`master_data.json` preserves full source provenance and evidence.

`clean_master_data.csv` provides the flattened representation used by downstream experiments.

These generated datasets are not committed to the public repository.

## Installation

Create and activate a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies:

    pip install -r requirements.txt

## Running the Data Pipeline

Run the three source collectors:

    python scrapers/openlibrary.py
    python scrapers/goodreads.py
    python scrapers/amazon.py

Build the provenance-preserving master dataset:

    python scripts/build_master_data.py

Build the flattened agent-ready dataset:

    python scripts/build_clean_master.py

## Taxonomies

Genre classification and metadata organization are intentionally maintained as separate taxonomies.

Planned taxonomy files:

- `taxonomy/genre_hierarchy.json`
- `taxonomy/metadata_hierarchy.json`

The genre hierarchy defines the valid hierarchical genre classification space.

The metadata hierarchy represents non-genre book characteristics without mixing them into genre labels.

## Classification and Resolution Pipeline

The next stages of the research pipeline are:

1. Genre evidence filtering
2. Hierarchical candidate generation
3. Multi-LLM book annotation
4. Consensus detection
5. Conflict detection
6. Debate-based conflict resolution
7. Manual review of unresolved cases
8. Final hierarchical classification dataset

Planned result artifacts include:

- `outputs/full_output.csv`
- `outputs/perfect_consensus.csv`
- `outputs/conflicting_genres.csv`
- `outputs/resolved_accepts.csv`
- `outputs/manual_review.csv`

## Project Status

### Completed

- [x] ISBN input preparation
- [x] Open Library metadata collection
- [x] Goodreads metadata collection
- [x] Amazon metadata collection
- [x] source-level provenance preservation
- [x] master dataset construction
- [x] clean dataset construction
- [x] data integrity audit
- [x] country provenance validation

### In Progress

- [ ] genre hierarchy
- [ ] metadata hierarchy
- [ ] genre-filtering agent
- [ ] multi-LLM annotation
- [ ] consensus and conflict analysis
- [ ] debate resolver
- [ ] manual-review pipeline
- [ ] final hierarchical genre dataset

## Reproducibility

The pipeline deliberately separates raw source evidence, canonical metadata, taxonomy definitions, model annotations, consensus decisions, and conflict-resolution decisions.

This design allows individual stages to be audited without silently modifying the original source evidence.

## Research Use

This repository is intended for research and educational experimentation in hierarchical classification, multi-source metadata integration, and LLM-assisted annotation.

Users should respect applicable source terms and rights when collecting or using externally derived content.
