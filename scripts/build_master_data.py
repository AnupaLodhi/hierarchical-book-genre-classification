import csv
import html
import json
import re
from pathlib import Path


INPUT_FILE = Path("input/isbns_400.csv")

OPENLIBRARY_FILE = Path("data/openlibrary_metadata.json")
GOODREADS_FILE = Path("data/goodreads_metadata.json")
AMAZON_FILE = Path("data/amazon_metadata.json")

OUTPUT_FILE = Path("data/master_data.json")


def load_json(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def clean_text(value):
    if value is None:
        return None

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value).strip()

    return value or None


def unique(values):
    result = []
    seen = set()

    for value in values:
        value = clean_text(value)

        if not value:
            continue

        key = value.casefold()

        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


def load_input_isbns():
    with INPUT_FILE.open(
        encoding="utf-8-sig",
        newline=""
    ) as f:

        return [
            row["Isbn-13"].strip()
            for row in csv.DictReader(f)
            if row.get("Isbn-13")
        ]


def index_records(records):
    return {
        record["isbn13"]: record
        for record in records
    }


def first_value(records, field):
    for record in records:
        if not record:
            continue

        value = record.get(field)

        if value not in (None, "", [], {}):
            return value

    return None



def first_list(records, field):
    """
    Return the first non-empty list-valued field according
    to the supplied source-priority order.

    This is used for canonical metadata such as authors and
    publication_place. Raw values from every source remain
    preserved separately in source_metadata.
    """
    for record in records:
        if not record:
            continue

        value = record.get(field)

        if isinstance(value, list):
            cleaned = unique(value)
            if cleaned:
                return cleaned

        elif value:
            cleaned = clean_text(value)
            if cleaned:
                return [cleaned]

    return []


def merge_lists(records, field):
    values = []

    for record in records:
        if not record:
            continue

        value = record.get(field)

        if isinstance(value, list):
            values.extend(value)

        elif value:
            values.append(value)

    return unique(values)


def collect_blurbs(source_records):
    blurbs = []

    for source, record in source_records.items():
        if not record:
            continue

        text = clean_text(
            record.get("_blurb")
        )

        if text:
            blurbs.append({
                "source": source,
                "text": text
            })

    return blurbs


def collect_reviews(source_records):
    reviews = []

    for source, record in source_records.items():
        if not record:
            continue

        for review in record.get("_reviews", []):
            review = clean_text(review)

            if review:
                reviews.append({
                    "source": source,
                    "text": review
                })

    return reviews


def collect_genres(source_records):
    result = {}

    for source, record in source_records.items():

        if not record:
            result[source] = []
            continue

        result[source] = unique(
            record.get("Genre", [])
        )

    return result


def build_master_record(
    isbn,
    ol,
    gr,
    am
):
    sources = {
        "OpenLibrary": ol,
        "Goodreads": gr,
        "Amazon": am,
    }

    available_sources = [
        source
        for source, record in sources.items()
        if record is not None
    ]

    # Selection order is deliberate:
    #
    # Open Library is strongest for bibliographic fields.
    # Goodreads/Amazon complement missing edition/text fields.
    #
    # Raw source values are retained below, so this selection
    # never destroys provenance.

    bibliographic_order = [
        ol,
        gr,
        am,
    ]

    title = clean_text(
        first_value(
            bibliographic_order,
            "title"
        )
    )

    authors = first_list(
        bibliographic_order,
        "authors"
    )

    publisher = clean_text(
        first_value(
            bibliographic_order,
            "publisher"
        )
    )

    # Country is selected only from explicit/defensible
    # bibliographic evidence. Goodreads and Amazon currently
    # intentionally contain no inferred country values.
    country = clean_text(
        first_value(
            bibliographic_order,
            "country"
        )
    )

    publication_place = first_list(
        bibliographic_order,
        "publication_place"
    )

    publication_date = clean_text(
        first_value(
            bibliographic_order,
            "date_of_publication"
        )
    )

    language = clean_text(
        first_value(
            bibliographic_order,
            "language"
        )
    )

    pages = first_value(
        bibliographic_order,
        "number_of_pages"
    )

    physical_format = clean_text(
        first_value(
            bibliographic_order,
            "physical_format"
        )
    )

    cover_url = clean_text(
        first_value(
            [gr, am, ol],
            "_cover_url"
        )
    )

    genre_evidence = collect_genres(
        sources
    )

    blurbs = collect_blurbs(
        sources
    )

    reviews = collect_reviews(
        sources
    )

    return {
        "isbn13": isbn,

        "available_sources":
            available_sources,

        "source_count":
            len(available_sources),

        "cleaned_metadata": {
            "title": title,
            "authors": authors,
            "publisher": publisher,
            "country": country,
            "publication_place":
                publication_place,
            "date_of_publication":
                publication_date,
            "language": language,
            "number_of_pages": pages,
            "physical_format":
                physical_format,
            "_cover_url": cover_url,
        },

        "genre_evidence":
            genre_evidence,

        "text_evidence": {
            "blurbs": blurbs,
            "reviews": reviews,
        },

        "source_metadata":
            sources,

        "provenance": {
            "title":
                first_source_with_value(
                    sources,
                    "title"
                ),

            "publisher":
                first_source_with_value(
                    sources,
                    "publisher"
                ),

            "country":
                first_source_with_value(
                    sources,
                    "country"
                ),

            "date_of_publication":
                first_source_with_value(
                    sources,
                    "date_of_publication"
                ),

            "language":
                first_source_with_value(
                    sources,
                    "language"
                ),

            "number_of_pages":
                first_source_with_value(
                    sources,
                    "number_of_pages"
                ),

            "physical_format":
                first_source_with_value(
                    sources,
                    "physical_format"
                ),

            "_cover_url":
                first_source_with_value_ordered(
                    [
                        ("Goodreads", gr),
                        ("Amazon", am),
                        ("OpenLibrary", ol),
                    ],
                    "_cover_url"
                ),
        }
    }


def first_source_with_value(
    sources,
    field
):
    for source in [
        "OpenLibrary",
        "Goodreads",
        "Amazon",
    ]:
        record = sources.get(source)

        if not record:
            continue

        value = record.get(field)

        if value not in (
            None,
            "",
            [],
            {}
        ):
            return source

    return None


def first_source_with_value_ordered(
    source_records,
    field
):
    for source, record in source_records:

        if not record:
            continue

        value = record.get(field)

        if value not in (
            None,
            "",
            [],
            {}
        ):
            return source

    return None


def main():
    isbns = load_input_isbns()

    ol = index_records(
        load_json(
            OPENLIBRARY_FILE
        )
    )

    gr = index_records(
        load_json(
            GOODREADS_FILE
        )
    )

    am = index_records(
        load_json(
            AMAZON_FILE
        )
    )

    master = []

    for isbn in isbns:

        record = build_master_record(
            isbn,
            ol.get(isbn),
            gr.get(isbn),
            am.get(isbn),
        )

        master.append(record)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            master,
            f,
            indent=2,
            ensure_ascii=False
        )

    print("\n================================")
    print("MASTER DATASET CREATED")
    print("================================")

    print(
        "Books       :",
        len(master)
    )

    print(
        "3 sources   :",
        sum(
            x["source_count"] == 3
            for x in master
        )
    )

    print(
        "2 sources   :",
        sum(
            x["source_count"] == 2
            for x in master
        )
    )

    print(
        "1 source    :",
        sum(
            x["source_count"] == 1
            for x in master
        )
    )

    print(
        "Output      :",
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()
