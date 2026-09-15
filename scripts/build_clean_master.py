import csv
import html
import json
import re
from pathlib import Path

INPUT = Path("data/master_data.json")
OUTPUT = Path("data/clean_master_data.csv")


def clean_text(value):
    if value is None:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def join_values(values, sep=" | "):
    if not values:
        return ""

    seen = set()
    result = []

    for value in values:
        value = clean_text(value)

        if not value:
            continue

        key = value.casefold()

        if key not in seen:
            seen.add(key)
            result.append(value)

    return sep.join(result)


with INPUT.open("r", encoding="utf-8") as f:
    books = json.load(f)


rows = []

for book in books:

    meta = book.get("cleaned_metadata", {})
    genres = book.get("genre_evidence", {})
    text = book.get("text_evidence", {})

    blurbs = text.get("blurbs", [])
    reviews = text.get("reviews", [])

    row = {
        "isbn13": book.get("isbn13", ""),

        "title": clean_text(meta.get("title")),

        "authors": join_values(
            meta.get("authors", [])
        ),

        "publisher": clean_text(
            meta.get("publisher")
        ),

        "country": clean_text(
            meta.get("country")
        ),

        "publication_place": join_values(
            meta.get("publication_place", [])
        ),

        "date_of_publication": clean_text(
            meta.get("date_of_publication")
        ),

        "language": clean_text(
            meta.get("language")
        ),

        "number_of_pages": clean_text(
            meta.get("number_of_pages")
        ),

        "physical_format": clean_text(
            meta.get("physical_format")
        ),

        "openlibrary_genres": join_values(
            genres.get("OpenLibrary", [])
        ),

        "goodreads_genres": join_values(
            genres.get("Goodreads", [])
        ),

        "amazon_genres": join_values(
            genres.get("Amazon", [])
        ),

        "blurbs": join_values([
            x.get("text", "")
            for x in blurbs
            if isinstance(x, dict)
        ]),

        "reviews": join_values([
            x.get("text", "")
            for x in reviews
            if isinstance(x, dict)
        ]),

        "available_sources": join_values(
            book.get("available_sources", [])
        ),

        "source_count": book.get(
            "source_count", 0
        ),
    }

    rows.append(row)


fieldnames = [
    "isbn13",
    "title",
    "authors",
    "publisher",
    "country",
    "publication_place",
    "date_of_publication",
    "language",
    "number_of_pages",
    "physical_format",
    "openlibrary_genres",
    "goodreads_genres",
    "amazon_genres",
    "blurbs",
    "reviews",
    "available_sources",
    "source_count",
]


OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(rows)


print("=" * 55)
print("CLEAN MASTER DATASET CREATED")
print("=" * 55)

print("Books              :", len(rows))
print(
    "With OL genres     :",
    sum(bool(x["openlibrary_genres"]) for x in rows)
)
print(
    "With GR genres     :",
    sum(bool(x["goodreads_genres"]) for x in rows)
)
print(
    "With Amazon genres :",
    sum(bool(x["amazon_genres"]) for x in rows)
)
print(
    "With blurbs        :",
    sum(bool(x["blurbs"]) for x in rows)
)
print(
    "With reviews       :",
    sum(bool(x["reviews"]) for x in rows)
)
print("Output             :", OUTPUT)
