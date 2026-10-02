import json
import re


def extract_json(text: str) -> dict:
    """Parses a JSON object from model output. JSON mode makes the fences
    and commentary rare, but this stays as the fallback for providers/models
    that still add them."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in the model's response")
    return json.loads(match.group(0))
