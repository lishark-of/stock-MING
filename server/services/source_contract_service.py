from __future__ import annotations

import re


def strip_js_ts_comments(source: str) -> str:
    """Remove JavaScript/TypeScript/JSX comments without touching quoted text."""

    output: list[str] = []
    index = 0
    quote = ""
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if quote:
            output.append(char)
            if char == "\\" and index + 1 < len(source):
                index += 1
                output.append(source[index])
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            output.append(char)
            index += 1
            continue
        if char == "/" and following == "/":
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and following == "*":
            index += 2
            while index < len(source):
                if source[index] == "*" and index + 1 < len(source) and source[index + 1] == "/":
                    index += 2
                    break
                if source[index] in "\r\n":
                    output.append(source[index])
                index += 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def extract_balanced(
    source: str,
    open_index: int,
    *,
    opening: str,
    closing: str,
) -> tuple[str, int] | None:
    if open_index < 0 or open_index >= len(source) or source[open_index] != opening:
        return None
    depth = 0
    quote = ""
    index = open_index
    while index < len(source):
        char = source[index]
        if quote:
            if char == "\\" and index + 1 < len(source):
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return source[open_index + 1 : index], index + 1
        index += 1
    return None


def extract_named_function_body(source: str, function_name: str) -> str:
    match = re.search(
        rf"\b(?:export\s+)?(?:async\s+)?function\s+{re.escape(function_name)}\s*\(",
        source,
    )
    if not match:
        return ""
    parameter_open = source.find("(", match.start())
    parameters = extract_balanced(source, parameter_open, opening="(", closing=")")
    if not parameters:
        return ""
    body_open = source.find("{", parameters[1])
    body = extract_balanced(source, body_open, opening="{", closing="}")
    return body[0] if body else ""
