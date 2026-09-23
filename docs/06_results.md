# Experimental Results

## 1. Experiment Scope

The full experiment contains:

```text
400 books
```

The experiment evaluates the complete pipeline:

```text
Multi-Source Collection
        ↓
Master Data Construction
        ↓
Genre Filtering
        ↓
Multi-LLM Annotation
        ↓
Inter-Annotator Agreement
        ↓
Consensus / Conflict Detection
        ↓
Debate Adjudication
        ↓
Final Hierarchical Dataset
        ↓
Integrity Audit
```

The full 400-book annotation stage is currently in progress.

Therefore this document separates:

1. completed 400-book preprocessing/filtering results
2. annotation progress
3. previously completed pipeline-validation results
4. final results that must remain pending

---

# 2. Multi-Source Data Collection

The 400-book experimental subset was searched across:

- Open Library
- Goodreads
- Amazon

Source retrieval results were:

| Source | Successful Records |
|---|---:|
| Open Library | 400 / 400 |
| Goodreads | 395 / 400 |
| Amazon | 305 / 400 |

No book in the 400-book experimental subset was missing from every source.

---

# 3. Source Overlap

The collected records showed different levels of source availability.

```text
All three sources:        301 books
Open Library + Goodreads: 395 books
Open Library + Amazon:    305 books
Only Open Library:          1 book
Missing everywhere:         0 books
```

This demonstrates why multi-source collection is useful: no individual commercial/community source provided complete coverage.

---

# 4. Master Dataset

The source records were merged by ISBN while preserving provenance.

The resulting experimental master dataset contains:

```text
400 books
400 unique ISBN records
```

Primary files include:

```text
data/master_data.json
data/clean_master_data.csv
```

Source-specific evidence remains available for later processing.

---

# 5. Evidence Availability

Within the 400-book experimental dataset:

```text
Open Library genre evidence: 394 books
Goodreads genre evidence:    217 books
Amazon genre evidence:       269 books

Books with blurb evidence:   389
Books with review evidence:   96
```

Evidence availability differs across sources and evidence types.

Missing evidence is preserved rather than synthetically generated.

---

# 6. Genre Filtering Results

The Genre Filtering Agent was executed over all 400 books.

Final filtering results:

```text
Total books:               400
Successful filtering:      397
No usable candidate tags:    3
Filtering errors:             0
Hallucinated new tags:        0
```

The three books without usable candidate tags remain explicit abstention/no-filtered-tag cases.

The filtering stage therefore completed successfully for the full experimental dataset.

---

# 7. Controlled Taxonomies

The active reviewed taxonomy files are:

```text
taxonomy/genre_hierarchy.json
taxonomy/metadata_hierarchy.json
```

The current Genre taxonomy contains approximately:

```text
661 hierarchical paths
```

The current Metadata taxonomy contains approximately:

```text
466 hierarchical paths
```

The annotation system accepts only validated paths from these controlled taxonomies.

---

# 8. Annotation Configurations

The full annotation experiment uses:

| Configuration | Model | Family |
|---|---|---|
| `qwen_groq` | `qwen/qwen3.8-27b` | Qwen |
| `gpt_oss_groq` | `openai/gpt-oss-120b` | GPT-OSS |
| `gpt_oss_20b` | `openai/gpt-oss-20b` | GPT-OSS |

The experiment therefore contains:

```text
3 annotation configurations
2 model families
```

---

# 9. Current 400-Book Annotation Progress

The latest saved checkpoint contains:

```text
Qwen 27B
success:           251
no_filtered_tags:    3
remaining/error:   146

GPT-OSS 120B
success:           202
no_filtered_tags:    3
remaining/error:   195

GPT-OSS 20B
success:           194
no_filtered_tags:    3
remaining/error:   203
```

For the 397 books with usable filtered evidence, the experiment requires:

```text
397 × 3 = 1191
```

successful annotation calls.

Currently completed successful annotations:

```text
251 + 202 + 194 = 647
```

Current completion of required successful annotation calls:

```text
647 / 1191 ≈ 54.3%
```

Remaining successful annotations required:

```text
544
```

These remaining records are incomplete primarily because external API daily token quotas interrupted the run.

They must not be interpreted as semantic model disagreement.

---

# 10. Annotation Checkpointing

Completed annotations are preserved in:

```text
results/annotations/multi_llm_annotations.json
```

The runner reuses successful results and retries incomplete/error records.

When a configured model reaches confirmed daily token quota exhaustion, it is paused for the remainder of that execution rather than repeatedly generating guaranteed quota failures.

This allows the experiment to continue across multiple API-quota windows without discarding completed work.

---

# 11. Pipeline Validation Experiment

Before scaling to the complete 400-book experiment, the complete downstream architecture was tested on smaller subsets.

A 25-book validation run successfully exercised:

```text
annotation
↓
inter-annotator evaluation
↓
path-level analysis
↓
consensus construction
↓
conflict routing
↓
debate adjudication
↓
final dataset construction
↓
integrity audit
```

The 25-book run demonstrated that the complete software pipeline operates end-to-end.

Its statistics are validation results and must not be reported as final 400-book experimental performance.

---

# 12. 25-Book Validation Summary

For the 25-book validation experiment:

```text
Qwen successful annotations:          24 / 25
GPT-OSS 120B successful annotations:  25 / 25
GPT-OSS 20B successful annotations:   25 / 25
```

Availability:

```text
24 books had 3 successful annotations
1 book had 2 successful annotations
```

For the 24 books with all three annotations available:

```text
Exact Genre agreement:       12 / 24 = 50.00%
Exact Metadata agreement:    13 / 24 = 54.17%
Exact combined agreement:     9 / 24 = 37.50%
```

These percentages measure inter-annotator consistency.

They do not measure classification accuracy.

---

# 13. 25-Book Pairwise Validation

Pairwise results from the validation experiment were:

### Qwen vs GPT-OSS 120B

```text
Common successful books: 24
Exact Genre:              58.33%
Exact Metadata:           62.50%
Exact combined:           41.67%
Mean Genre Jaccard:        0.750
Mean Metadata Jaccard:     0.531
```

### Qwen vs GPT-OSS 20B

```text
Common successful books: 24
Exact Genre:              58.33%
Exact Metadata:           70.83%
Exact combined:           41.67%
Mean Genre Jaccard:        0.731
Mean Metadata Jaccard:     0.757
```

### GPT-OSS 120B vs GPT-OSS 20B

```text
Common successful books: 25
Exact Genre:              60.00%
Exact Metadata:           68.00%
Exact combined:           48.00%
Mean Genre Jaccard:        0.700
Mean Metadata Jaccard:     0.582
```

Pairwise calculations use only books for which both compared annotators returned successful outputs.

---

# 14. 25-Book Hierarchy-Aware Validation

The validation experiment also detected:

```text
Genre ancestor/descendant relationships:    26
Metadata ancestor/descendant relationships: 23
```

This confirms that some model differences occur because annotators select related paths at different levels of the hierarchy.

These relationships are recorded separately and are not counted as exact agreement.

---

# 15. 25-Book Consensus Routing

The 25-book validation run produced:

```text
Perfect 3-of-3 consensus:   9
Partial consensus:          5
Conflicts:                 11
No filtered evidence:       0
```

All 25 books were accounted for.

The partial-consensus records included both:

```text
agreement_2_of_3
```

and:

```text
agreement_2_of_2
```

depending on annotator availability.

---

# 16. 25-Book Debate Validation

The 11 conflict records were routed to debate adjudication.

Final debate status:

```text
Successful debate resolutions: 11 / 11
```

This validated the conflict-routing and adjudication stages.

---

# 17. 25-Book Final Dataset Validation

The final validation dataset contained:

```text
Resolved records:       25
Manual-review records:   0
Total records:          25
Unique ISBNs:           25
```

Resolution methods:

```text
perfect_3_of_3_consensus: 9
agreement_2_of_3:          4
agreement_2_of_2:          1
debate_resolver:          11
```

---

# 18. 25-Book Integrity Audit

The final validation audit reported:

```text
Duplicate ISBNs:                   0
Final/manual-review overlap:       0
Empty resolved annotations:        0
Invalid Genre paths:               0
Invalid Metadata paths:            0
Fiction + Nonfiction violations:   0
```

This demonstrates structural correctness of the complete pipeline on the validation subset.

It does not constitute human ground-truth accuracy evaluation.

---

# 19. Final 400-Book Results — Pending

The following statistics must remain pending until all required annotations are complete:

```text
Final 3-model availability
Final pairwise coverage
Final exact Genre agreement
Final exact Metadata agreement
Final exact combined agreement
Final Genre Jaccard similarity
Final Metadata Jaccard similarity
Final hierarchy-aware overlap
Final perfect consensus count
Final partial consensus count
Final conflict count
Final debate count
Final debate success count
Final manual-review count
Final resolved dataset size
Final integrity-audit statistics
```

No values from the 25-book validation experiment should be copied into these fields as substitutes.

---

# 20. Required Final Execution Sequence

After annotation completion, the final 400-book downstream analysis must be regenerated in this order:

```bash
python -m scripts.split_annotations
python -m scripts.evaluate_annotations
python -m scripts.analyze_path_agreement
python -m scripts.build_consensus
python -m scripts.build_debate_inputs
```

After inspecting the actual conflict count:

```bash
python -m scripts.run_debate_resolver
```

Then:

```bash
python -m scripts.build_final_dataset
python -m scripts.audit_final_output
```

Only the newly generated 400-book outputs should be used for the final experimental report.

---

# 21. Result Interpretation

The experiment distinguishes three different questions.

### Coverage

How many books received successful annotations from each configuration?

### Consistency

How strongly did successful annotators agree with one another?

### Structural Validity

Did the final annotations obey the controlled Genre and Metadata hierarchies and dataset integrity rules?

These should not be confused with:

```text
ground-truth classification accuracy
```

because the current experiment does not contain an independent human-labelled gold-standard dataset.

---

# 22. Current Conclusion

The software architecture and complete end-to-end pipeline have been validated successfully.

The full 400-book preprocessing and Genre Filtering stages are complete.

The 400-book multi-LLM annotation stage remains incomplete because of external API quota constraints.

Therefore final claims about inter-annotator agreement, conflict frequency, debate resolution, and final dataset composition will be made only after the remaining annotations are completed and all downstream outputs are regenerated.