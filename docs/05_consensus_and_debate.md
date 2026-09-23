# Consensus, Conflict Detection, and Debate Adjudication

## 1. Purpose

After independent annotation and inter-annotator analysis, the system must determine which books can be accepted through consensus and which require further adjudication.

The pipeline separates:

- annotation
- agreement measurement
- consensus construction
- conflict detection
- debate adjudication
- final resolution

This separation prevents the debate model from influencing the original inter-annotator agreement measurement.

---

## 2. Pipeline Position

```text
Qwen 27B ───────────┐
                    |
GPT-OSS 120B ───────┼──> Inter-Annotator Analysis
                    |
GPT-OSS 20B ────────┘
                              |
                              v
                     Consensus Builder
                              |
                    +---------+---------+
                    |                   |
                    v                   v
                Consensus            Conflict
                    |                   |
                    |                   v
                    |             Debate Input
                    |                   |
                    |                   v
                    |          Debate Adjudicator
                    |                   |
                    +---------+---------+
                              |
                              v
                       Final Annotation
```

---

## 3. Consensus Input

Consensus construction uses only successful annotations.

Each successful annotation contains:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

The pipeline also records which annotators were actually available.

Provider/API failures are not converted into disagreement votes.

---

## 4. Exact Annotation Signature

For consensus routing, the complete annotation is considered using both:

```text
Genre path set
+
Metadata path set
```

Two annotations are exact matches only when both normalized sets match.

Therefore models can agree on Genre while still disagreeing on the complete annotation because their Metadata differs.

---

## 5. Perfect 3-of-3 Consensus

When all three annotation configurations successfully return the same complete annotation:

```text
Qwen          = A
GPT-OSS 120B  = A
GPT-OSS 20B   = A
```

the result is:

```text
perfect_3_of_3
```

This is the strongest exact consensus condition in the current pipeline.

It represents agreement among three annotation configurations, not three independent model families.

---

## 6. Partial 2-of-3 Consensus

When all three annotations are available but two return the same complete annotation:

```text
Qwen          = A
GPT-OSS 120B  = A
GPT-OSS 20B   = B
```

the majority annotation has:

```text
2-of-3 support
```

This is stored separately from perfect 3-of-3 consensus.

The minority annotation is still preserved in the original annotation records.

---

## 7. Agreement 2-of-2

A different situation occurs when only two valid annotations are available:

```text
Qwen          = A
GPT-OSS 120B  = A
GPT-OSS 20B   = API failure
```

The correct description is:

```text
agreement_2_of_2
```

It must not be described as 2-of-3 agreement.

The third model did not disagree; it was unavailable.

---

## 8. Conflict

A book is considered a genuine annotation conflict when sufficient successful annotations exist but the configured consensus condition is not satisfied.

For example:

```text
Qwen          = A
GPT-OSS 120B  = B
GPT-OSS 20B   = C
```

or when complete annotation sets differ enough that no accepted exact consensus route applies.

These cases are candidates for debate adjudication.

---

## 9. Path-Level Conflict Information

A conflict record does not simply state:

```text
models disagree
```

Instead, the pipeline preserves the structure of disagreement.

It records:

```json
{
  "shared_genre_paths": [],
  "shared_metadata_paths": [],
  "disputed_genre_paths": [],
  "disputed_metadata_paths": [],
  "model_only_paths": {}
}
```

This allows the adjudicator to distinguish stable shared information from genuinely disputed assignments.

---

## 10. Shared Paths

Shared paths are selected by every successful annotator available for the book.

Example:

```text
Short Fiction

Qwen          ✓
GPT-OSS 120B  ✓
GPT-OSS 20B   ✓
```

This path has:

```text
3/3 support
```

A conflict elsewhere in the annotation does not erase this shared evidence.

---

## 11. Disputed Paths

A disputed path appears in at least one successful annotation but is not selected by all successful annotators.

Example:

```text
Social and Political Fiction

Qwen          ✗
GPT-OSS 120B  ✓
GPT-OSS 20B   ✗
```

Support:

```text
1/3
```

The debate stage can specifically examine whether this disputed assignment is supported by the original evidence.

---

## 12. Debate Eligibility

The debate stage is intended for genuine conflicts with sufficient successful original annotations.

Cases with too little successful annotation evidence are separated rather than pretending that a debate occurred between unavailable models.

Conceptually:

```text
2 or more successful annotations + conflict
→ debate eligible

fewer than 2 successful annotations
→ incomplete/manual-review path
```

---

## 13. Debate Input

The debate input preserves the information required for adjudication.

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

The original model annotations remain visible.

The adjudicator therefore does not receive only a simplified majority label.

---

## 14. Role of the Debate Resolver

The debate resolver is an **adjudicator**.

Its purpose is to inspect conflicting annotations and produce one evidence-supported final annotation.

It is not:

- a fourth independent annotator
- another vote in the original agreement calculation
- a replacement for inter-annotator analysis

Therefore:

```text
3 initial annotation configurations
+
1 adjudicator
```

must never be reported as:

```text
4 independent annotators
```

---

## 15. Debate Evidence

The resolver considers information such as:

- filtered source-derived evidence
- candidate taxonomy paths
- original model annotations
- shared Genre paths
- shared Metadata paths
- disputed Genre paths
- disputed Metadata paths
- model-specific paths

The resolver must still follow the same controlled Genre and Metadata taxonomies.

---

## 16. Debate Output

The adjudicator returns a complete structured annotation:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

The resolver is not restricted to returning only the disputed path.

It returns the complete final annotation for the book.

---

## 17. Debate Validation

The adjudicated result is validated before being accepted.

The final paths must exist in the active taxonomies and satisfy the annotation constraints.

A debate response therefore cannot bypass the controlled classification system.

---

## 18. Example

Suppose the original annotations are:

```text
Qwen:
Genre:
- Short Fiction

Metadata:
- Short Story
- Young Adult
- Teen
- English
```

```text
GPT-OSS 120B:
Genre:
- Short Fiction
- Social and Political Fiction

Metadata:
- Short Story
- Young Adult
- Teen
- English
- Narrative Length: Short
```

```text
GPT-OSS 20B:
Genre:
- Short Fiction

Metadata:
- Short Story
- Young Adult
- English
- Narrative Length: Short
```

Path analysis can identify:

```text
Shared Genre:
- Short Fiction

Disputed Genre:
- Social and Political Fiction

Shared Metadata:
- Short Story
- Young Adult
- English

Disputed Metadata:
- Teen
- Narrative Length: Short
```

The adjudicator then examines the evidence supporting the disputed assignments.

It does not need to reconsider the case as three completely unrelated outputs.

---

## 19. Final Resolution Routes

A final annotation may originate from different resolution methods.

Examples include:

```text
perfect_3_of_3_consensus
agreement_2_of_3
agreement_2_of_2
debate_resolver
```

The resolution method is preserved so that downstream analysis can distinguish automatically agreed cases from adjudicated cases.

---

## 20. Manual Review

Not every book must be forced into an automatic final annotation.

Cases can require manual review when:

- insufficient successful annotations are available
- evidence is insufficient
- adjudication cannot produce a valid result
- structural validation fails

Manual review is preferable to fabricating unsupported annotations.

---

## 21. Final Dataset Construction

The final dataset combines valid resolved records from the available routes.

Conceptually:

```text
Perfect Consensus ─────────┐
                           |
Partial Consensus ─────────┼──> Final Dataset
                           |
Debate Resolution ─────────┤
                           |
Manual Review ─────────────┘
        kept separate when unresolved
```

Only validated resolved records enter the resolved final dataset.

---

## 22. Integrity Audit

After final construction, an integrity audit checks for:

- duplicate ISBNs
- invalid Genre paths
- invalid Metadata paths
- empty resolved annotations
- Fiction/Nonfiction contradictions
- resolved/manual-review overlap

This validates structural consistency of the final output.

It does not constitute human ground-truth validation.

---

## 23. Important Research Distinctions

The following concepts must remain separate:

```text
Consensus
≠ Accuracy

Disagreement
≠ Error

Provider failure
≠ Disagreement

Hierarchy proximity
≠ Exact agreement

Debate adjudication
≠ Independent annotation

Manual review
≠ Pipeline failure
```

These distinctions are important when interpreting the final experiment.

---

## 24. Why the Debate Stage Exists

A simple majority vote would discard useful information about *why* models differ.

The debate/adjudication stage instead preserves:

```text
shared evidence
+
disputed paths
+
model-specific decisions
+
original book evidence
```

and performs a separate controlled resolution step.

This makes the conflict-resolution process more transparent than blindly accepting a majority label.

---

## 25. Current Status

The consensus and debate implementation has already been validated on smaller pipeline runs.

However, the final 400-book annotation experiment is still incomplete because of external API quota limitations.

Therefore the current downstream consensus, debate, evaluation, and final-output files must not be interpreted as final 400-book experimental results until:

```text
400-book annotation completes
        ↓
agreement evaluation reruns
        ↓
consensus rebuilds
        ↓
debate inputs rebuild
        ↓
debate resolution completes
        ↓
final dataset rebuilds
        ↓
final audit passes
```

The final experiment statistics will be documented only after this process is complete.