import json
import re

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.MULTILINE)
_DECODER = json.JSONDecoder()


def extract_json(text: str) -> dict:
    """Parses the first JSON object in model output. JSON mode makes fences
    and commentary rare, but this stays as the fallback for providers/models
    that still add them. Decoding starts at the first `{` and stops where the
    object ends, so trailing prose (even prose containing braces) is ignored."""
    text = _FENCE.sub("", text.strip()).strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in the model's response")
    value, _ = _DECODER.raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("The model's JSON was not an object")
    return value
