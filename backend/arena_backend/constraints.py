"""Deterministic checks for supported typed design fields; unknown checks stay with audit."""
import json
import re

from .core import fold


def terms(value):
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            return parsed
    except (ValueError, TypeError):
        pass
    return [item.strip() for item in re.split(r"[,;]", str(value)) if item.strip()]


def normalize(field, value):
    text = fold(value)
    if field == "palette":
        return text.removeprefix("mau ")
    if field == "bottom_garment" and text in ("pants", "trousers", "quan dai", "quan"):
        return "quan"
    return text


def actual_values(candidate, field):
    if field == "subject":
        return [candidate["subject"]]
    design = candidate["design"]
    if field in ("palette", "accessories"):
        return design[field]
    if field in ("scene", "composition", "subject_description"):
        return [design[field]]
    if field in ("bottom_garment",):
        return [item["value"] for item in design["extensions"] if item["key"] == field]
    return None


def check_constraint(candidate, constraint, domain=None):
    field, op, value = constraint["field"], constraint["operator"], constraint["value"]
    field = {"accessory_count": "accessories", "palette_count": "palette"}.get(field, field)
    actual = actual_values(candidate, field)
    if actual is None:
        return None, None
    if field in ("accessories", "palette") and op == "equals" and re.fullmatch(r"\d+", str(value).strip()):
        return len(actual) == int(value), actual
    if op in ("at_most", "at_least"):
        if field not in ("accessories", "palette") or not re.fullmatch(r"\d+", str(value).strip()):
            return None, actual
        limit = int(value)
        return (len(actual) <= limit if op == "at_most" else len(actual) >= limit), actual
    if op not in ("include", "exclude", "equals", "preserve"):
        return None, actual
    if op == "preserve" and field in ("composition", "scene", "subject_description"):
        return None, actual  # Natural-language visual preservation is checked by the auditors.
    expected = terms(value)
    if not expected:
        if str(value).strip() == "[]" and op in ("equals", "preserve"):
            return not actual, actual
        return None, actual
    if field == "subject" and domain:
        expected = [domain.subject_id(item) or item for item in expected]
    expected = [normalize(field, item) for item in expected]
    actual_normalized = [normalize(field, item) for item in actual]
    present = [any(re.search(r"(?<!\w)" + re.escape(item) + r"(?!\w)", other) for other in actual_normalized) for item in expected]
    if op == "exclude":
        return not any(present), actual
    if op in ("equals", "preserve"):
        return set(actual_normalized) == set(expected), actual
    return all(present), actual


def changed_attributes(left, right):
    return [key for key in ("palette", "accessories", "composition", "scene")
            if normalize(key, json.dumps(left["design"][key], ensure_ascii=False, sort_keys=True)) !=
            normalize(key, json.dumps(right["design"][key], ensure_ascii=False, sort_keys=True))]
