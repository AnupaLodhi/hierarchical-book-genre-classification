# Limitations and Threats to Validity

## 1. Purpose

This document records the limitations of the Hierarchical Book Genre Classification experiment.

The purpose is not to weaken the research, but to clearly distinguish what the current experiment demonstrates from what it does not demonstrate.

---

## 2. No Human-Labeled Gold Standard

The current dataset does not contain an independently created expert human gold-standard annotation for every book.

Therefore the project can evaluate:

- inter-annotator consistency
- model agreement
- taxonomy compliance
- annotation coverage
- conflict frequency
- hierarchy relationships
- structural validity

However, it cannot directly claim:

```text
X% classification accuracy
```

against human ground truth.

Agreement between models is not equivalent to correctness.

---

## 3. Three Configurations but Two Model Families

The current experiment uses:

```text
Qwen 27B
GPT-OSS 120B
GPT-OSS 20B
```

These represent three annotation configurations but only two model families:

```text
Qwen
GPT-OSS
```

The GPT-OSS 120B and GPT-OSS 20B configurations may exhibit correlated behavior because they belong to the same model family.

Therefore the experiment must not describe the current setup as three fully independent model families.

---

## 4. Shared Provider Dependency

The current annotation configurations use the same external inference provider.

This introduces a common infrastructure dependency.

Provider-side factors such as:

- availability
- token quotas
- rate limits
- service capacity
- API behavior

can affect multiple annotators.

Provider failure is therefore tracked separately from semantic model disagreement.

---

## 5. API Quota Constraints

The full 400-book experiment has been interrupted by external daily token quotas.

Completed annotations are preserved through checkpointing, while incomplete records remain retryable.

This is an operational limitation rather than evidence of annotation disagreement.

The final experiment must not calculate complete 400-book agreement statistics until the remaining annotations are successfully collected.

---

## 6. Source Coverage Is Unequal

Not every book was available from all three metadata sources.

For the 400-book experimental subset:

```text
Open Library: 400 / 400
Goodreads:     395 / 400
Amazon:        305 / 400
```

Therefore some books contain richer multi-source evidence than others.

This can influence the amount of information available to later filtering and annotation stages.

---

## 7. Evidence Availability Is Unequal

Evidence types are also unevenly distributed.

For example:

```text
Books with blurbs:  389 / 400
Books with reviews:  96 / 400
```

A book with rich descriptive evidence may be easier to classify than a book with only sparse bibliographic and genre information.

The pipeline preserves this missingness rather than filling missing evidence with invented information.

---

## 8. Source Genre Labels Can Be Noisy

Amazon, Goodreads, and Open Library do not use identical classification systems.

Their source labels can contain:

- broad categories
- narrow genres
- subject headings
- audience labels
- commercial categories
- contextual Metadata
- inconsistent terminology

The Genre Filtering Agent reduces this noise, but filtering itself is an automated model-based decision.

---

## 9. Filtering Errors Can Propagate

The annotation stage relies on evidence retained by the filtering stage.

Therefore:

```text
source error
      ↓
filtering error
      ↓
candidate retrieval effect
      ↓
annotation effect
```

is possible.

A later LLM cannot recover information that was never collected or that was incorrectly removed upstream unless that information remains available elsewhere in the provided evidence.

---

## 10. Closed Taxonomy Limitation

The project uses controlled Genre and Metadata hierarchies.

This improves consistency but creates a closed-label limitation.

If a valid literary concept is absent from the taxonomy, the annotator cannot create a new taxonomy path during normal annotation.

Therefore the final dataset is constrained by the coverage and quality of the reviewed taxonomies.

---

## 11. Taxonomy Boundary Ambiguity

Hierarchical categories can overlap semantically.

A book may reasonably fit:

- a parent category
- a more specific child category
- multiple related branches

Different models may therefore choose different levels of specificity even when they broadly agree about the book.

The project records ancestor/descendant relationships separately to expose this behavior.

---

## 12. Exact Agreement Is Strict

Exact-set agreement requires complete equality between selected annotation sets.

For example:

```text
Model A:
{A, B}

Model B:
{A, B, C}
```

is counted as an exact disagreement even though the models share two paths.

Therefore exact agreement alone may underestimate semantic similarity.

The project supplements it with:

- Jaccard similarity
- path-level support
- hierarchy-aware relationships

---

## 13. Hierarchy Proximity Is Not Accuracy

An ancestor/descendant relationship indicates structural similarity between annotations.

It does not prove that either annotation is correct.

For this reason hierarchy proximity is reported separately rather than converted into an accuracy score.

---

## 14. Candidate Retrieval Can Affect Annotation

Annotators choose from retrieved candidate taxonomy paths rather than the entire taxonomy.

This improves efficiency and reduces irrelevant choices.

However, if candidate retrieval fails to retrieve a relevant valid path, the downstream annotator cannot select that path.

Candidate retrieval therefore represents another possible source of recall limitation.

---

## 15. LLM Output Variability

Large language models are probabilistic systems.

Even with controlled prompts and low-temperature generation, model behavior may vary because of:

- provider implementation
- backend model updates
- inference changes
- stochastic generation
- API changes

The project records exact model identifiers and configuration information to improve reproducibility.

---

## 16. External Model Version Stability

Externally hosted model identifiers and provider availability can change over time.

A model available during the experiment may later:

- be renamed
- be removed
- change provider
- receive backend updates
- move to a different pricing or quota tier

Exact model/provider information should therefore be preserved with experimental results.

---

## 17. Debate Resolver Is Not Independent Evidence

The debate resolver receives information derived from the initial annotations.

It is therefore an adjudication mechanism rather than an independent fourth annotation source.

Its success rate measures the ability of the pipeline to produce validated conflict resolutions.

It must not be interpreted as additional independent inter-annotator agreement.

---

## 18. Debate Resolution Is Still Model-Based

A debate-resolved annotation can pass structural and taxonomy validation while still being semantically incorrect.

The debate stage improves conflict handling but does not replace expert human validation.

---

## 19. Consensus Does Not Guarantee Correctness

A perfect 3-of-3 annotation means that all three configured annotators returned the same valid controlled annotation.

It does not prove that the annotation is objectively correct.

Models can share biases or interpret the same ambiguous evidence similarly.

Therefore:

```text
consensus ≠ ground truth
```

---

## 20. Shared Model Family Can Increase Correlation

Two annotators use GPT-OSS models of different sizes.

Because they share a model family, agreement between them may partly reflect shared architecture, training characteristics, or family-level behavior.

Pairwise results involving these two configurations should therefore be interpreted with this dependency in mind.

---

## 21. Multi-Source Data Does Not Guarantee Truth

Using multiple sources improves coverage and provenance.

However, repeated information across websites is not necessarily independently verified information.

The same incorrect category can appear on multiple sources.

Source frequency should therefore not automatically be interpreted as factual correctness.

---

## 22. Publication Country Ambiguity

Publication country can be difficult to determine reliably from web metadata.

The project intentionally avoids inferring publication country from:

- author nationality
- ISBN prefix
- website domain
- publisher name alone
- language

As a result, some country fields may remain missing.

This is preferable to introducing unsupported geographic information.

---

## 23. Geographical Metadata Risk

A book's publication location, author nationality, and narrative setting are different concepts.

The annotation prompt explicitly prevents these from being automatically conflated.

Nevertheless, geographical interpretation remains a challenging area when textual evidence is ambiguous.

---

## 24. Temporal Metadata Risk

Historical Genre classification does not necessarily identify the exact historical period represented in the story.

The pipeline therefore requires explicit evidence before assigning specific temporal Metadata.

This conservative approach can reduce unsupported assignments but may also produce more abstentions.

---

## 25. Review Evidence Is Sparse

Only a subset of books contains review evidence.

Reviews may also contain subjective interpretation, spoilers, or reader-specific opinions.

They are therefore treated as supporting textual evidence rather than unquestioned ground truth.

---

## 26. Dataset Size

The main experimental subset contains 400 books.

This is sufficient for evaluating the implemented pipeline and studying annotation behavior within the selected sample.

However, it should not automatically be treated as representative of:

- every literary tradition
- every language
- every publication period
- every Genre
- the entire global book population

Larger and more diverse datasets would improve external validity.

---

## 27. Language Distribution

The available dataset and web sources may contain unequal representation across languages.

Consequently, conclusions derived from the experiment should not automatically be generalized to low-resource languages or multilingual literary collections without additional evaluation.

---

## 28. Genre Distribution

Genre categories may not be equally represented in the 400-book sample.

Highly represented categories can dominate aggregate agreement statistics.

Future analysis can additionally report agreement by Genre branch when sufficient samples are available.

---

## 29. Validation Subset Versus Final Experiment

The completed 25-book experiment was used to validate the end-to-end pipeline.

Its metrics demonstrate that:

- annotation works
- agreement analysis works
- consensus routing works
- debate resolution works
- final construction works
- integrity auditing works

They do not represent final 400-book experimental results.

The distinction between validation results and final experimental results must be preserved.

---

## 30. Infrastructure Reproducibility

The project depends partly on external web sources and external inference APIs.

Exact reproduction at a later date may be affected by:

- changed web pages
- removed source records
- anti-scraping protections
- model availability
- API quotas
- provider changes

Preserving processed evidence and intermediate outputs reduces this reproducibility risk.

---

## 31. Structural Validation Versus Semantic Validation

The integrity audit can prove properties such as:

```text
valid taxonomy paths
no duplicate ISBNs
no prohibited Fiction/Nonfiction contradiction
correct output structure
```

It cannot prove:

```text
the literary interpretation is objectively correct
```

These are different validation levels.

---

## 32. Threats to Construct Validity

The experiment operationalizes annotation quality primarily through:

- agreement
- overlap
- hierarchy consistency
- controlled-taxonomy validity

These are useful indicators of annotation stability, but they are not complete measures of literary classification quality.

Human expert evaluation would strengthen construct validity.

---

## 33. Threats to Internal Validity

Potential internal influences include:

- upstream scraping errors
- missing evidence
- filtering decisions
- candidate retrieval limitations
- prompt interpretation
- shared model-family behavior
- provider-side model changes

The project reduces these risks through provenance preservation, strict schemas, checkpointing, independent initial annotation, and taxonomy validation.

---

## 34. Threats to External Validity

The results are derived from the selected 400-book sample and the active controlled taxonomies.

Generalization to different datasets, languages, domains, or taxonomy designs requires additional experiments.

---

## 35. Future Improvements

Potential future extensions include:

- expert human annotation of a representative gold-standard subset
- additional genuinely independent model families
- independent inference providers
- larger book collections
- multilingual evaluation
- Genre-balanced sampling
- branch-specific agreement analysis
- systematic candidate-retrieval recall evaluation
- comparison with traditional supervised classification baselines
- human evaluation of debate-resolved conflicts

These are extensions rather than requirements for completing the current experiment.

---

## 36. Final Interpretation Boundary

The current research can support conclusions about:

```text
multi-source evidence integration
controlled hierarchical annotation
multi-LLM annotation consistency
path-level disagreement
hierarchy-aware disagreement
consensus formation
LLM-based conflict adjudication
structural dataset integrity
```

It should not claim:

```text
human-level annotation accuracy
objective literary truth
complete independence among all three annotators
universal generalization to all books
```

Maintaining these boundaries keeps the reported conclusions aligned with what the experiment actually measures.