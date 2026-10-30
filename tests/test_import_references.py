"""Bibliographic imports preserve supplied facts and feed the existing JSON CLI."""

import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
imports = importlib.import_module("import_references")
editorial = importlib.import_module("editorial_checks")


class ImportReferencesTests(unittest.TestCase):
    def test_bibtex_supplied_metadata_is_preserved(self):
        source = """@article{OriginalKey,
 title = {SOURCE Title},
 author = {Doe, Jane and 김, 상훈},
 year = 2024,
 doi = {10.1234/EXAMPLE},
 url = {https://example.org/Paper},
 note = {Keep this supplied note}
}"""
        result = imports.parse_bibliography(source, "bibtex")
        self.assertEqual(len(result["references"]), 1)
        record = result["references"][0]
        self.assertEqual(record["id"], 1)
        self.assertEqual(record["title"], "SOURCE Title")
        self.assertEqual(record["authors"], "Doe, Jane and 김, 상훈")
        self.assertEqual(str(record["year"]), "2024")
        self.assertEqual(record["doi"], "10.1234/EXAMPLE")
        self.assertEqual(record["url"], "https://example.org/Paper")
        self.assertEqual(record["source"]["key"], "OriginalKey")
        self.assertEqual(record["source"]["format"], "bibtex")
        self.assertEqual(record["source"]["raw"].strip(), source)

    def test_bibtex_braced_and_quoted_multiline_values(self):
        source = r'''@article{nested,
 title = {A {DNA} result and \alpha},
 author = "Doe, Jane",
 note = {First line
Second line with {nested braces}}
}
@misc{quoted, title = "A \"quoted\" title"}
'''
        records = imports.parse_bibliography(source, "bibtex")["references"]
        self.assertEqual(records[0]["title"], r"A {DNA} result and \alpha")
        self.assertEqual(records[0]["authors"], "Doe, Jane")
        self.assertIn("First line\nSecond line with {nested braces}", records[0]["source"]["raw"])
        self.assertEqual(records[1]["title"], r'A \"quoted\" title')

    def test_bibtex_explicit_string_macros_and_concatenation(self):
        source = """@string{prefix = {A Real }}
@string{publicationYear = "2024"}
@article{key, title = prefix # {Title}, year = publicationYear}
"""
        records = imports.parse_bibliography(source, "bibtex")["references"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "A Real Title")
        self.assertEqual(str(records[0]["year"]), "2024")

    def test_bibtex_tabs_preserve_values_and_original_record_boundaries(self):
        first = "@misc{one,\n\ttitle={A\tB}\n}"
        second = "@misc{two, title={Second}}"
        records = imports.parse_bibliography(first + "\n" + second, "bibtex")["references"]
        self.assertEqual(records[0]["title"], "A\tB")
        self.assertEqual([record["source"]["raw"] for record in records], [first, second])

    def test_undefined_bibtex_macro_is_not_invented(self):
        source = "@article{key, title = missingTitle, year = missingYear}"
        result = imports.parse_bibliography(source, "bibtex")
        record = result["references"][0]
        self.assertNotIn("title", record)
        self.assertNotIn("year", record)
        self.assertIn("missingTitle", record["source"]["raw"])
        self.assertIn("missingYear", record["source"]["raw"])
        self.assertTrue(any(item.get("reference_id") == 1
                            for item in result["manual_review_suggestions"]))

    def test_bibtex_incomplete_and_empty_records_survive(self):
        source = "@misc{partial, title={Only a supplied title}}\n@misc{empty,}"
        result = imports.parse_bibliography(source, "bibtex")
        records = result["references"]
        self.assertEqual([record["id"] for record in records], [1, 2])
        self.assertEqual(records[0]["title"], "Only a supplied title")
        for record in records:
            self.assertFalse({"authors", "year", "doi", "url"} & record.keys())
        self.assertNotIn("title", records[1])
        warning_ids = {item.get("reference_id") for item in result["manual_review_suggestions"]}
        self.assertTrue({1, 2} <= warning_ids)

    def test_duplicate_source_keys_remain_distinct_records(self):
        samples = {
            "bibtex": "@misc{same,title={First}}\n@misc{same,title={Second}}",
            "ris": "TY  - GEN\nID  - same\nTI  - First\nER  -\n"
                   "TY  - GEN\nID  - same\nTI  - Second\nER  -\n",
        }
        for format, source in samples.items():
            with self.subTest(format=format):
                records = imports.parse_bibliography(source, format)["references"]
                self.assertEqual([record["id"] for record in records], [1, 2])
                self.assertEqual([record["source"]["key"] for record in records], ["same", "same"])
                self.assertEqual([record["title"] for record in records], ["First", "Second"])

    def test_ris_author_order_aliases_and_original_metadata(self):
        source = """TY  - JOUR
ID  - source-id
T1  - SOURCE Title
AU  - Doe, Jane
A1  - 김, 상훈
AU  - Organization and Partners
PY  - 2024
DO  - 10.1234/EXAMPLE
UR  - https://example.org/Paper
N1  - Retain this original note
ER  -
"""
        record = imports.parse_bibliography(source, "ris")["references"][0]
        self.assertEqual(record["title"], "SOURCE Title")
        self.assertEqual(record["authors"], ["Doe, Jane", "김, 상훈", "Organization and Partners"])
        self.assertEqual(str(record["year"]), "2024")
        self.assertEqual(record["doi"], "10.1234/EXAMPLE")
        self.assertEqual(record["url"], "https://example.org/Paper")
        self.assertEqual(record["source"]["key"], "source-id")
        self.assertIn("N1  - Retain this original note", record["source"]["raw"])

    def test_ris_publication_dates_supply_only_the_given_year(self):
        for tag, date in [("PY", "2021"), ("PY", "2021/10/02"),
                          ("PY", "2021/10/02/"), ("Y1", "2021/10/02")]:
            with self.subTest(tag=tag, date=date):
                source = f"TY  - JOUR\n{tag}  - {date}\nER  -\n"
                record = imports.parse_bibliography(source, "ris")["references"][0]
                self.assertEqual(str(record["year"]), "2021")
                self.assertIn(date, record["source"]["raw"])

    def test_invalid_year_is_kept_in_source_without_a_numeric_guess(self):
        for year in ["99", "forthcoming", "2020--2021"]:
            samples = {
                "bibtex": f"@misc{{key, year={{{year}}}}}",
                "ris": f"TY  - JOUR\nPY  - {year}\nER  -\n",
            }
            for format, source in samples.items():
                with self.subTest(format=format, year=year):
                    result = imports.parse_bibliography(source, format)
                    self.assertEqual(len(result["references"]), 1)
                    record = result["references"][0]
                    self.assertNotIn("year", record)
                    self.assertIn(year, record["source"]["raw"])
                    self.assertTrue(any(item.get("reference_id") == 1
                                        for item in result["manual_review_suggestions"]))

    def test_ris_empty_record_has_no_fabricated_source_key(self):
        records = imports.parse_bibliography("TY  - GEN\nER  -\nTY  - GEN\nER  -\n", "ris")["references"]
        self.assertEqual([record["id"] for record in records], [1, 2])
        for record in records:
            self.assertNotIn("key", record["source"])
            self.assertFalse({"title", "authors", "year", "doi", "url"} & record.keys())

    def test_malformed_doi_is_preserved_for_editorial_check(self):
        records = imports.parse_bibliography("@misc{key,title={Source},doi={not-a-doi}}", "bibtex")["references"]
        self.assertEqual(records[0]["doi"], "not-a-doi")
        result = editorial.check_manuscript("# Article\nA source [1].\n## References\n[1] Source.\n", records)
        self.assertIn("malformed_metadata_doi", {item["code"] for item in result["structural_findings"]})

    def test_invalid_syntax_or_format_is_rejected(self):
        for format, source in [("bibtex", "@article{broken,title={Never closed}"),
                               ("ris", "TY  - JOUR\nTI  - Missing terminator\n"),
                               ("bibtex", ""), ("ris", " "),
                               ("json", "@misc{key,}")]:
            with self.subTest(format=format, source=source):
                with self.assertRaises(ValueError):
                    imports.parse_bibliography(source, format)

    def test_write_import_preserves_input_and_writes_existing_report_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "sources.bib", root / "imported"
            original = b"\xef\xbb\xbf@misc{key, title={Provided title}}\r\n"
            source.write_bytes(original)
            summary = imports.write_import(source, output)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(summary["network_requests"], 0)
            self.assertIsInstance(json.loads((output / "references.json").read_text(encoding="utf-8")), list)
            report = json.loads((output / "import-report.json").read_text(encoding="utf-8"))
            self.assertIsInstance(report["structural_findings"], list)
            self.assertTrue(report["manual_review_suggestions"])
            for item in report["structural_findings"] + report["manual_review_suggestions"]:
                self.assertIsInstance(item["code"], str)
                self.assertIsInstance(item["detail"], str)
            self.assertTrue((output / "import-report.md").is_file())

    def test_existing_output_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "sources.bib", root / "imported"
            source.write_text("@misc{key,}", encoding="utf-8")
            imports.write_import(source, output)
            saved = {path.name: path.read_bytes() for path in output.iterdir()}
            with self.assertRaises(FileExistsError):
                imports.write_import(source, output)
            self.assertEqual(saved, {path.name: path.read_bytes() for path in output.iterdir()})

    def test_extension_detection_and_explicit_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources.txt"
            source.write_text("TY  - GEN\nTI  - Supplied title\nER  -\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                imports.write_import(source, root / "undetected")
            self.assertFalse((root / "undetected").exists())
            imports.write_import(source, root / "explicit", format="ris")
            records = json.loads((root / "explicit" / "references.json").read_text(encoding="utf-8"))
            self.assertEqual(records[0]["title"], "Supplied title")

    def test_paths_must_be_absolute(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "sources.bib"
            source.write_text("@misc{key,}", encoding="utf-8")
            with self.assertRaises(ValueError):
                imports.write_import(source, Path("relative-output"))

    def test_cli_imports_feed_existing_json_workflow(self):
        samples = {
            "bib": "@article{key,title={Source Title},author={Doe, Jane},year=2024,doi={10.1234/example}}",
            "ris": "TY  - JOUR\nTI  - Source Title\nAU  - Doe, Jane\nPY  - 2024/10/02\nDO  - 10.1234/example\nER  -\n",
        }
        for extension, source_text in samples.items():
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, output = root / f"sources.{extension}", root / "imported"
                source.write_text(source_text, encoding="utf-8")
                imported = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "import_references.py"),
                     "--input", str(source), "--output-dir", str(output)],
                    cwd=root, capture_output=True, text=True, timeout=20)
                self.assertEqual(imported.returncode, 0, imported.stderr)
                self.assertEqual(json.loads(imported.stdout)["network_requests"], 0)
                manuscript = root / "article.md"
                manuscript.write_text("# Article\nA source [1].\n## References\n"
                                      "[1] Doe, Jane. Source Title. 2024. doi:10.1234/example\n",
                                      encoding="utf-8")
                checked = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "editorial_checks.py"), "check",
                     "--manuscript", str(manuscript), "--references-json", str(output / "references.json"),
                     "--output-dir", str(root / "editorial")],
                    cwd=root, capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual(json.loads(checked.stdout)["structural_findings"], 0)
                self.assertEqual(source.read_text(encoding="utf-8"), source_text)

    def test_cli_syntax_error_keeps_input_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "sources.bib", root / "imported"
            original = "@article{broken,title={Unclosed}"
            source.write_text(original, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "import_references.py"),
                 "--input", str(source), "--output-dir", str(output)],
                cwd=root, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIsInstance(json.loads(result.stderr)["error"], str)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
