import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path

from agents.llm_providers import query_model


INPUT = Path("results/path_debate_v2/path_conflicts.json")
OUTPUT = Path("results/path_debate_v2/round1_supporters.json")

MODELS = {
    "qwen_groq": {
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "max_tokens": 350,
    },
    "gpt_oss_groq": {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "max_tokens": 350,
    },
    "gpt_oss_20b": {
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "max_tokens": 350,
    },
}


def atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
            )

        os.replace(temp_name, path)

    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def parse_json_object(raw):
    text = raw.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

    try:
        obj = json.loads(text)

    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                "No JSON object found in model response"
            )

        obj = json.loads(text[start:end + 1])

    if not isinstance(obj, dict):
        raise ValueError(
            "Model response must be a JSON object"
        )

    return obj


def normalize_response(raw, valid_tags):
    obj = parse_json_object(raw)

    decision = str(
        obj.get("decision", "")
    ).strip().upper()

    if decision not in {"MAINTAIN", "RETRACT"}:
        raise ValueError(
            "decision must be MAINTAIN or RETRACT"
        )

    evidence = obj.get("evidence_tags", [])

    if not isinstance(evidence, list):
        raise ValueError(
            "evidence_tags must be a JSON list"
        )

    evidence = [
        str(x).strip()
        for x in evidence
        if str(x).strip()
    ]

    invalid = [
        tag
        for tag in evidence
        if tag not in valid_tags
    ]

    if invalid:
        raise ValueError(
            "Returned evidence tag was not present "
            f"in filtered_tags: {invalid}"
        )

    justification = str(
        obj.get("justification", "")
    ).strip()

    if not justification:
        raise ValueError(
            "justification must not be empty"
        )

    return {
        "decision": decision,
        "evidence_tags": evidence,
        "justification": justification,
    }


def build_prompt(dispute, supporter):
    tags = dispute["filtered_tags"]
    annotation_type = dispute["annotation_type"]
    path = dispute["disputed_path"]

    if annotation_type == "Metadata":
        domain_rules = """
METADATA RULES
- Use zero inference.
- The disputed metadata path must be supported by explicit
  wording in FILTERED TAGS.
- Do not assume language, audience, geography, era, format,
  authorship, relationships, setting, or other metadata.
- If the path depends on an assumption rather than explicit
  source evidence, RETRACT it.
""".strip()
    else:
        domain_rules = """
GENRE RULES
- Judge whether the disputed genre path is directly supported
  by FILTERED TAGS.
- Do not invent themes or genre specificity absent from the
  source evidence.
- A broader tag does not automatically justify a narrower
  disputed genre path.
- Variable hierarchy depth is valid; do not force a deeper
  taxonomy level.
""".strip()

    return f"""
You previously supported one annotation path for this book.
Reconsider ONLY that disputed path using the supplied source
evidence.

Do not evaluate other paths.
Do not use outside knowledge.
Do not use the title as evidence.
Do not provide hidden chain-of-thought.

BOOK
ISBN: {dispute["isbn13"]}
Title: {dispute.get("title", "")}

ANNOTATION TYPE
{annotation_type}

DISPUTED PATH
{path}

FILTERED TAGS
{json.dumps(tags, ensure_ascii=False)}

{domain_rules}

DECISION
Return MAINTAIN only if the disputed path is sufficiently
supported by the filtered source tags.
Otherwise return RETRACT.

EVIDENCE TAGS
Copy only exact strings from FILTERED TAGS that directly
support your decision.
If no filtered tag directly supports the path, use [].

JUSTIFICATION
Give one short evidence-based sentence. Do not reveal internal
reasoning or chain-of-thought.

Return JSON only:
{{
  "decision": "MAINTAIN or RETRACT",
  "evidence_tags": [],
  "justification": "one short sentence"
}}

Original supporter model identifier: {supporter}
""".strip()


def load_existing():
    if not OUTPUT.exists():
        return {}

    data = json.loads(
        OUTPUT.read_text(encoding="utf-8")
    )

    return {
        (
            x["debate_id"],
            x["supporter_model"],
        ): x
        for x in data
    }


def run(limit=None, delay=1.0):
    disputes = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    if limit is not None:
        disputes = disputes[:limit]

    records = load_existing()

    expected = sum(
        len(x["models_for"])
        for x in disputes
    )

    print("===== ROUND 1 SUPPORTER RECONSIDERATION =====")
    print("Disputes selected :", len(disputes))
    print("Supporter tasks    :", expected)

    task_number = 0
    paused_models = set()

    for dispute in disputes:
        for supporter in dispute["models_for"]:
            task_number += 1

            key = (
                dispute["debate_id"],
                supporter,
            )

            existing = records.get(key)

            if supporter in paused_models:
                print(
                    f"[{task_number}/{expected}] "
                    f"{supporter} quota paused - skip"
                )
                continue

            if existing and existing.get("status") == "success":
                print(
                    f"[{task_number}/{expected}] "
                    f"{supporter} checkpoint ✓"
                )
                continue

            config = MODELS[supporter]
            prompt = build_prompt(
                dispute,
                supporter,
            )

            print(
                f"[{task_number}/{expected}] "
                f"{supporter} | "
                f"{dispute['annotation_type']} | "
                f"{dispute['isbn13']}"
            )

            try:
                try:
                    raw = query_model(
                        prompt,
                        provider=config["provider"],
                        model=config["model"],
                        max_tokens=config["max_tokens"],
                    )
                except RuntimeError as length_error:
                    if "finish_reason=length" not in str(length_error):
                        raise

                    print(
                        "    Output hit token limit; "
                        "retrying with 700 tokens..."
                    )

                    raw = query_model(
                        prompt,
                        provider=config["provider"],
                        model=config["model"],
                        max_tokens=700,
                    )

                try:
                    parsed = normalize_response(
                        raw,
                        dispute["filtered_tags"],
                    )
                except (ValueError, json.JSONDecodeError) as first_error:
                    print(
                        "    Invalid model output; "
                        "requesting one correction..."
                    )

                    correction_prompt = f"""
{prompt}

Your previous response failed validation:
{first_error}

Return the answer again using ONLY the required JSON object.

IMPORTANT:
- Keep the same reconsideration task and evidence rules.
- evidence_tags must contain ONLY exact strings copied
  character-for-character from FILTERED TAGS above.
- Do not paraphrase, normalize, combine, or invent evidence tags.
- If no supplied tag directly supports the disputed path,
  use an empty evidence_tags list and RETRACT.
- Return no prose, markdown, or code fences outside the JSON.
""".strip()

                    raw = query_model(
                        correction_prompt,
                        provider=config["provider"],
                        model=config["model"],
                        max_tokens=config["max_tokens"],
                    )

                    parsed = normalize_response(
                        raw,
                        dispute["filtered_tags"],
                    )

                records[key] = {
                    "debate_id": dispute["debate_id"],
                    "isbn13": dispute["isbn13"],
                    "title": dispute.get("title", ""),
                    "annotation_type":
                        dispute["annotation_type"],
                    "disputed_path":
                        dispute["disputed_path"],
                    "support_count":
                        dispute["support_count"],
                    "supporter_model": supporter,
                    "provider": config["provider"],
                    "model": config["model"],
                    "status": "success",
                    "decision": parsed["decision"],
                    "evidence_tags":
                        parsed["evidence_tags"],
                    "justification":
                        parsed["justification"],
                    "error": "",
                }

                print(
                    "  ",
                    parsed["decision"],
                    parsed["evidence_tags"],
                )

            except Exception as exc:
                records[key] = {
                    "debate_id": dispute["debate_id"],
                    "isbn13": dispute["isbn13"],
                    "title": dispute.get("title", ""),
                    "annotation_type":
                        dispute["annotation_type"],
                    "disputed_path":
                        dispute["disputed_path"],
                    "support_count":
                        dispute["support_count"],
                    "supporter_model": supporter,
                    "provider": config["provider"],
                    "model": config["model"],
                    "status": "error",
                    "decision": "",
                    "evidence_tags": [],
                    "justification": "",
                    "error": str(exc),
                }

                error_text = str(exc)

                print(
                    "  ERROR:",
                    error_text[:300],
                )

                error_lower = error_text.lower()
                is_daily_quota = (
                    "429" in error_lower
                    and (
                        "tokens per day" in error_lower
                        or "(tpd)" in error_lower
                    )
                )

                if is_daily_quota:
                    paused_models.add(supporter)
                    print(
                        f"  {supporter}: DAILY QUOTA EXHAUSTED "
                        "- paused for this run"
                    )

            atomic_write_json(
                OUTPUT,
                list(records.values()),
            )

            if delay:
                time.sleep(delay)

    selected_ids = {
        x["debate_id"]
        for x in disputes
    }

    selected_records = [
        x
        for x in records.values()
        if x["debate_id"] in selected_ids
    ]

    success = sum(
        x["status"] == "success"
        for x in selected_records
    )

    errors = sum(
        x["status"] == "error"
        for x in selected_records
    )

    maintain = sum(
        x.get("decision") == "MAINTAIN"
        for x in selected_records
    )

    retract = sum(
        x.get("decision") == "RETRACT"
        for x in selected_records
    )

    print("\n===== PILOT SUMMARY =====")
    print("Expected tasks :", expected)
    print("Successful     :", success)
    print("Errors         :", errors)
    print("MAINTAIN       :", maintain)
    print("RETRACT        :", retract)
    print("Output         :", OUTPUT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of disputes to process.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
    )

    args = parser.parse_args()

    run(
        limit=args.limit,
        delay=args.delay,
    )
