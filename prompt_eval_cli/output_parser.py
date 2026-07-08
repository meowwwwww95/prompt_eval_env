from __future__ import annotations

import re


EXPLICIT_PARSE_PATTERNS = [
    (re.compile(r'"(?:judgment|label|result|conclusion)"\s*:\s*"(是|否)"', re.IGNORECASE), 'json_field'),
    (re.compile(r'(?:结论|判断|最终判断|答案|标签|结果)\s*[:：]\s*(是|否)'), 'explicit_tag'),
]
LINE_PREFIX_RE = re.compile(r'^[\-*\d\.\)\s>]*(是|否)(?:\s|$|[：:])')


def parse_judgment(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return '未知', 'empty'

    for pattern, method in EXPLICIT_PARSE_PATTERNS:
        match = pattern.search(stripped)
        if match:
            return match.group(1), method

    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = LINE_PREFIX_RE.match(line)
        if match:
            return match.group(1), 'line_prefix'
        break

    compact = re.sub(r'\s+', '', stripped)
    if compact in {'是', 'yes', 'YES'}:
        return '是', 'single_token'
    if compact in {'否', 'no', 'NO'}:
        return '否', 'single_token'
    return '未知', 'unparsed'


def parse_status_from_result(parsed_judgment: str, parse_method: str, error_message: str) -> str:
    if error_message:
        return 'failed'
    if parsed_judgment != '未知':
        return 'success'
    if parse_method == 'empty':
        return 'empty_output'
    return 'unparsed'
