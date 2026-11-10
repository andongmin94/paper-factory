"""Offset-preserving code and math masking for publication Markdown checks."""

import re


# Inline code may wrap, but cannot cross a blank paragraph boundary.
_INLINE_CODE = (r"(?<!`)(?P<ticks>`+)(?!`)"
                r"(?:[^\r\n]|(?:\r\n?|\n)(?![ \t]*(?:\r\n?|\n)))*?"
                r"(?<!`)(?P=ticks)(?!`)")


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
        # Pandoc permits backticks in quoted fence attributes, but not bare info.
        elif marker and (marker[1][0] == "~" or "`" not in marker[2] or
                         re.fullmatch(r"""\s*\{(?:[^`'"]|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')*\}\s*""", marker[2])):
            fence = marker[1]
            lines.append(_blank(line))
        else:
            lines.append(line)
    return "".join(lines)


def mask_code(markdown: str) -> str:
    fenced = mask_fenced_code(markdown)
    return re.sub(_INLINE_CODE, lambda match: _blank(match[0]), fenced)


def mask_code_and_math(markdown: str) -> str:
    """Exclude code and the converter's dollar-delimited TeX math from prose."""
    # https://pandoc.org/MANUAL.html#extension-tex_math_dollars
    # Neither math form crosses blank lines. Inline delimiters also distinguish
    # whitespace and currency; escaped dollars are not math delimiters.
    line = r"(?:\r\n?|\n)(?![ \t]*(?:\r\n?|\n))"
    inline = rf"\$(?![\s$])(?:\\[^\r\n]|[^\\$\r\n]|{line})*?(?<!\s)\$(?!\d)"
    display = rf"\$\$(?:\\[^\r\n]|(?!\$\$)[^\\\r\n]|{line})*?\$\$"
    # One scan preserves delimiter precedence: dollars in code and backticks in
    # math cannot start a different span that hides surrounding prose.
    pattern = rf"(?P<escape>\\[^\r\n])|{_INLINE_CODE}|{display}|{inline}"
    return re.sub(pattern, lambda match: match[0] if match["escape"] else _blank(match[0]),
                  mask_fenced_code(markdown))


def section_headers(markdown: str) -> list[re.Match]:
    return list(re.finditer(r"(?m)^ {0,3}##[ \t]+(.+?)[ \t]*#*[ \t]*$", mask_code(markdown)))
