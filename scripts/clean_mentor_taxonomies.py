import json
import re
from pathlib import Path

GENRE_SOURCE = Path(
    "taxonomy/reviewed/genre_hierarchy_mentor_original.json"
)

METADATA_SOURCE = Path(
    "taxonomy/reviewed/metadata_hierarchy_mentor_original.json"
)


def clean_text(text):
    text = text.replace("�", "")
    text = text.replace("’", "'")

    cleaned_lines = []

    for line in text.splitlines():
        stripped = line.strip()

        # Remove standalone mentor review notes.
        if re.match(r"^\[RM\d+\]", stripped):
            continue

        # Remove inline /// comments.
        if "///" in line:
            line = line.split("///", 1)[0].rstrip()

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Remove inline markers such as [RM1], [RM6], etc.
    text = re.sub(r"\[RM\d+\]", "", text)

    # Repair malformed punctuation in mentor-reviewed files.
    text = text.replace('"Indo-Pacific".', '"Indo-Pacific",')

    # Remove trailing commas immediately before ] or }.
    text = re.sub(r",(\s*[\]\}])", r"\1", text)

    # Mentor review notes may appear after the JSON document has closed.
    # Keep only the first complete JSON object.
    decoder = json.JSONDecoder()
    stripped = text.lstrip()
    try:
        _, end = decoder.raw_decode(stripped)
        text = stripped[:end]
    except json.JSONDecodeError:
        pass

    return text


def test_file(path, name):
    raw = path.read_text(encoding="utf-8")
    cleaned = clean_text(raw)

    try:
        data = json.loads(cleaned)

        print(f"✅ {name}: PARSED")
        print("   Root keys:", list(data.keys()))

        return data

    except json.JSONDecodeError as error:
        print(f"❌ {name}: STILL INVALID")
        print("   Line:", error.lineno)
        print("   Column:", error.colno)
        print("   Error:", error.msg)

        lines = cleaned.splitlines()

        print("   Context:")

        start = max(0, error.lineno - 3)
        end = min(len(lines), error.lineno + 2)

        for index in range(start, end):
            marker = ">>" if index + 1 == error.lineno else "  "
            print(f"{marker} {index + 1}: {lines[index]}")

        return None


def main():
    print("===== MENTOR TAXONOMY CLEANUP TEST =====")
    print()

    genre = test_file(GENRE_SOURCE, "GENRE")

    print()

    metadata = test_file(METADATA_SOURCE, "METADATA")

    print()

    if genre is not None and metadata is not None:
        genre, metadata, changes = apply_mentor_semantic_decisions(
            genre,
            metadata
        )

        GENRE_OUTPUT = Path("taxonomy/genre_hierarchy.json")
        METADATA_OUTPUT = Path("taxonomy/metadata_hierarchy.json")

        GENRE_OUTPUT.write_text(
            json.dumps(genre, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

        METADATA_OUTPUT.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

        print("✅ BOTH MENTOR TAXONOMIES ARE STRUCTURALLY PARSEABLE")
        print("✅ WROTE:", GENRE_OUTPUT)
        print("✅ WROTE:", METADATA_OUTPUT)
    else:
        print("⚠️ MORE SYNTAX CLEANUP IS REQUIRED")



# ============================================================
# SEMANTIC TRANSFORMATIONS FROM MENTOR REVIEW
# ============================================================

def apply_mentor_semantic_decisions(genre, metadata):

    changes = []

    # --------------------------------------------------------
    # 1. GENRE: historical time periods belong in metadata.
    # --------------------------------------------------------
    historical = genre["Fiction"]["Historical Fiction"]

    if "Historical Fiction" in historical:
        removed = historical["Historical Fiction"]
        historical.pop("Historical Fiction")

        changes.append(
            "Removed time-period Historical Fiction subgenres from Genre: "
            + ", ".join(removed)
        )

    # --------------------------------------------------------
    # 2. GENRE: mentor explicitly says Information Studies
    #    should not be a genre.
    # --------------------------------------------------------
    library_branch = (
        genre["Nonfiction"]
        ["Reference and Knowledge Organization"]
        ["Library and Information Studies"]
    )

    if isinstance(library_branch, list):
        library_branch[:] = [
            x for x in library_branch
            if x != "Information Studies"
        ]
        changes.append(
            "Removed Information Studies from Genre taxonomy."
        )

    # Writing Studies is intentionally retained:
    # mentor questioned it but did not give a final removal decision.
    changes.append(
        "Retained Writing Studies because mentor review was unresolved."
    )

    root = metadata["Book_Metadata_Hierarchy"]

    # --------------------------------------------------------
    # 3. METADATA: Interactive Ebook explicitly marked
    #    'Not needed'.
    # --------------------------------------------------------
    digital = (
        root["Book_Format_and_Form"]
        ["Physical_or_Digital_Format"]
        ["Digital"]
    )

    if "Interactive Ebook" in digital:
        digital.remove("Interactive Ebook")
        changes.append(
            "Removed Interactive Ebook from metadata."
        )

    # --------------------------------------------------------
    # 4. GEOGRAPHY: remove empty accidental value.
    #    Do NOT guess what 'Missoure' means.
    # --------------------------------------------------------
    geo = root["Geographical Context"]

    central = geo["World_Region"].get("Central America", [])

    central[:] = [
        x for x in central
        if isinstance(x, str) and x.strip()
    ]

    changes.append(
        "Removed empty geographical label from Central America."
    )

    changes.append(
        "Left 'Missoure' unchanged and flagged for mentor review; "
        "its intended meaning was not specified."
    )

    # --------------------------------------------------------
    # 5. TEMPORAL CONTEXT:
    #    Replace criticized Historical_Period structure with
    #    mentor-proposed global + regional hierarchy.
    # --------------------------------------------------------
    temporal = root["Temporal_Context"]

    temporal.pop("Historical_Period", None)

    temporal["Global_Time_Frame"] = {
        "Prehistory": [
            "Prehistoric"
        ],
        "Antiquity": [
            "Pre-5th Century"
        ],
        "First_Millennium_CE": [
            "5th Century",
            "6th Century",
            "7th Century",
            "8th Century",
            "9th Century",
            "10th Century"
        ],
        "Second_Millennium_CE": {
            "Early_Second_Millennium": [
                "11th Century",
                "12th Century",
                "13th Century",
                "14th Century",
                "15th Century"
            ],
            "Late_Second_Millennium": [
                "16th Century",
                "17th Century",
                "18th Century",
                "19th Century",
                "20th Century"
            ]
        },
        "Third_Millennium_CE": [
            "21st Century",
            "Present Day"
        ],
        "Future": [
            "Near Future",
            "Far Future"
        ]
    }

    temporal["Regional_Historical_Eras"] = {
        "Indian_History": [
            "Vedic Period",
            "Maurya Era",
            "Gupta Era",
            "Delhi Sultanate",
            "Mughal Era",
            "British Raj"
        ],
        "European_and_British_History": [
            "Classical Period",
            "Anglo-Saxon Era",
            "Norman Period",
            "Tudor Period",
            "Elizabethan Era",
            "Victorian Era",
            "Edwardian Era"
        ],
        "East_Asian_History": [
            "Han Dynasty",
            "Tang Dynasty",
            "Song Dynasty",
            "Ming Dynasty",
            "Qing Dynasty",
            "Edo Period",
            "Meiji Era"
        ]
    }

    changes.append(
        "Replaced Historical_Period with mentor-proposed "
        "Global_Time_Frame and Regional_Historical_Eras."
    )

    # --------------------------------------------------------
    # 6. Mentor interpretation notes.
    # These affect annotation semantics, not taxonomy labels.
    # --------------------------------------------------------
    changes.append(
        "Geographical Context interpreted as story/setting location."
    )

    changes.append(
        "Role_Profile interpreted as roles of characters in the story."
    )

    changes.append(
        "Group_Profile interpreted as groups of characters in the text."
    )

    return genre, metadata, changes


if __name__ == "__main__":
    main()
