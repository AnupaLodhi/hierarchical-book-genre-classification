import csv
import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


INPUT_FILE = Path("input/isbns_400.csv")
OUTPUT_FILE = Path("data/goodreads_metadata.json")
FAILURE_FILE = Path("data/goodreads_failures.json")

SEARCH_URL = "https://www.goodreads.com/search?q={isbn}"
WAIT_SECONDS = 15
DELAY_SECONDS = 2
MAX_REVIEWS = 5


def clean_text(value):
    if value is None:
        return None

    value = re.sub(r"\s+", " ", str(value)).strip()
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
            isbn = clean_text(row.get("Isbn-13"))

            if isbn:
                isbns.append(isbn)

    return isbns


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def build_driver():
    options = Options()

    # Goodreads is resource-heavy. "none" lets Selenium return
    # without waiting for every image/script/network request.
    options.page_load_strategy = "none"

    options.add_argument("--window-size=1400,1000")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")

    options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"]
    )

    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
    }

    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)

    # Short timeout because fetch_book handles slow pages itself.
    driver.set_page_load_timeout(15)

    return driver


def safe_get(driver, url):
    """
    Navigate without allowing a slow Goodreads page to kill
    the entire ISBN collection.
    """
    try:
        driver.get(url)

    except TimeoutException:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass

    # Wait only for useful HTML to exist.
    try:
        WebDriverWait(driver, 12).until(
            lambda d: len(d.page_source) > 1000
        )
    except TimeoutException:
        pass

def parse_json_ld(soup):
    objects = []

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(data, dict):
            objects.append(data)

        elif isinstance(data, list):
            objects.extend(
                item
                for item in data
                if isinstance(item, dict)
            )

    for obj in objects:
        obj_type = obj.get("@type")

        if obj_type == "Book":
            return obj

        if isinstance(obj.get("@graph"), list):
            for item in obj["@graph"]:
                if (
                    isinstance(item, dict)
                    and item.get("@type") == "Book"
                ):
                    return item

    return {}


def extract_author(book_json, soup):
    authors = []

    author_data = book_json.get("author")

    if isinstance(author_data, dict):
        name = clean_text(author_data.get("name"))
        if name:
            authors.append(name)

    elif isinstance(author_data, list):
        for author in author_data:
            if isinstance(author, dict):
                name = clean_text(author.get("name"))
                if name:
                    authors.append(name)

    if not authors:
        for element in soup.select(
            'a.ContributorLink, a[href*="/author/show/"]'
        ):
            name = clean_text(element.get_text(" ", strip=True))

            if name:
                authors.append(name)

    return unique(authors)


def extract_genres(soup):
    genres = []

    # Only inspect Goodreads' book-specific genre section.
    # Do NOT use a[href*="/genres/"] globally because that
    # also captures Goodreads' site-wide genre navigation.
    selectors = [
        "div.BookPageMetadataSection__genres a",
        "div.BookPageMetadataSection__genreButton a",
        "span.BookPageMetadataSection__genreButton a",
        "div[data-testid='genresList'] a",
    ]

    for selector in selectors:
        for element in soup.select(selector):
            text = clean_text(
                element.get_text(" ", strip=True)
            )

            if text:
                genres.append(text)

    return unique(genres)

def extract_blurb(book_json, soup):
    description = clean_text(
        book_json.get("description")
    )

    if description:
        # JSON-LD descriptions may contain HTML.
        description = BeautifulSoup(
            description,
            "html.parser"
        ).get_text(" ", strip=True)

        return clean_text(description)

    selectors = [
        'div.BookPageMetadataSection__description span.Formatted',
        'div.BookPageMetadataSection__description',
        'div[data-testid="description"]',
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            text = clean_text(
                element.get_text(" ", strip=True)
            )

            if text:
                return text

    return None


def extract_cover(book_json, soup):
    image = book_json.get("image")

    if isinstance(image, str):
        return clean_text(image)

    if isinstance(image, dict):
        return clean_text(
            image.get("url")
            or image.get("contentUrl")
        )

    selectors = [
        'img.ResponsiveImage',
        'img.BookCover__image',
    ]

    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            src = clean_text(element.get("src"))

            if src:
                return src

    return None


def extract_reviews(soup):
    reviews = []

    selectors = [
        'section.ReviewText span.Formatted',
        'div.ReviewText span.Formatted',
        'article.ReviewCard span.Formatted',
    ]

    for selector in selectors:
        for element in soup.select(selector):
            text = clean_text(
                element.get_text(" ", strip=True)
            )

            if (
                text
                and len(text) >= 20
                and text not in reviews
            ):
                reviews.append(text)

                if len(reviews) >= MAX_REVIEWS:
                    return reviews

    return reviews


def extract_details_from_text(soup):
    page_text = clean_text(
        soup.get_text("\n", strip=True)
    ) or ""

    publisher = None
    publication_date = None
    language = None
    pages = None
    physical_format = None

    # Current Goodreads pages often expose edition information
    # in text rather than stable machine-readable fields.
    match = re.search(
        r"First published\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4})",
        page_text,
        flags=re.IGNORECASE,
    )

    if match:
        publication_date = clean_text(match.group(1))

    match = re.search(
        r"(\d{1,5})\s+pages\b",
        page_text,
        flags=re.IGNORECASE,
    )

    if match:
        try:
            pages = int(match.group(1))
        except ValueError:
            pages = None

    # Goodreads visibly exposes edition format next to page count,
    # e.g. "212 pages, Hardcover".
    match = re.search(
        r"\d{1,5}\s+pages\s*,\s*"
        r"(Hardcover|Paperback|Mass Market Paperback|"
        r"Kindle Edition|ebook|Audiobook|Audio CD|"
        r"Library Binding|Board Book)",
        page_text,
        flags=re.IGNORECASE,
    )

    if match:
        physical_format = clean_text(match.group(1))

    # Publisher and language remain None unless Goodreads exposes
    # them in a reliably identifiable book/edition field.
    return {
        "publisher": publisher,
        "date_of_publication": publication_date,
        "language": language,
        "number_of_pages": pages,
        "physical_format": physical_format,
    }


def fetch_book(isbn13, driver):
    search_url = SEARCH_URL.format(isbn=isbn13)

    safe_get(driver, search_url)

    WebDriverWait(
        driver,
        WAIT_SECONDS
    ).until(
        EC.presence_of_element_located(
            (By.TAG_NAME, "body")
        )
    )

    # Goodreads frequently redirects an ISBN search directly
    # to the corresponding book page.
    time.sleep(1)

    current_url = driver.current_url

    if "/book/show/" not in current_url:
        links = driver.find_elements(
            By.CSS_SELECTOR,
            'a[href*="/book/show/"]'
        )

        if not links:
            return None

        target = links[0].get_attribute("href")

        if not target:
            return None

        safe_get(driver, target)

        WebDriverWait(
            driver,
            WAIT_SECONDS
        ).until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "body")
            )
        )

        time.sleep(1)

    soup = BeautifulSoup(
        driver.page_source,
        "html.parser"
    )

    book_json = parse_json_ld(soup)

    title = clean_text(book_json.get("name"))

    if not title:
        heading = soup.select_one("h1")

        if heading:
            title = clean_text(
                heading.get_text(" ", strip=True)
            )

    if not title:
        return None

    authors = extract_author(book_json, soup)
    genres = extract_genres(soup)
    blurb = extract_blurb(book_json, soup)
    cover_url = extract_cover(book_json, soup)
    reviews = extract_reviews(soup)

    details = extract_details_from_text(soup)

    # Country deliberately remains unknown unless Goodreads
    # provides explicit publication-country evidence.
    country = None
    publication_place = []

    return {
        "isbn13": isbn13,
        "title": title,
        "authors": authors,
        "publisher": details["publisher"],
        "country": country,
        "publication_place": publication_place,
        "date_of_publication":
            details["date_of_publication"],
        "language": details["language"],
        "Genre": genres,
        "number_of_pages":
            details["number_of_pages"],
        "physical_format":
            details["physical_format"],
        "source_url": driver.current_url,
        "sources": ["Goodreads"],
        "_cover_url": cover_url,
        "_blurb": blurb,
        "_reviews": reviews,
    }


def main():
    isbns = load_isbns()

    existing = []

    if OUTPUT_FILE.exists():
        try:
            existing = json.load(
                OUTPUT_FILE.open(
                    encoding="utf-8"
                )
            )
        except Exception:
            existing = []

    failures = []

    if FAILURE_FILE.exists():
        try:
            failures = json.load(
                FAILURE_FILE.open(
                    encoding="utf-8"
                )
            )
        except Exception:
            failures = []

    completed = {
        item.get("isbn13")
        for item in existing
        if item.get("isbn13")
    }

    print(f"Loaded ISBNs : {len(isbns)}")
    print(f"Already done : {len(completed)}")
    print("Starting Goodreads collection...\n")

    driver = build_driver()

    try:
        for index, isbn in enumerate(
            isbns,
            start=1
        ):
            if isbn in completed:
                print(
                    f"[{index}/{len(isbns)}] "
                    f"{isbn} -> SKIP"
                )
                continue

            try:
                record = fetch_book(
                    isbn,
                    driver,
                )

                if record is None:
                    failures.append({
                        "isbn13": isbn,
                        "reason":
                            "No Goodreads book record found",
                    })

                    print(
                        f"[{index}/{len(isbns)}] "
                        f"{isbn} -> NOT FOUND"
                    )

                else:
                    existing.append(record)
                    completed.add(isbn)

                    # Remove stale failure if a retry succeeds.
                    failures = [
                        failure
                        for failure in failures
                        if failure.get("isbn13") != isbn
                    ]

                    print(
                        f"[{index}/{len(isbns)}] "
                        f"{isbn} -> "
                        f"{record['title']}"
                    )

                save_json(
                    OUTPUT_FILE,
                    existing,
                )

                save_json(
                    FAILURE_FILE,
                    failures,
                )

            except (
                TimeoutException,
                WebDriverException,
                Exception
            ) as error:
                failures = [
                    failure
                    for failure in failures
                    if failure.get("isbn13") != isbn
                ]

                failures.append({
                    "isbn13": isbn,
                    "reason": str(error),
                })

                save_json(
                    FAILURE_FILE,
                    failures,
                )

                print(
                    f"[{index}/{len(isbns)}] "
                    f"{isbn} -> ERROR: {error}"
                )

            time.sleep(DELAY_SECONDS)

    except KeyboardInterrupt:
        print(
            "\nStopped manually. "
            "Existing progress has been saved."
        )

    finally:
        save_json(
            OUTPUT_FILE,
            existing,
        )

        save_json(
            FAILURE_FILE,
            failures,
        )

        driver.quit()

    print("\n================================")
    print("GOODREADS COLLECTION STOPPED/COMPLETE")
    print("================================")
    print(f"Successful : {len(existing)}")
    print(f"Failures   : {len(failures)}")


if __name__ == "__main__":
    main()
