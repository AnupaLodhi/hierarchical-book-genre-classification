# Annotation Methodology

## 1. Purpose

The annotation stage converts evidence-supported book tags into controlled hierarchical Genre and Metadata paths.

The system does not allow an LLM to freely invent labels. Annotation is constrained by the reviewed Genre and Metadata taxonomies.

---

## 2. Annotation Pipeline

```text
Filtered Book Evidence
        |
        v
Candidate Taxonomy Retrieval
        |
        v
+----------------------------+
| Independent LLM Annotation |
+----------------------------+
     /       |       \
    v        v        v
  Qwen    GPT-OSS   GPT-OSS
  27B      120B      20B
    \        |        /
     \       |       /
        Validation
            |
            v
  Inter-Annotator Analysis
```

---

## 3. Annotation Evidence

The annotation stage receives evidence produced by the earlier pipeline rather than starting directly from uncontrolled web data.

Important inputs include:

- ISBN
- filtered source tags
- source provenance
- relevant book evidence
- candidate Genre taxonomy paths
- candidate Metadata taxonomy paths

The filtered tags are evidence.

The retrieved taxonomy paths are classification options.

A candidate taxonomy path must not be treated as evidence merely because it was retrieved.

---

## 4. Controlled Genre and Metadata Spaces

Two reviewed taxonomies constrain annotation:

```text
taxonomy/genre_hierarchy.json
taxonomy/metadata_hierarchy.json
```

Genre and Metadata are treated as different annotation dimensions.

Genre describes literary or content classification.

Metadata captures contextual characteristics such as:

- audience
- geography
- language and textual context
- book form
- temporal context
- themes
- character and representation information
- narrative and stylistic information
- content suitability
- series and publication information

The model must select valid taxonomy paths rather than generating arbitrary labels.

---

## 5. Candidate Path Retrieval

The complete taxonomies contain hundreds of hierarchical paths.

For each book, the system retrieves a smaller relevant candidate set using the filtered evidence.

The annotation agent then chooses only from these candidate paths.

This provides two controls:

1. it reduces irrelevant taxonomy choices presented to the model
2. it prevents unrestricted label generation

Candidate retrieval does not itself determine the final annotation.

---

## 6. Annotation Configurations

The current experiment uses three annotation configurations:

| Configuration | Provider | Model |
|---|---|---|
| `qwen_groq` | Groq | `qwen/qwen3.8-27b` |
| `gpt_oss_groq` | Groq | `openai/gpt-oss-120b` |
| `gpt_oss_20b` | Groq | `openai/gpt-oss-20b` |

These are three annotation configurations but two model families:

- Qwen
- GPT-OSS

The 120B and 20B GPT-OSS models must therefore not be described as two independent model families.

---

## 7. Independent Annotation

Each configuration performs the annotation task independently.

One annotator's output is not supplied to another annotator during the initial annotation stage.

This prevents later annotators from simply copying an earlier annotation.

Each model returns:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

The individual outputs are preserved so that inter-annotator agreement can be measured later.

---

## 8. Closed-Taxonomy Annotation

The annotation task is closed-taxonomy classification.

A successful annotation must use paths from the reviewed taxonomies.

For example:

```text
Fiction / Literary Fiction / Short Form Literary Fiction / Short Fiction
```

is acceptable only if that exact path exists in the active Genre taxonomy and was available in the candidate set.

The model cannot create a new path such as:

```text
Fiction / Emotional Books / Sad Short Story
```

if that path does not exist in the controlled taxonomy.

---

## 9. Strict Structured Output

The required model response contains exactly the annotation dimensions:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

The parser rejects responses that are:

- truncated
- malformed
- missing required keys
- using incorrect data types
- otherwise incompatible with the expected annotation schema

This prevents free-form LLM text from silently entering the research dataset.

---

## 10. Valid Abstention

The system permits a model to return:

```json
{
  "genre_paths": [],
  "metadata_paths": []
}
```

when the available evidence does not justify a controlled annotation.

This is a valid abstention.

Abstention is preferable to fabricating an unsupported taxonomy path.

---

## 11. Taxonomy Validation

After parsing, the system validates the selected paths.

The validator checks that:

- every Genre path exists in the Genre taxonomy
- every Metadata path exists in the Metadata taxonomy
- selected paths belong to the allowed candidate paths
- contradictory Fiction and Nonfiction assignments are not accepted

Therefore a syntactically valid JSON response can still be rejected if its taxonomy assignments are invalid.

---

## 12. Evidence Safeguards

Several safeguards reduce unsupported inference.

### Geographical Context

Geographical Metadata should represent the setting or content context of the book.

It must not be inferred solely from:

- author nationality
- publication country
- publisher
- ISBN origin
- language
- source categories such as "American Short stories"

### Temporal Context

Temporal Metadata requires supporting evidence.

A Historical Fiction label alone must not automatically produce a specific historical period.

### Character Metadata

Character-related Metadata must describe characters represented in the work.

Bibliographic information about the author must not be converted into character Metadata.

---

## 13. Fiction and Nonfiction Constraint

The annotation validator checks for contradictory simultaneous Fiction and Nonfiction classification.

This provides an additional consistency safeguard before annotations enter agreement analysis.

---

## 14. Checkpointing

Annotation results are stored incrementally in:

```text
results/annotations/multi_llm_annotations.json
```

Successful annotations are checkpointed.

When the pipeline is restarted, already successful annotations from the same configured provider/model can be preserved rather than unnecessarily regenerated.

Failed requests remain retryable.

This is particularly important for large experiments using rate-limited external APIs.

---

## 15. Provider Failure Handling

External API failure is treated separately from semantic model behavior.

Examples include:

- HTTP 429 rate limits
- provider capacity errors
- connection failures
- blank provider responses

These are recorded as annotation errors.

They are not counted as model disagreement.

---

## 16. Daily Quota Protection

The annotation runner detects confirmed daily token-quota exhaustion.

When one model reaches its daily token quota, that configuration is paused for the remainder of the current execution.

Other configurations may continue independently.

This prevents the pipeline from repeatedly sending requests that are already known to fail because of quota exhaustion.

Previously successful annotations remain checkpointed.

---

## 17. Annotation Status Interpretation

The following states are semantically different:

```text
success
no_filtered_tags
valid empty annotation
provider/API error
malformed response
taxonomy validation failure
```

They must not be collapsed into a single unsuccessful category when evaluating the experiment.

---

## 18. Inter-Annotator Evaluation Boundary

Only successful model outputs can contribute to semantic agreement calculations.

For example:

```text
Qwen       = success
GPT-OSS120 = success
GPT-OSS20  = API error
```

provides two available successful annotations.

It does not represent a three-model disagreement.

Similarly:

```text
Qwen       = success
GPT-OSS120 = success
GPT-OSS20  = success
```

is eligible for genuine three-configuration agreement analysis.

Detailed inter-annotator metrics are documented separately in:

```text
docs/04_inter_annotator_agreement.md
```

---

## 19. Annotation Versus Adjudication

Initial annotation and conflict resolution are deliberately separated.

The three configured annotators first produce independent outputs.

Only after agreement analysis are genuine conflicts sent to the debate resolver.

Therefore:

```text
Initial annotators
= independent annotation configurations

Debate resolver
= adjudicator
```

The debate resolver must not be counted as a fourth independent annotation vote.

---

## 20. Reproducibility Information

For every annotation configuration, the pipeline records information such as:

- configuration name
- provider
- actual model identifier
- status
- Genre paths
- Metadata paths
- error information when applicable

Actual model identifiers must be reported.

A substituted model must never be presented under the name of a different model.

---

## 21. Methodological Limitation

The current configuration contains three annotators but only two model families because both GPT-OSS configurations belong to the GPT-OSS family.

Therefore the experiment can measure agreement among three annotation configurations, but it must not claim agreement among three fully independent model families.

This limitation is reported explicitly rather than hidden.

---

## 22. Core Annotation Principle

The annotation methodology follows this rule:

> Evidence determines whether a classification is supportable; the taxonomy determines how that supported classification is represented.

The LLM therefore acts as a constrained annotator rather than an unrestricted genre generator.