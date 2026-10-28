"""Offset-preserving code masking for publication Markdown checks."""

import re


def _blank(text: str) -> str:
    return re.sub(r"[^\r\n]", " ", text)


def mask_fenced_code(markdown: str) -> str:
    lines, fence = [], None
    for line in markdown.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)", line)
        if fence is not None:
            lines.append(_blank(line))
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
            lines.append(_blank(line))
        else:
            lines.append(line)
    return "".join(lines)


def mask_code(markdown: str) -> str:
    fenced = mask_fenced_code(markdown)
    return re.sub(r"(?<!`)(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)", lambda match: _blank(match[0]), fenced)


def section_headers(markdown: str) -> list[re.Match]:
    return list(re.finditer(r"(?m)^ {0,3}##[ \t]+(.+?)[ \t]*#*[ \t]*$", mask_code(markdown)))
