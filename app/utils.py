from __future__ import annotations
import json
import re

def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Model tidak mengembalikan JSON yang valid.")
    return json.loads(m.group(0))