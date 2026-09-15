import csv
import json
import time
from pathlib import Path

import requests


INPUT_FILE = Path("input/isbns_400.csv")
OUTPUT_FILE = Path("data/openlibrary_metadata.json")
FAILURE_FILE = Path("data/openlibrary_failures.json")

OPENLIBRARY = "https://openlibrary.org"
BOOKS_API = f"{OPENLIBRARY}/api/books"

REQUEST_TIMEOUT = 20
DELAY_SECONDS = 0.5


# Only explicit publication-place normalization.
# This is NOT based on language, author nationality, ISBN prefix,
# publisher identity, website domain, or storefront.
PLACE_TO_COUNTRY = {
    "new york": "United States",
    "new york, n.y.": "United States",
    "new york, ny": "United States",
    "boston": "United States",
    "chicago": "United States",
    "san francisco": "United States",
    "london": "United Kingdom",
    "oxford": "United Kingdom",
    "cambridge": "United Kingdom",
    "toronto": "Canada",
    "montreal": "Canada",
    "new delhi": "India",
    "delhi": "India",
    "mumbai": "India",
    "bombay": "India",
    "kolkata": "India",
    "calcutta": "India",
    "chennai": "India",
    "madras": "India",
}


def clean_text(value):
    if value is None:
        return None

    if isinstance(value, str):
        value = " ".join(value.split())
        return value or None

    return value


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


def extract_description(value):
    if isinstance(value, str):
        return clean_text(value)

    if isinstance(value, dict):
        return clean_text(value.get("value"))

    return None


def extract_names(items):
    if not isinstance(items, list):
        return []

    names = []

    for item in items:
        if isinstance(item, dict):
            name = clean_text(item.get("name"))

            if name:
                names.append(name)

        elif isinstance(item, str):
            item = clean_text(item)

            if item:
                names.append(item)

    return unique(names)


def extract_keys(items):
    if not isinstance(items, list):
        return []

    keys = []

    for item in items:
        if isinstance(item, dict):
            key = clean_text(item.get("key"))

            if key:
                keys.append(key)

    return unique(keys)


def normalize_language(value):
    if not value:
        return None

    mapping = {
        "eng": "English",
        "fre": "French",
        "fra": "French",
        "ger": "German",
        "deu": "German",
        "spa": "Spanish",
        "ita": "Italian",
        "hin": "Hindi",
        "jpn": "Japanese",
        "kor": "Korean",
        "chi": "Chinese",
        "zho": "Chinese",
    }

    return mapping.get(value.lower(), value)


def country_from_publication_places(places):
    """
    Derive country only from an explicit bibliographic publication place.

    Example:
        publication_place = "New York"
        country = "United States"

    This is geographic normalization of an explicit publication-place
    field, NOT inference from language, author nationality, ISBN prefix,
    publisher, domain, or storefront.

    Unknown/ambiguous places remain None.
    """
    for place in places:
        normalized = clean_text(place)

        if not normalized:
            continue

        key = normalized.casefold().strip(" .")

        if key in PLACE_TO_COUNTRY:
            return PLACE_TO_COUNTRY[key]

        # Handle strings such as "New York : Harper & Row"
        for known_place, country in PLACE_TO_COUNTRY.items():
            if key.startswith(known_place + " :"):
                return country

    return None


def request_json(session, url, params=None):
    response = session.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()
    return response.json()


def get_work_data(session, work_key):
    if not work_key:
        return {}

    try:
        return request_json(
            session,
            f"{OPENLIBRARY}{work_key}.json",
        )
    except (requests.RequestException, ValueError):
        return {}


def get_author_name(session, author_key):
    if not author_key:
        return None

    try:
        data = request_json(
            session,
            f"{OPENLIBRARY}{author_key}.json",
        )

        return clean_text(data.get("name"))

    except (requests.RequestException, ValueError):
        return None


def get_edition_data(session, edition_key):
    if not edition_key:
        return {}

    try:
        return request_json(
            session,
            f"{OPENLIBRARY}{edition_key}.json",
        )

    except (requests.RequestException, ValueError):
        return {}


def fetch_book(isbn13, session):
    # ---------------------------------------------------------
    # 1. Books API: convenient bibliographic representation
    # ---------------------------------------------------------
    payload = request_json(
        session,
        BOOKS_API,
        params={
            "bibkeys": f"ISBN:{isbn13}",
            "format": "json",
            "jscmd": "data",
        },
    )

    api_key = f"ISBN:{isbn13}"

    if api_key not in payload:
        return None

    book = payload[api_key]

    title = clean_text(book.get("title"))

    authors = extract_names(book.get("authors"))
    publishers = extract_names(book.get("publishers"))

    publisher = publishers[0] if publishers else None

    pub_date = clean_text(book.get("publish_date"))

    publication_places = extract_names(
        book.get("publish_places")
    )

    # ---------------------------------------------------------
    # 2. Find edition record
    # ---------------------------------------------------------
    edition_key = None

    identifiers = book.get("identifiers", {})

    olid_values = identifiers.get("openlibrary", [])

    if isinstance(olid_values, list) and olid_values:
        edition_key = f"/books/{olid_values[0]}"

    # API URL can also contain the edition identifier.
    if not edition_key:
        source_url = clean_text(book.get("url"))

        if source_url and "/books/" in source_url:
            edition_key = "/" + source_url.split(
                OPENLIBRARY + "/",
                1
            )[-1]

            edition_key = edition_key.split("?")[0]

    edition = get_edition_data(session, edition_key)

    # ---------------------------------------------------------
    # 3. Edition-level fields
    # ---------------------------------------------------------
    number_of_pages = edition.get("number_of_pages")

    physical_format = clean_text(
        edition.get("physical_format")
    )

    if not publication_places:
        edition_places = edition.get("publish_places", [])

        if isinstance(edition_places, list):
            publication_places = unique(edition_places)

    if not pub_date:
        pub_date = clean_text(
            edition.get("publish_date")
        )

    if not publisher:
        edition_publishers = edition.get("publishers", [])

        if isinstance(edition_publishers, list):
            edition_publishers = unique(
                edition_publishers
            )

            publisher = (
                edition_publishers[0]
                if edition_publishers
                else None
            )

    # ---------------------------------------------------------
    # 4. Language
    # ---------------------------------------------------------
    language_values = []

    languages = edition.get("languages", [])

    if isinstance(languages, list):
        for language in languages:
            if not isinstance(language, dict):
                continue

            key = clean_text(language.get("key"))

            if key:
                code = key.rsplit("/", 1)[-1]
                language_values.append(
                    normalize_language(code)
                )

    if not language_values:
        api_languages = extract_names(
            book.get("languages")
        )

        language_values.extend(api_languages)

    language_values = unique(language_values)

    if len(language_values) == 1:
        language = language_values[0]
    elif language_values:
        language = language_values
    else:
        language = None

    # ---------------------------------------------------------
    # 5. Work record
    # ---------------------------------------------------------
    work_keys = extract_keys(
        edition.get("works", [])
    )

    work_key = work_keys[0] if work_keys else None
    work = get_work_data(session, work_key)

    # ---------------------------------------------------------
    # 6. Authors fallback
    # ---------------------------------------------------------
    if not authors:
        author_keys = extract_keys(
            edition.get("authors", [])
        )

        author_names = []

        for author_key in author_keys:
            name = get_author_name(
                session,
                author_key,
            )

            if name:
                author_names.append(name)

        authors = unique(author_names)

    # ---------------------------------------------------------
    # 7. Genre / subjects
    # ---------------------------------------------------------
    genres = []

    work_subjects = work.get("subjects", [])

    if isinstance(work_subjects, list):
        genres.extend(work_subjects)

    edition_subjects = edition.get("subjects", [])

    if isinstance(edition_subjects, list):
        genres.extend(edition_subjects)

    api_subjects = extract_names(
        book.get("subjects")
    )

    genres.extend(api_subjects)
    genres = unique(genres)

    # ---------------------------------------------------------
    # 8. REAL blurb/description
    #
    # Work description is preferred.
    # Edition "notes" are deliberately NOT used as the blurb,
    # because notes may contain bibliographic statements such as
    # "An Ursula Nordstrom book."
    # ---------------------------------------------------------
    blurb = extract_description(
        work.get("description")
    )

    if not blurb:
        blurb = extract_description(
            edition.get("description")
        )

    # ---------------------------------------------------------
    # 9. Cover
    # ---------------------------------------------------------
    cover_url = None

    covers = edition.get("covers", [])

    if isinstance(covers, list) and covers:
        cover_id = covers[0]

        if isinstance(cover_id, int) and cover_id > 0:
            cover_url = (
                f"https://covers.openlibrary.org/"
                f"b/id/{cover_id}-L.jpg"
            )

    if not cover_url:
        cover_data = book.get("cover")

        if isinstance(cover_data, dict):
            cover_url = clean_text(
                cover_data.get("large")
                or cover_data.get("medium")
                or cover_data.get("small")
            )

    # ---------------------------------------------------------
    # 10. Publication country
    # ---------------------------------------------------------
    country = country_from_publication_places(
        publication_places
    )

    # ---------------------------------------------------------
    # 11. Source URL
    # ---------------------------------------------------------
    source_url = clean_text(book.get("url"))

    if source_url and source_url.startswith("http://"):
        source_url = "https://" + source_url[len("http://"):]

    # ---------------------------------------------------------
    # 12. Reviews
    #
    # Open Library does not provide genuine review text through
    # the metadata endpoints used here. Do not fabricate it.
    # ---------------------------------------------------------
    reviews = []

    return {
        "isbn13": isbn13,
        "title": title,
        "authors": authors,
        "publisher": publisher,
        "country": country,
        "publication_place": publication_places,
        "date_of_publication": pub_date,
        "language": language,
        "Genre": genres,
        "number_of_pages": number_of_pages,
        "physical_format": physical_format,
        "source_url": source_url,
        "sources": ["OpenLibrary"],
        "_cover_url": cover_url,
        "_blurb": blurb,
        "_reviews": reviews,
    }


def load_isbns():
    isbns = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        if (
            not reader.fieldnames
            or "Isbn-13" not in reader.fieldnames
        ):
            raise ValueError(
                "Expected CSV column 'Isbn-13'. "
                f"Found: {reader.fieldnames}"
            )

        for row in reader:
            isbn = clean_text(
                row.get("Isbn-13")
            )

            if isbn:
                isbns.append(isbn)

    return isbns


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main():
    isbns = load_isbns()

    print(
        f"Loaded {len(isbns)} ISBNs."
    )
    print(
        "Starting Open Library collection...\n"
    )

    results = []
    failures = []

    session = requests.Session()

    session.headers.update({
        "User-Agent":
            "HierarchicalBookGenreResearch/1.0 "
            "(academic metadata research)"
    })

    for index, isbn in enumerate(
        isbns,
        start=1
    ):
        try:
            record = fetch_book(
                isbn,
                session,
            )

            if record is None:
                failures.append({
                    "isbn13": isbn,
                    "reason":
                        "No Open Library record found",
                })

                print(
                    f"[{index}/{len(isbns)}] "
                    f"{isbn} -> NOT FOUND"
                )

            else:
                results.append(record)

                print(
                    f"[{index}/{len(isbns)}] "
                    f"{isbn} -> "
                    f"{record['title'] or 'NO TITLE'}"
                )

        except requests.RequestException as error:
            failures.append({
                "isbn13": isbn,
                "reason": str(error),
            })

            print(
                f"[{index}/{len(isbns)}] "
                f"{isbn} -> REQUEST ERROR: "
                f"{error}"
            )

        except Exception as error:
            failures.append({
                "isbn13": isbn,
                "reason": str(error),
            })

            print(
                f"[{index}/{len(isbns)}] "
                f"{isbn} -> ERROR: {error}"
            )

        # Save continuously so an interrupted run
        # does not destroy already collected results.
        save_json(
            OUTPUT_FILE,
            results,
        )

        save_json(
            FAILURE_FILE,
            failures,
        )

        time.sleep(DELAY_SECONDS)

    print("\n================================")
    print("OPEN LIBRARY COMPLETE")
    print("================================")
    print(f"Successful : {len(results)}")
    print(f"Failed     : {len(failures)}")
    print(f"Metadata   : {OUTPUT_FILE}")
    print(f"Failures   : {FAILURE_FILE}")


if __name__ == "__main__":
    main()
