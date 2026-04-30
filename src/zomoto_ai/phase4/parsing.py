from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple


def extract_first_json_object(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Tries to extract the first JSON object from a raw model response.
    Returns (parsed_obj_or_none, error_message).
    """
    if text is None:
        return None, "empty response"

    s = text.strip()
    if not s:
        return None, "empty response"

    # Fast path: whole string is JSON
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj, ""
    except Exception:
        pass

    # Scan for a JSON object substring: find first '{' and balance braces.
    start = s.find("{")
    if start == -1:
        return None, "no '{' found"

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start : i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        return obj, ""
                    return None, "json is not an object"
                except Exception as e:
                    return None, f"failed to parse extracted json: {e}"

    return None, "unterminated json object"

