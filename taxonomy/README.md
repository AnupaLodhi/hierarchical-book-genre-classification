# Taxonomies

This directory contains the controlled taxonomies used by the hierarchical book genre classification pipeline.

## Files

- `genre_hierarchy.json` — hierarchical taxonomy used for book genre classification.
- `metadata_hierarchy.json` — separate hierarchy used for non-genre book metadata.

Genre classification and metadata classification are intentionally maintained as separate taxonomies.

## Genre Hierarchy

The genre taxonomy has two mutually exclusive Level-1 roots:

- `Fiction`
- `Nonfiction`

Downstream annotation must select genre paths from one Level-1 branch for each book.

The taxonomy currently contains paths up to four levels deep.

## Metadata Hierarchy

The metadata taxonomy is rooted at:

`Book_Metadata_Hierarchy`

It represents attributes such as audience, geographical context, language/textual context, format/form, temporal context, themes, representation, narrative/style, content suitability, and publication/series metadata.

Metadata paths are kept separate from genre paths.

## Provenance

The initial taxonomy structure was derived from the reference hierarchical book genre classification project used to guide this implementation.

The working reference annotation pipeline uses:

- `clean_true_book_genre_hierarchy.json`
- `book_genre_metadata_hierarchy.json`

These were adopted under the simplified names used in this repository.

## Controlled Correction

During taxonomy validation, the reference genre hierarchy contained the Level-2 label:

`Fiction / Scince Fiction`

This was corrected to:

`Fiction / Science Fiction`

The descendants and hierarchical structure were otherwise preserved.

## Reproducibility

Taxonomy files are version-controlled so classification experiments can be reproduced against a known classification space.
