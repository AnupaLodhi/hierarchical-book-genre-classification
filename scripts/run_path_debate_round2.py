import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path

from agents.llm_providers import query_model


INPUT = Path("results/path_debate_v2/path_conflicts.json")
ROUND1 = Path(
    "results/path_debate_v2/frozen_round1/"
    "round1_supporters_1259_complete.json"
)
OUTPUT = Path("results/path_debate_v2/round2_opponents.json")

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

    if decision not in {"ACCEPT", "REJECT"}:
        raise ValueError(
            "decision must be ACCEPT or REJECT"
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

def get_round2_opponents(dispute, round1_by_debate):
    records = round1_by_debate.get(
        dispute["debate_id"],
        [],
    )

    if len(records) != dispute["support_count"]:
        raise ValueError(
            f"Round 1 record count mismatch for "
            f"{dispute['debate_id']}"
        )

    if any(x.get("status") != "success" for x in records):
        raise ValueError(
            f"Round 1 is not complete for "
            f"{dispute['debate_id']}"
        )

    decisions = [
        x["decision"]
        for x in records
    ]

    if dispute["support_count"] == 1:
        if decisions == ["MAINTAIN"]:
            return list(dispute["models_against"])

        if decisions == ["RETRACT"]:
            return []

    elif dispute["support_count"] == 2:
        maintain = decisions.count("MAINTAIN")
        retract = decisions.count("RETRACT")

        if maintain == 2:
            return list(dispute["models_against"])

        if retract == 2:
            return []

        if maintain == 1 and retract == 1:
            return []

    raise ValueError(
        f"Unexpected Round 1 state for "
        f"{dispute['debate_id']}: {decisions}"
    )

def build_prompt(dispute, opponent, round1_records):
    tags = dispute["filtered_tags"]
    annotation_type = dispute["annotation_type"]
    path = dispute["disputed_path"]

    supporter_arguments = [
        {
            "supporter_model": r["supporter_model"],
            "decision": r["decision"],
            "evidence_tags": r["evidence_tags"],
            "justification": r["justification"],
        }
        for r in round1_records
    ]

    if annotation_type == "Metadata":
        domain_rules = """
METADATA RULES
- Use zero inference.
- The disputed metadata path must be supported by explicit
  wording in FILTERED TAGS.
- Do not assume language, audience, geography, era, format,
  authorship, relationships, setting, or other metadata.
- If the path depends on an assumption rather than explicit
  source evidence, REJECT it.
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
You previously opposed one disputed annotation path for this
book. The original supporter model(s) have reconsidered the
path and maintained their support.

Review ONLY this disputed path again after considering their
Round 1 argument(s).

The supporter arguments are debate context, not new source
evidence. The final decision must still be grounded only in
FILTERED TAGS.

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

ROUND 1 SUPPORTER ARGUMENTS
{json.dumps(supporter_arguments, ensure_ascii=False, indent=2)}

{domain_rules}

DECISION
Return ACCEPT if, after reviewing the supporter argument(s),
you agree that the disputed path is sufficiently supported by
FILTERED TAGS.

Return REJECT if the disputed path is not sufficiently
supported by FILTERED TAGS.

EVIDENCE TAGS
Copy only exact strings from FILTERED TAGS that directly
support your decision.
If no filtered tag directly supports the disputed path,
use [].

JUSTIFICATION
Give one short evidence-based sentence. Do not reveal internal
reasoning or chain-of-thought.

Return JSON only:
{{
  "decision": "ACCEPT or REJECT",
  "evidence_tags": [],
  "justification": "one short sentence"
}}

Opponent model identifier: {opponent}
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
            x["opponent_model"],
        ): x
        for x in data
    }


def run(limit=None, delay=1.0):
    disputes = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    round1 = json.loads(
        ROUND1.read_text(encoding="utf-8")
    )

    round1_by_debate = {}

    for record in round1:
        round1_by_debate.setdefault(
            record["debate_id"],
            [],
        ).append(record)

    eligible = []

    for dispute in disputes:
        opponents = get_round2_opponents(
            dispute,
            round1_by_debate,
        )

        if opponents:
            eligible.append(
                (dispute, opponents)
            )

    if limit is not None:
        eligible = eligible[:limit]

    records = load_existing()

    expected = sum(
        len(opponents)
        for _, opponents in eligible
    )

    print("===== ROUND 2 OPPONENT REVIEW =====")
    print("Eligible disputes :", len(eligible))
    print("Opponent tasks    :", expected)

    task_number = 0
    paused_models = set()

    for dispute, opponents in eligible:
        r1_records = round1_by_debate[
            dispute["debate_id"]
        ]

        for opponent in opponents:
            task_number += 1

            key = (
                dispute["debate_id"],
                opponent,
            )

            existing = records.get(key)

            if opponent in paused_models:
                print(
                    f"[{task_number}/{expected}] "
                    f"{opponent} quota paused - skip"
                )
                continue

            if existing and existing.get("status") == "success":
                print(
                    f"[{task_number}/{expected}] "
                    f"{opponent} checkpoint ✓"
                )
                continue

            config = MODELS[opponent]

            prompt = build_prompt(
                dispute,
                opponent,
                r1_records,
            )

            print(
                f"[{task_number}/{expected}] "
                f"{opponent} | "
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
- Keep the same opponent-review task and evidence rules.
- decision must be ACCEPT or REJECT.
- evidence_tags must contain ONLY exact strings copied
  character-for-character from FILTERED TAGS above.
- Do not paraphrase, normalize, combine, or invent evidence tags.
- If no supplied tag directly supports the disputed path,
  use an empty evidence_tags list and REJECT.
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
                    "opponent_model": opponent,
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
                    "opponent_model": opponent,
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
                    paused_models.add(opponent)
                    print(
                        f"  {opponent}: DAILY QUOTA EXHAUSTED "
                        "- paused for this run"
                    )

            atomic_write_json(
                OUTPUT,
                list(records.values()),
            )

            if delay:
                time.sleep(delay)

    selected_ids = {
        dispute["debate_id"]
        for dispute, _ in eligible
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

    accept = sum(
        x.get("decision") == "ACCEPT"
        for x in selected_records
    )

    reject = sum(
        x.get("decision") == "REJECT"
        for x in selected_records
    )

    print("\n===== ROUND 2 SUMMARY =====")
    print("Eligible disputes :", len(eligible))
    print("Expected tasks    :", expected)
    print("Successful        :", success)
    print("Errors            :", errors)
    print("ACCEPT            :", accept)
    print("REJECT            :", reject)
    print("Output            :", OUTPUT)


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
