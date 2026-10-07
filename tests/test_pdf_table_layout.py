"""Native PDF regression for readable statistics with intact long labels."""
import hashlib
import json
import re
import subprocess

import pytest

from paper_factory import conversion
from paper_factory.autonomous import science
from paper_factory.workspace import digest_file


@pytest.mark.parametrize("condition_count", [2, 8])
@pytest.mark.parametrize("sample_count", [36, 10000])
def test_statistics_pdf_wraps_complete_identifiers_within_page_margins(tmp_path, pandoc, condition_count, sample_count):
    pytest.importorskip("typst")
    from docx import Document
    from pypdf import PdfReader

    metric = "canonicalization_invariance_with_long_identifiers"
    unit = "normalized_milliseconds_per_complete_observation"
    conditions = [f"alternative_policy_replaying_conflicting_events_{index}" for index in range(condition_count)]
    summaries = [{"metric": metric, "condition": condition, "unit": unit, "count": sample_count,
                  "mean": 115465.25, "median": 67037.5, "stdev": 284341.7243,
                  "min": 40880, "max": 1770754} for condition in conditions]
    paired = [{"metric": metric, "condition": conditions[1], "baseline": conditions[0], "count": sample_count,
               "mean": -114053.8611, "median": -65711, "stdev": 284346.453,
               "min": -1769431, "max": -39989}]
    source = tmp_path / "long-statistics.md"
    source.write_text("# 한국어 표 검증\n\n" + science._tables({"summaries": summaries, "paired_deltas": paired}), encoding="utf-8")
    original = source.read_bytes()
    output = source.with_suffix(".pdf")
    receipt = conversion.convert(source, output, pandoc=pandoc)

    reader = PdfReader(output)
    text = "".join(page.extract_text() or "" for page in reader.pages)
    # Soft wrapping may add line breaks or zero-width opportunities, but loses no printed character.
    tokens = re.sub(r"[\s\u200b]", "", text).replace("−", "-")
    assert metric in tokens and unit in tokens
    assert tokens.count(metric) == condition_count
    assert tokens.count(unit) == condition_count
    for condition in conditions:
        assert condition in tokens
    assert tokens.count("1.155e+05") == condition_count
    assert tokens.count("2.843e+05") == condition_count
    assert tokens.count("-1.141e+05") == 1
    assert "한국어표검증" in tokens

    # Use Pandoc's actual column allocation to catch right-aligned counts
    # extending into the preceding condition cell, even within page margins.
    parsed = subprocess.run([pandoc, str(source), "--from=markdown-smart-raw_tex-raw_html", "--to=json"],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    table_ast = next(block for block in json.loads(parsed.stdout)["blocks"] if block["t"] == "Table")
    column_widths = [column[1]["c"] for column in table_ast["c"][2]]
    positioned_text = []
    positioned_counts = []
    for page in reader.pages:
        width = float(page.mediabox.width)
        count_cell_left = 72 + sum(column_widths[:2]) * (width - 144)

        def collect(text, cm, tm, _font, _size):
            if text.strip():
                # Apply the text origin through the current transformation matrix.
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                positioned_text.append((text, x))
                assert 72 - 0.1 <= x <= width - 72 + 0.1, (text, x, width)
                if text.strip() == str(sample_count):
                    positioned_counts.append(x)
                    assert x >= count_cell_left - 0.1, (text, x, count_cell_left)

        page.extract_text(visitor_text=collect)
    assert positioned_text
    assert len(positioned_counts) == condition_count
    assert source.read_bytes() == original
    assert receipt["input_sha256"] == hashlib.sha256(original).hexdigest()
    assert receipt["output_sha256"] == digest_file(output)

    # PDF wrapping is presentation only: Word retains the exact original cell values.
    word = source.with_suffix(".docx")
    conversion.convert(source, word, pandoc=pandoc)
    table = Document(word).tables[0]
    for index, row in enumerate(table.rows[1:]):
        assert row.cells[0].text == f"{metric} ({unit})"
        assert row.cells[1].text == conditions[index]
    assert source.read_bytes() == original
