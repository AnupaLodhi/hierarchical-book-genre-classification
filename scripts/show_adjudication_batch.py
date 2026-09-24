import argparse
import csv
from pathlib import Path

FILE = Path("results/adjudication/adjudication_interim.csv")


def load_rows():
    with FILE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--size",
        type=int,
        default=15,
        help="Number of unfinished cases to display",
    )
    args = parser.parse_args()

    rows = load_rows()

    pending = [
        r for r in rows
        if not r["decision"].strip()
    ]

    batch = pending[:args.size]

    print("===== ADJUDICATION BATCH =====")
    print("Total cases:", len(rows))
    print("Completed:", len(rows) - len(pending))
    print("Remaining:", len(pending))
    print("Showing:", len(batch))

    for r in batch:
        print("\n" + "=" * 100)
        print(r["case_id"], "|", r["title"])
        print("FIELD:", r["field"].upper())

        print("\nCANDIDATE:")
        print(" ", r["candidate_path"])

        print("\nSOURCE TAGS:")
        for tag in r["filtered_tags"].split("|"):
            tag = tag.strip()
            if tag:
                print(" -", tag)

        print("\nCANONICAL:")
        for path in r["canonical_paths"].split("|"):
            path = path.strip()
            if path:
                print(" -", path)

    print("\n" + "=" * 100)
    print("Displayed cases:", len(batch))


if __name__ == "__main__":
    main()
