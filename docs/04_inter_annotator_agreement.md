# Inter-Annotator Agreement

## 1. Purpose

The project uses multiple LLM annotation configurations to determine whether hierarchical Genre and Metadata assignments are stable across annotators.

Inter-annotator agreement measures consistency between successful annotations.

It does **not** by itself measure ground-truth accuracy.

The experiment currently compares:

| Annotator | Model Family | Model |
|---|---|---|
| `qwen_groq` | Qwen | `qwen/qwen3.8-27b` |
| `gpt_oss_groq` | GPT-OSS | `openai/gpt-oss-120b` |
| `gpt_oss_20b` | GPT-OSS | `openai/gpt-oss-20b` |

Therefore the experiment contains three annotation configurations but two model families.

---

## 2. Agreement Input

Each successful annotator independently produces:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

Agreement analysis compares these outputs for the same ISBN.

Conceptually:

```text
Book
 |
 +--> Qwen annotation
 |
 +--> GPT-OSS 120B annotation
 |
 +--> GPT-OSS 20B annotation
 |
 v
Inter-Annotator Agreement
```

The models do not see each other's initial annotations.

---

## 3. Availability Before Agreement

Before measuring agreement, the system determines how many successful annotations are available.

Possible cases are:

```text
3 successful annotations
→ eligible for 3-configuration agreement

2 successful annotations
→ eligible for pairwise / 2-available agreement

1 successful annotation
→ insufficient for inter-annotator agreement

0 successful annotations
→ no agreement measurement
```

Availability and agreement are reported separately.

This prevents API failures from being interpreted as semantic disagreement.

---

## 4. Provider Failure Is Not Disagreement

Suppose:

```text
Qwen          → success
GPT-OSS 120B  → success
GPT-OSS 20B   → HTTP 429
```

This means:

```text
available annotators = 2
```

It does **not** mean:

```text
2 models agree and 1 model disagrees
```

The third model did not produce an annotation.

Therefore provider errors, network failures, malformed responses, and other unsuccessful calls are excluded from semantic disagreement calculations.

---

## 5. Exact Genre Agreement

Genre annotations are treated as sets of taxonomy paths.

Exact Genre agreement occurs when successful annotators return the same Genre-path set.

Example:

```text
Model A:
{Short Fiction}

Model B:
{Short Fiction}

Model C:
{Short Fiction}
```

This is exact Genre agreement.

However:

```text
Model A:
{Short Fiction}

Model B:
{Short Fiction, Social and Political Fiction}

Model C:
{Short Fiction}
```

is not exact three-way Genre agreement because the complete sets differ.

---

## 6. Exact Metadata Agreement

Metadata is evaluated separately from Genre.

Example:

```text
Model A:
{English, Young Adult}

Model B:
{English, Young Adult}

Model C:
{English, Young Adult}
```

produces exact Metadata agreement.

If one model additionally assigns another Metadata path, exact set agreement fails even if most Metadata paths are shared.

---

## 7. Exact Combined Agreement

A book receives exact combined agreement only when both dimensions agree:

```text
Genre sets equal
AND
Metadata sets equal
```

This is stricter than evaluating Genre or Metadata independently.

---

## 8. Pairwise Agreement

Agreement is also measured between each pair of successful annotation configurations.

The current pairs are:

```text
Qwen 27B      ↔ GPT-OSS 120B
Qwen 27B      ↔ GPT-OSS 20B
GPT-OSS 120B  ↔ GPT-OSS 20B
```

Each pair is evaluated only on books for which both configurations successfully produced annotations.

The denominator can therefore differ between model pairs.

---

## 9. Jaccard Similarity

Exact agreement is strict.

To measure partial set overlap, the project also uses Jaccard similarity.

For annotation sets A and B:

```text
J(A,B) = |A ∩ B| / |A ∪ B|
```

Interpretation:

```text
1.0
→ identical non-empty sets

0.0
→ no shared paths

between 0 and 1
→ partial overlap
```

Genre and Metadata Jaccard similarity are calculated separately.

---

## 10. Empty-Set Handling

Two empty annotation sets require special treatment.

An empty-empty comparison can be an exact match, but it provides no positive path overlap.

Therefore empty-empty cases are not used to artificially inflate mean Jaccard similarity.

Exact agreement and Jaccard similarity answer different questions and are reported separately.

---

## 11. Path-Level Agreement

Exact-set comparison can hide meaningful agreement.

Example:

```text
Qwen:
Short Fiction

GPT-OSS 120B:
Short Fiction
Social and Political Fiction

GPT-OSS 20B:
Short Fiction
```

Although the complete Genre sets differ, all three annotators selected:

```text
Short Fiction
```

The pipeline therefore computes path-level support.

For each book it identifies:

```json
{
  "shared_genre_paths": [],
  "shared_metadata_paths": [],
  "disputed_genre_paths": [],
  "disputed_metadata_paths": [],
  "model_only_paths": {}
}
```

---

## 12. Shared Paths

A shared path is selected by every successful annotator available for that book.

For three successful annotators:

```text
Short Fiction
Qwen          ✓
GPT-OSS 120B  ✓
GPT-OSS 20B   ✓

Support = 3/3
```

For two successful annotators:

```text
Short Fiction
Qwen          ✓
GPT-OSS 120B  ✓

Support = 2/2
```

The second case must not be reported as 2/3 because the third annotation was unavailable.

---

## 13. Disputed Paths

A disputed path appears in at least one successful annotation but is not shared by all successful annotators.

Example:

```text
Social and Political Fiction

Qwen          ✗
GPT-OSS 120B  ✓
GPT-OSS 20B   ✗

Support = 1/3
```

Disputed paths become important evidence for the later adjudication stage.

---

## 14. Model-Only Paths

The system also records paths selected uniquely by one annotator.

This helps identify where a particular configuration produced a more specific or different interpretation than the others.

Model-only paths are not automatically considered incorrect.

They are preserved for conflict analysis.

---

## 15. Hierarchy-Aware Agreement

Hierarchical classification creates another type of partial relationship.

Consider:

```text
Fiction / Thriller
```

and:

```text
Fiction / Thriller / Political Thriller
```

These are not exact path matches.

However, one is an ancestor of the other.

The project therefore separately detects ancestor/descendant relationships between model annotations.

This is called hierarchy-aware overlap or hierarchy proximity.

---

## 16. Hierarchy Proximity Is Not Exact Agreement

An ancestor/descendant relationship is informative, but it must not be converted into exact agreement.

Therefore:

```text
exact path match
≠
hierarchical relationship
```

Both statistics can be reported, but they answer different questions.

This avoids artificially increasing agreement scores.

---

## 17. Consensus Categories

After agreement analysis, successful annotations may be routed into categories such as:

```text
perfect_3_of_3
agreement_2_of_3
agreement_2_of_2
conflict
```

### Perfect 3-of-3

All three successful annotation configurations return the same complete Genre and Metadata annotation.

### Agreement 2-of-3

Three annotations are available and two have the same complete annotation.

### Agreement 2-of-2

Only two successful annotations are available and both agree.

This must remain distinguishable from 2-of-3 agreement.

### Conflict

Successful annotations do not satisfy the configured consensus condition and require further examination.

---

## 18. No-Filtered-Tag Cases

Books for which the filtering stage produced no usable evidence are treated separately.

They are not forced into the agreement pipeline merely to obtain a label.

This preserves the system's ability to abstain.

---

## 19. Insufficient Annotation Cases

If fewer than two successful annotations are available for a book, inter-annotator agreement cannot be meaningfully calculated.

Such a case should be treated as incomplete or manual-review eligible rather than semantic disagreement.

---

## 20. Debate Routing

Agreement analysis determines which cases require adjudication.

Conceptually:

```text
Independent Annotations
         |
         v
Agreement Analysis
         |
    +----+----+
    |         |
    v         v
Consensus   Conflict
              |
              v
       Debate Adjudication
```

The debate stage is therefore downstream of inter-annotator analysis.

It does not participate in the original agreement measurement.

---

## 21. Why Multiple Metrics Are Required

No single metric fully describes hierarchical annotation consistency.

Exact agreement answers:

> Did the annotators return exactly the same set?

Jaccard similarity answers:

> How much do their selected sets overlap?

Path-level support answers:

> Which individual taxonomy assignments are shared or disputed?

Hierarchy-aware analysis answers:

> Are different selections structurally related within the taxonomy?

Availability answers:

> How many annotators actually produced valid outputs?

Together, these provide a more informative analysis than a single agreement percentage.

---

## 22. Interpretation of Agreement

High agreement can indicate that the annotation task and taxonomy produce consistent model decisions.

Low agreement can identify:

- ambiguous book evidence
- overlapping taxonomy categories
- differences in annotation specificity
- model reasoning differences
- difficult hierarchical boundaries

However:

```text
agreement ≠ correctness
```

Three models can agree and still be wrong.

Without an independent human-labelled gold standard, the experiment should describe these measurements as inter-annotator consistency rather than classification accuracy.

---

## 23. Current Full-Run Status

The complete experiment contains 400 books.

The Genre Filtering stage has already been completed.

The full three-configuration annotation run is still incomplete because external API token quotas interrupted the remaining annotation calls.

Therefore final 400-book agreement percentages must not be reported until the annotation checkpoint is complete and the evaluation scripts are rerun.

Existing 25-book measurements belong to the earlier pipeline-validation experiment and must not be presented as final 400-book results.

---

## 24. Research Interpretation Rule

The agreement analysis follows this principle:

> Compare semantic decisions only when annotators actually produced valid decisions, report availability separately, preserve partial hierarchical agreement, and never convert infrastructure failure into model disagreement.

This distinction is essential for scientifically meaningful inter-annotator analysis.