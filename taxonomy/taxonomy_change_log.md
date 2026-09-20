# Mentor Taxonomy Processing Log

## Source Files

The active taxonomies were derived from the mentor-reviewed files:

- `taxonomy/reviewed/genre_hierarchy_mentor_original.json`
- `taxonomy/reviewed/metadata_hierarchy_mentor_original.json`

Original mentor files are preserved unchanged.

### Original SHA-1

Genre:
`93b97ae403afb0433b824d87485321929984dd7d`

Metadata:
`83deabfdf1e66165fb4a444d2bd9013127a54027`

## Active Machine-Readable Files

- `taxonomy/genre_hierarchy.json`
- `taxonomy/metadata_hierarchy.json`

These are cleaned derivatives of the preserved mentor-reviewed originals.

## Mechanical Cleaning

The cleaning script:

`scripts/clean_mentor_taxonomies.py`

performs the following mechanical operations:

- removes `[RM#]` review markers
- removes inline `///` reviewer comments
- removes broken replacement characters (`�`)
- normalizes curly apostrophes
- repairs invalid trailing commas
- repairs the malformed `"Indo-Pacific".` punctuation
- parses the first complete JSON object when reviewer notes occur after the JSON structure

## Genre Decisions

### Historical Fiction

Time-period labels were removed from the Genre hierarchy:

- Ancient Historical Fiction
- Medieval Historical Fiction
- Early Modern Historical Fiction
- Modern Historical Fiction

Historical Adventure Fiction, Historical Speculative Fiction, and
Biographical Historical Fiction remain genre branches.

Temporal information is represented in Metadata instead.

### Information Studies

`Information Studies` was removed from:

`Nonfiction / Reference and Knowledge Organization / Library and Information Studies`

following the mentor inline review indicating that it should not be treated as a genre.

### Writing Studies

`Writing Studies` is retained because the mentor review raised a question
about its placement but did not provide a final removal decision.

## Metadata Decisions

### Geographical Context

Geographical Context represents the geographical setting/place of the
story or content.

It must not be inferred from:

- author nationality
- publication country
- publisher
- ISBN origin
- language
- bookstore/source domain

### Character Metadata

`Role_Profile` represents roles of characters in the story.

`Group_Profile` represents groups of characters represented in the text.

### Interactive Ebook

`Interactive Ebook` was removed following mentor feedback.

### Temporal Context

The previous `Historical_Period` structure was removed.

The mentor-proposed temporal structure was introduced using:

- `Global_Time_Frame`
- `Regional_Historical_Eras`

Regional historical eras currently include:

- Indian History
- European and British History
- East Asian History

### Central America

An empty string entry under Central America was removed.

The label `Missoure` is retained unchanged because its intended meaning
cannot be determined safely from the mentor file. It requires manual
review rather than silent correction.

## Annotation Safeguards

The annotation agent uses the cleaned taxonomies as closed label spaces.

The agent:

- cannot invent taxonomy paths
- may select only retrieved candidate paths
- cannot classify a book as both Fiction and Nonfiction
- uses filtered source tags as evidence
- treats candidate paths as options rather than evidence
- does not infer geographical context from nationality-style labels
- requires explicit evidence for temporal metadata
- interprets Role_Profile and Group_Profile according to mentor clarification

Candidate retrieval uses evidence-aware Fiction/Nonfiction root pruning.

If root evidence cannot be determined safely, both roots remain available
rather than forcing a classification.

## Reproducibility

The preserved mentor files are the immutable source material.

The active JSON taxonomies are reproducible by running:

`python -m scripts.clean_mentor_taxonomies`

Any future taxonomy modification should be documented in this file before
a new annotation experiment is started.
