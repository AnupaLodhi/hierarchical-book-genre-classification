# Hierarchical Book Genre Classification

A research pipeline for **multi-source, evidence-grounded, hierarchical book Genre and Metadata annotation** using controlled taxonomies, multiple LLM annotators, inter-annotator agreement analysis, consensus detection, and debate-based conflict adjudication.

The system integrates evidence from **Open Library, Goodreads, and Amazon** using ISBN-13 as the common book identifier while preserving source-level provenance throughout the pipeline.

---

## Research Objective

Book classification across online platforms is difficult because source labels are often:

- incomplete
- inconsistent
- noisy
- overly broad or overly specific
- mixed with audience or Metadata labels
- represented at different hierarchical levels

This project investigates whether a controlled multi-agent pipeline can transform heterogeneous source evidence into a structurally valid hierarchical book dataset.

The core research workflow is:

```text
Multi-Source Evidence
        ↓
Evidence Integration
        ↓
Genre Filtering
        ↓
Controlled Taxonomy Retrieval
        ↓
Independent Multi-LLM Annotation
        ↓
Inter-Annotator Agreement
        ↓
Consensus / Conflict Detection
        ↓
Debate Adjudication
        ↓
Final Hierarchical Dataset
```

---

# System Architecture

```text
                     ISBN-13 Input
                          |
                          v
        +-----------------------------------+
        |     Multi-Source Collection       |
        |                                   |
        | Amazon | Goodreads | Open Library |
        +-----------------------------------+
                          |
                          v
                 Master Book Records
                          |
             +------------+------------+
             |                         |
             v                         v
       Genre Evidence            Text Evidence
                                Blurbs / Reviews
             |                         |
             +------------+------------+
                          |
                          v
                Genre Filtering Agent
                          |
                          v
                  Filtered Evidence
                          |
            +-------------+-------------+
            |                           |
            v                           v
     Genre Hierarchy            Metadata Hierarchy
            |                           |
            +-------------+-------------+
                          |
                          v
                 Candidate Retrieval
                          |
                          v
             +--------------------------+
             |   Independent Annotation |
             +--------------------------+
                /          |          \
               v           v           v
          Qwen 27B    GPT-OSS 120B  GPT-OSS 20B
               \           |           /
                \          |          /
                 +---------+---------+
                           |
                           v
              Inter-Annotator Analysis
                           |
                 +---------+---------+
                 |                   |
                 v                   v
              Consensus           Conflict
                 |                   |
                 |                   v
                 |            Debate Adjudicator
                 |                   |
                 +---------+---------+
                           |
                           v
                Final Hierarchical Dataset
                           |
                           v
                    Integrity Audit
```

---

# Dataset

The current main experiment contains:

```text
400 unique ISBN-13 records
```

## Source Coverage

| Source | Successful Books |
|---|---:|
| Open Library | 400 / 400 |
| Goodreads | 395 / 400 |
| Amazon | 305 / 400 |

Source availability:

```text
301 books → all three sources
 98 books → two sources
  1 book  → one source
  0 books → missing from every source
```

## Evidence Coverage

```text
Open Library genre evidence: 394 books
Goodreads genre evidence:    217 books
Amazon genre evidence:       269 books

Books with blurbs:           389
Books with review evidence:   96
```

Missing information is preserved as missing rather than guessed.

---

# Multi-Source Evidence Integration

ISBN-13 is used as the primary identifier for matching books across:

```text
Amazon
Goodreads
Open Library
```

Source records are normalized before integration.

The master dataset preserves:

- bibliographic Metadata
- source availability
- source-specific genre labels
- textual evidence
- source provenance
- original normalized source records

Primary local outputs include:

```text
data/master_data.json
data/clean_master_data.csv
```

Source evidence is preserved rather than destroyed during merging.

---

# Publication Country Policy

`country` represents **publication country**.

It is not inferred from:

- author nationality
- Amazon domain
- Goodreads locale
- language
- publisher identity alone
- ISBN prefix

When explicit publication-place evidence is unavailable or ambiguous, the value remains missing.

This prevents unrelated geographical concepts from being conflated.

---

# Genre Union

Genre/category evidence from all available sources is collected for each ISBN.

Source provenance is retained so that a label can be traced back to its originating source.

Genre union files are stored locally under:

```text
data/genre union/
```

The union represents source evidence.

It is **not** treated as the final Genre classification.

---

# Genre Filtering Agent

Source categories can contain both useful and noisy information.

The Genre Filtering Agent evaluates source-derived tags against available textual evidence.

It can:

```text
retain supported tags
remove unsupported/noisy tags
preserve source provenance
abstain when usable candidates are unavailable
```

It does not invent arbitrary replacement tags.

Primary output:

```text
results/filtering/processed_book_genres.json
results/filtering/processed_book_genres.csv
```

## Filtering Results

For the complete 400-book experiment:

```text
Total books:             400
Successful filtering:    397
No candidate evidence:     3
Filtering errors:           0
Hallucinated new tags:      0
```

The filtering stage is complete.

---

# Controlled Taxonomies

Genre and Metadata are deliberately maintained as separate hierarchical spaces.

## Genre Taxonomy

```text
taxonomy/genre_hierarchy.json
```

Approximately:

```text
661 hierarchical Genre paths
```

## Metadata Taxonomy

```text
taxonomy/metadata_hierarchy.json
```

Approximately:

```text
466 hierarchical Metadata paths
```

Metadata dimensions include:

- Audience
- Geographical Context
- Language and Textual Context
- Book Format and Form
- Temporal Context
- Thematic Metadata
- Character and Representation Metadata
- Narrative and Stylistic Metadata
- Content Suitability Metadata
- Series and Publication Metadata

Only valid controlled taxonomy paths can enter accepted annotations.

---

# Candidate Retrieval

The complete Genre and Metadata hierarchies contain many possible paths.

For each book, relevant candidate paths are retrieved from the taxonomies using filtered evidence.

Conceptually:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

Candidate paths represent **possible classification choices**.

Their presence does not constitute evidence that the book belongs to those paths.

---

# Multi-LLM Annotation

Three annotation configurations are used:

| Configuration | Provider | Model | Family |
|---|---|---|---|
| `qwen_groq` | Groq | `qwen/qwen3.8-27b` | Qwen |
| `gpt_oss_groq` | Groq | `openai/gpt-oss-120b` | GPT-OSS |
| `gpt_oss_20b` | Groq | `openai/gpt-oss-20b` | GPT-OSS |

The experiment therefore contains:

```text
3 annotation configurations
2 model families
```

This distinction is explicitly preserved in the methodology.

Each configuration performs the initial annotation independently.

---

# Structured Annotation Output

Every successful annotator must return:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

An explicit empty annotation is allowed when the evidence does not justify a classification:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

This represents valid abstention rather than malformed output.

---

# Strict Annotation Validation

LLM responses are validated before acceptance.

The system checks:

- JSON structure
- required keys
- correct list types
- valid Genre taxonomy paths
- valid Metadata taxonomy paths
- candidate-path membership
- Fiction/Nonfiction contradictions

Malformed or truncated output is recorded as an error rather than silently accepted.

---

# Inter-Annotator Agreement

Successful annotations are compared using several complementary measurements.

## Exact Agreement

The system measures:

```text
Exact Genre agreement
Exact Metadata agreement
Exact combined agreement
```

## Pairwise Agreement

Comparisons are calculated for:

```text
Qwen 27B      ↔ GPT-OSS 120B
Qwen 27B      ↔ GPT-OSS 20B
GPT-OSS 120B  ↔ GPT-OSS 20B
```

Only books successfully annotated by both members of a pair are included in that pair's denominator.

## Jaccard Similarity

Set overlap is additionally measured using:

```text
J(A,B) = |A ∩ B| / |A ∪ B|
```

Genre and Metadata are evaluated separately.

## Path-Level Agreement

The pipeline identifies:

```text
shared Genre paths
shared Metadata paths
disputed Genre paths
disputed Metadata paths
model-specific paths
```

## Hierarchy-Aware Analysis

Ancestor/descendant relationships are also detected.

For example:

```text
Fiction / Thriller
```

and:

```text
Fiction / Thriller / Political Thriller
```

are hierarchically related but are **not counted as exact agreement**.

---

# Availability Is Separate from Agreement

Infrastructure failure is not treated as semantic disagreement.

For example:

```text
Qwen          → success
GPT-OSS 120B  → success
GPT-OSS 20B   → API failure
```

is:

```text
2 available annotations
```

not a three-model disagreement.

Likewise:

```text
agreement_2_of_2
```

is kept separate from:

```text
agreement_2_of_3
```

---

# Consensus Detection

The consensus stage operates on successful annotations.

Possible resolution categories include:

```text
perfect_3_of_3
agreement_2_of_3
agreement_2_of_2
conflict
```

Original annotations remain preserved even when consensus is detected.

---

# Conflict Analysis

Conflicts preserve more information than a simple disagreement flag.

For each conflict, the system can retain:

```json
{
  "shared_genre_paths": [],
  "shared_metadata_paths": [],
  "disputed_genre_paths": [],
  "disputed_metadata_paths": [],
  "model_only_paths": {}
}
```

This makes the disagreement structure available to the adjudication stage.

---

# Debate Adjudication

Genuine conflicts with sufficient successful annotations are routed to a debate resolver.

The resolver receives:

- filtered evidence
- original annotations
- shared paths
- disputed paths
- model-specific paths
- controlled taxonomy candidates

The resolver returns a complete final annotation.

The debate resolver is an **adjudicator**, not a fourth independent annotator.

Therefore its decisions are not included in the original inter-annotator agreement calculation.

---

# Final Dataset

Final resolved records can originate from:

```text
perfect consensus
partial consensus
debate adjudication
```

Cases that cannot be resolved safely can be separated for manual review.

The final dataset is then subjected to an integrity audit.

---

# Integrity Audit

The final audit checks for:

- duplicate ISBNs
- invalid Genre paths
- invalid Metadata paths
- empty resolved annotations
- Fiction/Nonfiction contradictions
- overlap between resolved and manual-review records

Structural validation does not imply human ground-truth accuracy.

---

# 25-Book End-to-End Validation

Before scaling the experiment, the complete pipeline was validated on 25 books.

Availability:

```text
Qwen 27B:       24 / 25
GPT-OSS 120B:   25 / 25
GPT-OSS 20B:    25 / 25
```

For the 24 books with all three annotations:

```text
Exact Genre agreement:     50.00%
Exact Metadata agreement:  54.17%
Exact combined agreement:  37.50%
```

Consensus routing produced:

```text
Perfect 3-of-3:   9
Partial consensus: 5
Conflicts:        11
```

All:

```text
11 / 11
```

conflicts were successfully processed through debate adjudication.

Final validation dataset:

```text
Resolved:       25
Manual review:   0
Duplicates:      0
Invalid paths:   0
```

These are **pipeline-validation results**, not final 400-book experimental results.

---

# Current 400-Book Experiment Status

Completed:

- [x] ISBN preparation
- [x] Open Library collection
- [x] Goodreads collection
- [x] Amazon collection
- [x] source provenance preservation
- [x] master dataset construction
- [x] evidence extraction
- [x] Genre union
- [x] Genre filtering agent
- [x] reviewed Genre hierarchy
- [x] reviewed Metadata hierarchy
- [x] candidate retrieval
- [x] annotation agent
- [x] strict annotation parser
- [x] taxonomy validator
- [x] multi-LLM annotation framework
- [x] checkpointing
- [x] quota handling
- [x] inter-annotator evaluation
- [x] path-level agreement analysis
- [x] hierarchy-aware analysis
- [x] consensus builder
- [x] conflict routing
- [x] debate resolver
- [x] final dataset builder
- [x] integrity audit
- [x] end-to-end 25-book validation

In progress:

- [ ] complete remaining 400-book annotation calls
- [ ] regenerate final 400-book agreement metrics
- [ ] regenerate final consensus/conflict outputs
- [ ] run final 400-book debate queue
- [ ] build final 400-book hierarchical dataset
- [ ] run final 400-book integrity audit

---

# Current Annotation Checkpoint

Latest saved full-run progress:

```text
Qwen 27B
Successful:        251
No filtered tags:    3
Remaining:         146

GPT-OSS 120B
Successful:        202
No filtered tags:    3
Remaining:         195

GPT-OSS 20B
Successful:        194
No filtered tags:    3
Remaining:         203
```

Required successful annotations:

```text
397 books × 3 configurations
= 1191
```

Currently completed:

```text
647 / 1191
≈ 54.3%
```

The remaining annotations are primarily blocked by external API daily token quotas.

Provider failures are not interpreted as model disagreement.

---

# Repository Structure

```text
hierarchical-book-genre-classification/
│
├── agents/
│   ├── genre_filtering_agent.py
│   ├── annotation_agent.py
│   ├── debate_resolver.py
│   └── llm_providers.py
│
├── data/
│   ├── book coverpage/
│   ├── book blurb/
│   ├── book reviews/
│   ├── genre union/
│   ├── master_data.json
│   └── clean_master_data.csv
│
├── docs/
│   ├── 01_project_workflow.md
│   ├── 02_data_contract.md
│   ├── 03_annotation_methodology.md
│   ├── 04_inter_annotator_agreement.md
│   ├── 05_consensus_and_debate.md
│   ├── 06_results.md
│   └── 07_limitations.md
│
├── input/
│   ├── isbns.csv
│   └── isbns_400.csv
│
├── results/
│   ├── annotations/
│   ├── consensus/
│   ├── debate/
│   ├── evaluation/
│   ├── filtering/
│   └── final/
│
├── scrapers/
│   ├── openlibrary.py
│   ├── goodreads.py
│   └── amazon.py
│
├── scripts/
│   ├── build_master_data.py
│   ├── build_clean_master.py
│   ├── run_genre_filtering.py
│   ├── run_annotations.py
│   ├── split_annotations.py
│   ├── evaluate_annotations.py
│   ├── analyze_path_agreement.py
│   ├── build_consensus.py
│   ├── build_debate_inputs.py
│   ├── run_debate_resolver.py
│   ├── build_final_dataset.py
│   └── audit_final_output.py
│
├── taxonomy/
│   ├── genre_hierarchy.json
│   └── metadata_hierarchy.json
│
├── tests/
├── requirements.txt
└── README.md
```

Generated research datasets containing source-derived content may be excluded from the public repository while the code, methodology, schemas, and taxonomy definitions remain reproducible.

---

# Documentation

Detailed methodology is available in:

```text
docs/01_project_workflow.md
```

Complete data and JSON flow:

```text
docs/02_data_contract.md
```

Annotation methodology:

```text
docs/03_annotation_methodology.md
```

Inter-annotator agreement:

```text
docs/04_inter_annotator_agreement.md
```

Consensus and debate methodology:

```text
docs/05_consensus_and_debate.md
```

Experimental results:

```text
docs/06_results.md
```

Limitations and threats to validity:

```text
docs/07_limitations.md
```

---

# Installation

Create the environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Environment Variables

LLM provider credentials are stored locally in:

```text
.env
```

API credentials must never be committed to Git.

The repository `.gitignore` should exclude:

```text
.env
```

---

# Running the Pipeline

## 1. Build source/master data

```bash
python -m scripts.build_master_data
python -m scripts.build_clean_master
```

## 2. Run Genre filtering

```bash
python -m scripts.run_genre_filtering
```

## 3. Run multi-LLM annotation

For the full experiment:

```bash
python -m scripts.run_annotations --limit 400 --delay 2
```

Successful results are checkpointed.

The command can therefore be rerun after provider quota recovery without discarding previously successful annotations.

## 4. Build annotation outputs and agreement analysis

After all annotations are complete:

```bash
python -m scripts.split_annotations
python -m scripts.evaluate_annotations
python -m scripts.analyze_path_agreement
```

## 5. Build consensus and conflict inputs

```bash
python -m scripts.build_consensus
python -m scripts.build_debate_inputs
```

## 6. Resolve conflicts

```bash
python -m scripts.run_debate_resolver
```

## 7. Build and audit the final dataset

```bash
python -m scripts.build_final_dataset
python -m scripts.audit_final_output
```

---

# Testing

Run the project tests from the repository root:

```bash
PYTHONPATH=. python -m pytest -q
```

---

# Reproducibility Principles

The project deliberately separates:

```text
source evidence
↓
filtered evidence
↓
taxonomy candidates
↓
individual model annotations
↓
agreement measurements
↓
consensus decisions
↓
conflict adjudication
↓
final resolved dataset
```

This allows each stage to be inspected independently without silently overwriting the evidence from previous stages.

---

# Interpretation

The project measures:

- source coverage
- annotation availability
- exact inter-annotator agreement
- pairwise agreement
- set overlap
- path-level agreement
- hierarchical relationships
- consensus
- conflict frequency
- adjudication outcomes
- structural validity

It does **not** currently claim human ground-truth classification accuracy because the experiment does not contain an independent expert-labelled gold-standard dataset.

In particular:

```text
agreement ≠ accuracy
consensus ≠ ground truth
provider failure ≠ disagreement
hierarchy proximity ≠ exact agreement
debate resolver ≠ fourth independent annotator
```

---

# Research Status

The pipeline implementation is complete and has been validated end-to-end.

The final 400-book experiment remains in progress because external API token quotas interrupted the remaining annotation requests.

Final 400-book agreement, consensus, debate, and dataset statistics will be reported only after all remaining annotation calls are completed and the downstream analysis is regenerated.

---

## Research Use

This repository is intended for research and educational experimentation in:

- hierarchical classification
- multi-source metadata integration
- LLM-assisted annotation
- inter-annotator agreement
- multi-agent conflict resolution
- controlled taxonomy annotation

Users should respect applicable source terms, copyright restrictions, and data-use requirements when collecting or redistributing externally derived book content.