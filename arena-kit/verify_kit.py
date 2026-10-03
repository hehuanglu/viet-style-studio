"""Check the design kit without API calls or third-party dependencies.

Checks config/schema/source/template consistency and a few scoring invariants.
This is not a runtime validator, cultural oracle, or live Gemini benchmark.
"""

from pathlib import Path
import json
import re


ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def eligible_score(ratings, profile, hard_statuses, mode, policy):
    """Illustrate filtering then scoring; assumes scope/evidence already checked."""
    if mode == "historical":
        profile = policy["scoring"]["historical_profile"]
    allowed = set(policy["gates"]["hard_statuses_allowed"])
    if not hard_statuses or any(s not in allowed for s in hard_statuses):
        return None
    minimums = dict(policy["scoring"]["minimum_ratings"])
    if mode == "historical":
        minimums.update(policy["scoring"]["historical_minimum_ratings"])
    if any(ratings[k] < value for k, value in minimums.items()):
        return None
    score = sum(policy["profiles"][profile][k] * ratings[k] / 4
                for k in policy["dimensions"])
    return score if score >= policy["scoring"]["minimum_total"] else None


def main():
    policy = read_json("policy.json")
    pack = read_json("domain-pack.example.json")
    schemas = read_json("contracts.json")
    cases = read_json("eval-cases.json")["cases"]
    prompts = (ROOT / "prompts.md").read_text(encoding="utf-8")
    dimensions = set(policy["dimensions"])
    for name, weights in policy["profiles"].items():
        require(set(weights) == dimensions, f"Dimensions differ: {name}")
        require(sum(weights.values()) == 100, f"Weights do not sum to 100: {name}")
        require(all(v >= 0 for v in weights.values()), f"Negative weight: {name}")

    references = []

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                require(ref.startswith("#/$defs/"), f"Unexpected schema reference: {ref}")
                require(ref.split("/")[-1] in schemas["$defs"], f"Unresolved reference: {ref}")
                references.append(ref)
            if node.get("type") == "object":
                require(set(node.get("required", [])) <= set(node.get("properties", {})),
                        "Required property absent from schema")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schemas)
    require(schemas["$defs"]["CandidateBatch"]["properties"]["candidates"]["maxItems"] ==
            policy["request_budget"]["candidate_limit"], "Candidate budget/schema differ")
    require(schemas["$defs"]["Question"]["properties"]["impact"]["enum"] ==
            ["blocking", "quality", "optional"], "Question impact contract differs")
    require(set(schemas["$defs"]["Ratings"]["properties"]) == dimensions,
            "Rating schema differs from policy")

    source_by_id = {source["id"]: source for source in pack["sources"]}
    require(len(source_by_id) == len(pack["sources"]), "Duplicate source ID")
    unit_by_id = {unit["id"]: unit for unit in pack["knowledge_units"]}
    require(len(unit_by_id) == len(pack["knowledge_units"]), "Duplicate knowledge ID")
    for unit in pack["knowledge_units"]:
        require(unit["source_id"] in source_by_id, f"Missing source: {unit['id']}")
        source = source_by_id[unit["source_id"]]
        if source.get("path"):
            contents = (ROOT / source["path"]).read_text(encoding="utf-8")
            require(unit["source_excerpt"] in contents, f"Excerpt absent: {unit['id']}")
        require(unit["kind"] != "cultural_fact", "Starter pack must not invent cultural facts")
    for rule in pack["rules"]:
        require(all(k in unit_by_id for k in rule["knowledge_ids"]),
                f"Rule references unknown knowledge: {rule['id']}")
        if rule["enabled"]:
            require(rule["status"] == "verified", f"Unverified active rule: {rule['id']}")

    expected_placeholders = {
        "P00": {"TASK_BRIEF", "SOURCE_ID", "ENABLED_CAPABILITIES"},
        "P01": {"SOURCE_RECORDS", "ONTOLOGY", "MODES"},
        "P02": {"REQUEST_METADATA", "CURRENT_TURN", "TURN_ID", "USER_TURNS", "PREVIOUS_BRIEF", "DOMAIN_FIELDS", "QUESTION_STATE", "ENABLED_CAPABILITIES"},
        "P03": {"USER_TURNS", "NORMALIZED_BRIEF", "EVIDENCE_BUNDLE", "APPLICABLE_RULES", "VARIATION_AXES", "CANDIDATE_LIMIT", "ENABLED_CAPABILITIES"},
        "P04": {"USER_TURNS", "NORMALIZED_BRIEF", "CANDIDATES_SHUFFLED", "EVIDENCE_BUNDLE", "APPLICABLE_RULES", "RUBRIC", "EXPECTED_GATES"},
        "P05": {"SUBJECT_DESCRIPTION", "KEEP_INVARIANTS", "SELECTED_DESIGN", "SCENE", "COMPOSITION", "ALLOWED_CHANGES", "AVOID_LIST"},
        "P06": {"IMAGE_ARTIFACTS", "APPROVED_CONCEPTS", "NORMALIZED_BRIEF", "VISIBLE_RULES", "EXPECTED_IMAGE_GATES"},
        "P07": {"PARENT_ARTIFACT", "ORIGINAL_IMAGE", "ANNOTATED_IMAGE", "ANNOTATIONS", "EDIT_REQUEST", "LOCKED_INVARIANTS", "APPLICABLE_RULES", "ENABLED_CAPABILITIES"},
        "P08": {"CANDIDATE", "AUDIT_FINDINGS", "NORMALIZED_BRIEF", "EVIDENCE_BUNDLE", "APPLICABLE_RULES"},
        "P09": {"APPROVED_CANDIDATE", "NORMALIZED_BRIEF", "LOCKED_REQUIREMENTS", "DRAFT_PROMPT"},
        "P10": {"REQUEST_METADATA", "USER_TURNS", "PROPOSED_BRIEF", "DOMAIN_FIELDS"}
    }
    sections = re.split(r"^## (P\d\d) — .*?$", prompts, flags=re.MULTILINE)
    found = {sections[i]: sections[i + 1] for i in range(1, len(sections), 2)}
    require(set(found) == set(expected_placeholders), "Missing/extra template")
    for name, expected in expected_placeholders.items():
        actual = set(re.findall(r"\{\{([A-Z_]+)\}\}", found[name]))
        require(actual == expected, f"Template variable mismatch: {name}")

    all_four = {key: 4 for key in dimensions}
    for profile in policy["profiles"]:
        require(eligible_score(all_four, profile, ["fail"], "inspired", policy) is None,
                "Beauty must not compensate for hard failure")
        require(eligible_score(all_four, profile, ["uncertain"], "inspired", policy) is None,
                "Uncertainty must not become success")
        require(eligible_score(all_four, profile, ["pass"], "inspired", policy) == 100,
                "Rating normalization differs")
    low_fit = dict(all_four, need_fit=2)
    require(eligible_score(low_fit, "balanced", ["pass"], "inspired", policy) is None,
            "Dimension floor is not enforced")
    require(eligible_score(all_four, "balanced", [], "inspired", policy) is None,
            "An empty audit must not pass")
    heritage_gap = dict(all_four, grounded_explanation=2)
    require(eligible_score(heritage_gap, "creative", ["pass"], "historical", policy) is None,
            "Historical mode must keep its explanation floor")
    require(len({case["id"] for case in cases}) == len(cases), "Duplicate eval ID")
    require(all(case["expected"] for case in cases), "Empty eval expectation")

    print(json.dumps({
        "status": "passed",
        "json_files_checked": 4,
        "prompt_templates_checked": len(found),
        "scoring_profiles_checked": len(policy["profiles"]),
        "schema_references_checked": len(references),
        "task_excerpts_checked": len(pack["knowledge_units"]),
        "behavioral_cases_prepared_not_api_run": len(cases),
        "live_gemini_calls": 0
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
