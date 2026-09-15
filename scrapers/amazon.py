import csv
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options


INPUT_FILE = Path("input/isbns_400.csv")
OUTPUT_FILE = Path("data/amazon_metadata.json")
FAILURE_FILE = Path("data/amazon_failures.json")

BASE_URL = "https://www.amazon.com"
SEARCH_URL = BASE_URL + "/s?k={isbn}&i=stripbooks"

DELAY_SECONDS = 2.5
MAX_REVIEWS = 5


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


def load_isbns():
    result = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        if (
            not reader.fieldnames
            or "Isbn-13" not in reader.fieldnames
        ):
            raise ValueError(
                f"Expected Isbn-13 column. Found: {reader.fieldnames}"
            )

        for row in reader:
            isbn = clean_text(row.get("Isbn-13"))

            if isbn:
                result.append(isbn)

    return result


def save_json(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def build_driver():
    options = Options()

    # Amazon pages contain many slow resources.
    # We do not need to wait for all of them.
    options.page_load_strategy = "none"

    options.add_argument(
        "--window-size=1400,1000"
    )

    options.add_argument(
        "--disable-notifications"
    )

    options.add_argument(
        "--disable-popup-blocking"
    )

    options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"]
    )

    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
    }

    options.add_experimental_option(
        "prefs",
        prefs
    )

    driver = webdriver.Chrome(
        options=options
    )

    driver.set_page_load_timeout(15)

    return driver


def safe_get(driver, url, wait=4):
    try:
        driver.get(url)

    except TimeoutException:
        try:
            driver.execute_script(
                "window.stop();"
            )
        except Exception:
            pass

    time.sleep(wait)


def is_blocked(soup):
    text = clean_text(
        soup.get_text(
            " ",
            strip=True
        )
    ) or ""

    indicators = [
        "enter the characters you see below",
        "sorry, we just need to make sure you're not a robot",
        "type the characters you see in this image",
    ]

    lower = text.casefold()

    return any(
        indicator in lower
        for indicator in indicators
    )


def find_product_url(isbn, driver):
    url = SEARCH_URL.format(
        isbn=quote_plus(isbn)
    )

    safe_get(driver, url)

    soup = BeautifulSoup(
        driver.page_source,
        "html.parser"
    )

    if is_blocked(soup):
        raise RuntimeError(
            "Amazon verification/CAPTCHA encountered"
        )

    candidates = []

    for result in soup.select(
        'div[data-component-type="s-search-result"]'
    ):
        link = result.select_one(
            'h2 a[href*="/dp/"], '
            'a.a-link-normal[href*="/dp/"]'
        )

        if not link:
            continue

        href = link.get("href")

        if not href:
            continue

        if href.startswith("/"):
            href = BASE_URL + href

        candidates.append(
            href.split("?")[0]
        )

    candidates = unique(candidates)

    if not candidates:
        return None

    return candidates[0]


def parse_byline(soup):
    authors = []

    selectors = [
        "#bylineInfo a.contributorNameID",
        "#bylineInfo a.a-link-normal",
        ".author a.a-link-normal",
    ]

    for selector in selectors:
        for element in soup.select(selector):

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if not text:
                continue

            if text.casefold() in {
                "visit amazon's store",
                "follow",
            }:
                continue

            authors.append(text)

    return unique(authors)


def extract_title(soup):
    selectors = [
        "#productTitle",
        "#ebooksProductTitle",
        "h1 span",
    ]

    for selector in selectors:
        element = soup.select_one(
            selector
        )

        if element:
            value = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if value:
                return value

    return None


def extract_cover(soup):
    selectors = [
        "#imgBlkFront",
        "#landingImage",
        "#ebooksImgBlkFront",
    ]

    for selector in selectors:
        image = soup.select_one(
            selector
        )

        if not image:
            continue

        for attr in [
            "data-old-hires",
            "data-a-dynamic-image",
            "src",
        ]:
            value = image.get(attr)

            if not value:
                continue

            if attr == "data-a-dynamic-image":
                try:
                    images = json.loads(
                        value
                    )

                    if images:
                        return next(
                            iter(images.keys())
                        )

                except Exception:
                    pass

            else:
                value = clean_text(value)

                if value:
                    return value

    return None


def extract_description(soup):
    selectors = [
        "#bookDescription_feature_div",
        "#bookDescription_feature_div noscript",
        "#productDescription",
        "#productDescription_feature_div",
        "#aplus",
    ]

    for selector in selectors:
        element = soup.select_one(
            selector
        )

        if not element:
            continue

        text = clean_text(
            element.get_text(
                " ",
                strip=True
            )
        )

        if text and len(text) >= 30:
            return text

    return None


def product_details(soup):
    details = {}

    selectors = [
        "#detailBullets_feature_div li",
        "#productDetailsTable tr",
        "#productDetails_detailBullets_sections1 tr",
        "#productDetails_techSpec_section_1 tr",
    ]

    for selector in selectors:

        for row in soup.select(
            selector
        ):

            text = clean_text(
                row.get_text(
                    " ",
                    strip=True
                )
            )

            if not text:
                continue

            if ":" in text:
                key, value = text.split(
                    ":",
                    1
                )

                key = clean_text(key)
                value = clean_text(value)

            else:
                th = row.find("th")
                td = row.find("td")

                if not th or not td:
                    continue

                key = clean_text(
                    th.get_text(
                        " ",
                        strip=True
                    )
                )

                value = clean_text(
                    td.get_text(
                        " ",
                        strip=True
                    )
                )

            if key and value:
                details[key.casefold()] = value

    return details


def get_detail(details, *names):
    for wanted in names:

        wanted = wanted.casefold()

        for key, value in details.items():

            if wanted == key:
                return value

    return None


def extract_pages(details, soup):
    value = get_detail(
        details,
        "print length",
        "paperback",
        "hardcover",
    )

    if value:
        match = re.search(
            r"(\d[\d,]*)\s+pages?",
            value,
            re.I
        )

        if match:
            return int(
                match.group(1).replace(
                    ",",
                    ""
                )
            )

    text = clean_text(
        soup.get_text(
            " ",
            strip=True
        )
    ) or ""

    match = re.search(
        r"(\d[\d,]*)\s+pages\b",
        text,
        re.I
    )

    if match:
        return int(
            match.group(1).replace(
                ",",
                ""
            )
        )

    return None


def extract_format(details, soup):
    text = clean_text(
        soup.get_text(
            " ",
            strip=True
        )
    ) or ""

    formats = [
        "Mass Market Paperback",
        "Library Binding",
        "Kindle Edition",
        "Hardcover",
        "Paperback",
        "Audiobook",
        "Audio CD",
        "Board Book",
    ]

    for fmt in formats:
        if re.search(
            rf"\b{re.escape(fmt)}\b",
            text,
            re.I
        ):
            return fmt

    return None


def extract_genres(soup):
    genres = []

    # Only breadcrumbs/category structures.
    # Never scrape Amazon's generic navigation menu.
    selectors = [
        "#wayfinding-breadcrumbs_feature_div a",
        "#wayfinding-breadcrumbs_container a",
    ]

    for selector in selectors:

        for element in soup.select(
            selector
        ):

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if not text:
                continue

            if text.casefold() in {
                "books",
                "kindle store",
            }:
                continue

            genres.append(text)

    return unique(genres)


def extract_reviews(soup):
    reviews = []

    selectors = [
        '[data-hook="review-body"] span',
        '[data-hook="review-body"]',
    ]

    for selector in selectors:

        for element in soup.select(
            selector
        ):

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
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


def extract_isbn13(details, soup):
    """
    Return ISBN-13 when Amazon explicitly exposes it.
    Do not derive ISBN-13 from ASIN or ISBN-10.
    """
    value = get_detail(
        details,
        "isbn-13",
        "isbn 13",
    )

    if value:
        match = re.search(
            r"97[89][\d\-\s]{10,20}",
            value
        )

        if match:
            return re.sub(
                r"[^0-9]",
                "",
                match.group(0)
            )[:13]

    # Restrict fallback to text explicitly labelled ISBN-13.
    text = clean_text(
        soup.get_text(" ", strip=True)
    ) or ""

    match = re.search(
        r"ISBN[-\s]?13\s*[:\-]?\s*"
        r"(97[89][\d\-\s]{10,20})",
        text,
        flags=re.I,
    )

    if match:
        digits = re.sub(
            r"[^0-9]",
            "",
            match.group(1)
        )

        if len(digits) >= 13:
            return digits[:13]

    return None


def normalize_language(value):
    value = clean_text(value)

    if not value:
        return None

    # Product-detail values occasionally include surrounding labels.
    value = re.sub(
        r"^language\s*[:\-]?\s*",
        "",
        value,
        flags=re.I
    )

    return clean_text(value)


def fetch_book(isbn13, driver):
    product_url = find_product_url(
        isbn13,
        driver
    )

    if not product_url:
        return None

    safe_get(
        driver,
        product_url,
        wait=5
    )

    soup = BeautifulSoup(
        driver.page_source,
        "html.parser"
    )

    if is_blocked(soup):
        raise RuntimeError(
            "Amazon verification/CAPTCHA encountered"
        )

    title = extract_title(soup)

    if not title:
        return None

    details = product_details(soup)

    page_isbn13 = extract_isbn13(
        details,
        soup
    )

    # Reject an explicitly mismatched edition/product.
    # If Amazon does not expose ISBN-13, do not invent one.
    if page_isbn13 and page_isbn13 != isbn13:
        raise RuntimeError(
            f"ISBN mismatch: requested {isbn13}, "
            f"Amazon page exposes {page_isbn13}"
        )

    publisher = get_detail(
        details,
        "publisher"
    )

    publication_date = get_detail(
        details,
        "publication date"
    )

    language = normalize_language(
        get_detail(
            details,
            "language"
        )
    )

    pages = extract_pages(
        details,
        soup
    )

    physical_format = extract_format(
        details,
        soup
    )

    genres = extract_genres(soup)

    record = {
        "isbn13": isbn13,
        "title": title,
        "authors": parse_byline(soup),

        # Never infer publication country from
        # Amazon.com or another storefront.
        "publisher": publisher,
        "country": None,
        "publication_place": [],

        "date_of_publication":
            publication_date,

        "language": language,
        "Genre": genres,

        "number_of_pages": pages,
        "physical_format":
            physical_format,

        "source_url":
            driver.current_url,

        "sources": ["Amazon"],

        "_cover_url":
            extract_cover(soup),

        "_blurb":
            extract_description(soup),

        "_reviews":
            extract_reviews(soup),
    }

    return record


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
        x.get("isbn13")
        for x in existing
        if x.get("isbn13")
    }

    print(
        f"Loaded ISBNs : {len(isbns)}"
    )

    print(
        f"Already done : {len(completed)}"
    )

    print(
        "Starting Amazon collection...\n"
    )

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
                    driver
                )

                failures = [
                    x
                    for x in failures
                    if x.get("isbn13") != isbn
                ]

                if record is None:

                    failures.append({
                        "isbn13": isbn,
                        "reason":
                            "No Amazon book record found"
                    })

                    print(
                        f"[{index}/{len(isbns)}] "
                        f"{isbn} -> NOT FOUND"
                    )

                else:
                    existing.append(
                        record
                    )

                    completed.add(
                        isbn
                    )

                    print(
                        f"[{index}/{len(isbns)}] "
                        f"{isbn} -> "
                        f"{record['title']}"
                    )

                save_json(
                    OUTPUT_FILE,
                    existing
                )

                save_json(
                    FAILURE_FILE,
                    failures
                )

            except Exception as error:

                failures = [
                    x
                    for x in failures
                    if x.get("isbn13") != isbn
                ]

                failures.append({
                    "isbn13": isbn,
                    "reason": str(error)
                })

                save_json(
                    FAILURE_FILE,
                    failures
                )

                print(
                    f"[{index}/{len(isbns)}] "
                    f"{isbn} -> ERROR: {error}"
                )

            time.sleep(
                DELAY_SECONDS
            )

    except KeyboardInterrupt:
        print(
            "\nStopped manually. "
            "Progress is saved."
        )

    finally:
        save_json(
            OUTPUT_FILE,
            existing
        )

        save_json(
            FAILURE_FILE,
            failures
        )

        driver.quit()

    print(
        "\n================================"
    )

    print(
        "AMAZON COLLECTION STOPPED/COMPLETE"
    )

    print(
        "================================"
    )

    print(
        f"Successful : {len(existing)}"
    )

    print(
        f"Failures   : {len(failures)}"
    )


if __name__ == "__main__":
    main()
