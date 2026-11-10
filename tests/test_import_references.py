"""Bibliographic imports preserve supplied facts and feed the existing JSON CLI."""

import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pytest


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

    def test_bibtex_key_punctuation_and_outer_delimiters(self):
        key = "10.1016/S0167-2789(99)00000-4"
        for opening, closing in [("{", "}"), ("(", ")")]:
            with self.subTest(opening=opening):
                entry = f"@article{opening}{key}, title={{Supplied title}}{closing}"
                empty = f"@misc{opening}key=value{closing}"
                first, second = imports.parse_bibliography(entry + "\n" + empty, "bibtex")["references"]
                self.assertEqual((first["source"]["key"], first["source"]["raw"], first["title"]),
                                 (key, entry, "Supplied title"))
                self.assertEqual((second["source"]["key"], second["source"]["raw"]), ("key=value", empty))
                adjacent = imports.parse_bibliography(empty + entry, "bibtex")["references"]
                self.assertEqual([row["source"]["key"] for row in adjacent], ["key=value", key])

    def test_bibtex_key_characters_do_not_relax_macro_or_field_syntax(self):
        for invalid in ["@string{prefix=}", "@preamble(prefix=)",
                        "@misc{key=one,title=}", "@misc(key(x),title={Missing close}"]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                imports.parse_bibliography(invalid + "\n@misc{ok,title={Control}}", "bibtex")

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

    def test_cli_reference_ids_match_reversed_export_to_manuscript(self):
        samples = {
            "bib": "@article{second,title={Second Source},author={Roe, John},year=2025,doi={10.1234/second}}\n"
                   "@article{first,title={First Source},author={Doe, Jane},year=2024,doi={10.1234/first}}\n",
            "ris": "TY  - JOUR\nTI  - Second Source\nAU  - Roe, John\nPY  - 2025\nDO  - 10.1234/second\nER  -\n"
                   "TY  - JOUR\nTI  - First Source\nAU  - Doe, Jane\nPY  - 2024\nDO  - 10.1234/first\nER  -\n",
        }
        for extension, source_text in samples.items():
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, output = root / f"sources.{extension}", root / "imported"
                original = b"\xef\xbb\xbf" + source_text.replace("\n", "\r\n").encode("utf-8")
                source.write_bytes(original)
                imported = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "import_references.py"),
                     "--input", str(source), "--output-dir", str(output), "--reference-ids", "2", "1"],
                    cwd=root, capture_output=True, text=True, timeout=20)
                self.assertEqual(imported.returncode, 0, imported.stderr)
                self.assertEqual(json.loads(imported.stdout)["network_requests"], 0)
                records = json.loads((output / "references.json").read_text(encoding="utf-8"))
                self.assertEqual([record["id"] for record in records], [2, 1])
                self.assertEqual([record["title"] for record in records], ["Second Source", "First Source"])
                manuscript = root / "article.md"
                manuscript_bytes = ("# Article\nSources [1, 2].\n## References\n"
                                    "[1] Doe, Jane. First Source. 2024. doi:10.1234/first\n"
                                    "[2] Roe, John. Second Source. 2025. doi:10.1234/second\n").encode("utf-8")
                manuscript.write_bytes(manuscript_bytes)
                checked = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "editorial_checks.py"), "check",
                     "--manuscript", str(manuscript), "--references-json", str(output / "references.json"),
                     "--output-dir", str(root / "editorial")],
                    cwd=root, capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual(json.loads(checked.stdout)["network_requests"], 0)
                report = json.loads((root / "editorial" / "editorial-report.json").read_text(encoding="utf-8"))
                self.assertEqual(report["structural_findings"], [])
                self.assertFalse(any(item["code"].startswith("metadata_")
                                     for item in report["manual_review_suggestions"]))
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(manuscript.read_bytes(), manuscript_bytes)

    def test_explicit_reference_ids_are_used_by_all_record_warnings(self):
        samples = {
            "bibtex": "@misc{same,doi={bad-one}}\n@misc{same,doi={bad-two}}",
            "ris": "TY  - GEN\nID  - same\nDO  - bad-one\nER  -\n"
                   "TY  - GEN\nID  - same\nDO  - bad-two\nER  -\n",
        }
        for format, source in samples.items():
            with self.subTest(format=format):
                result = imports.parse_bibliography(source, format, reference_ids=[7, 3])
                self.assertEqual([record["id"] for record in result["references"]], [7, 3])
                warnings = result["structural_findings"] + result["manual_review_suggestions"]
                for code in ("malformed_metadata_doi", "incomplete_reference_metadata"):
                    self.assertEqual({item["reference_id"] for item in warnings if item["code"] == code}, {7, 3})
                duplicates = [item for item in warnings if item["code"] == "duplicate_source_key"]
                self.assertEqual(len(duplicates), 1)
                self.assertEqual(duplicates[0]["reference_ids"], [7, 3])
                for item in warnings:
                    if "reference_id" in item:
                        self.assertIn(item["reference_id"], {7, 3})
                    if "reference_ids" in item:
                        self.assertTrue(set(item["reference_ids"]) <= {7, 3})

    def test_invalid_reference_ids_fail_before_output_and_preserve_input(self):
        samples = {
            "bib": "@misc{first,}\n@misc{second,}\n",
            "ris": "TY  - GEN\nER  -\nTY  - GEN\nER  -\n",
        }
        invalid_ids = [[], [7], [7, 3, 9], [7, 7], [0, 3], [-7, 3],
                       [True, 3], [7, False], [7, "3"], [7, 3.0]]
        for extension, source_text in samples.items():
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / f"sources.{extension}"
                original = b"\xef\xbb\xbf" + source_text.replace("\n", "\r\n").encode("utf-8")
                source.write_bytes(original)
                for index, reference_ids in enumerate(invalid_ids):
                    with self.subTest(extension=extension, reference_ids=reference_ids):
                        output = root / f"invalid-{index}"
                        with self.assertRaises(ValueError):
                            imports.write_import(source, output, reference_ids=reference_ids)
                        self.assertFalse(output.exists())
                        self.assertEqual(source.read_bytes(), original)


    def test_csl_json_maps_supplied_fields_names_and_original_record(self):
        original = {
            "id": 41,
            "type": "article-journal",
            "title": "Original {DNA} TITLE",
            "author": [
                {"given": "Jane", "family": "Doe"},
                {"family": "Cruz", "suffix": "Jr.", "non-dropping-particle": "la",
                 "given": "Juan", "dropping-particle": "de"},
                {"literal": "Research and Development Group", "given": "Unselected", "family": "Name"},
                {"family": "김"},
                {"given": "Plato"},
            ],
            "issued": {"date-parts": [[2024, 10, 30]]},
            "DOI": "10.1234/EXAMPLE",
            "URL": "https://example.org/Paper",
            "container-title": "Supplied Journal",
            "note": "Retain this unmapped source field",
        }
        result = imports.parse_bibliography(json.dumps([original], ensure_ascii=False), "csl-json")
        self.assertEqual(len(result["references"]), 1)
        record = result["references"][0]
        self.assertEqual(record["id"], 1)
        self.assertEqual(record["source"]["key"], 41)
        self.assertEqual(record["source"]["format"], "csl-json")
        self.assertEqual(json.loads(record["source"]["raw"]), original)
        self.assertEqual(record["title"], original["title"])
        self.assertEqual(record["authors"], ["Jane Doe", "Juan de la Cruz Jr.",
                                             "Research and Development Group", "김", "Plato"])
        self.assertEqual(record["year"], "2024")
        self.assertEqual(record["doi"], original["DOI"])
        self.assertEqual(record["url"], original["URL"])

    def test_csl_json_retains_incomplete_and_unmapped_metadata(self):
        originals = [
            {},
            {"id": 1.5, "title": None, "author": None, "issued": None,
             "DOI": None, "URL": None, "note": "Only supplied source material"},
            {"title": 17, "DOI": False, "URL": [],
             "author": [{}, "not a name object", {"family": 5},
                        {"given": "Do not map this partial name", "family": True},
                        {"family": "Valid family"}]},
            {"author": {"given": "Wrong container"}},
        ]
        result = imports.parse_bibliography(json.dumps(originals), "csl-json")
        records = result["references"]
        self.assertEqual([record["id"] for record in records], [1, 2, 3, 4])
        self.assertEqual([json.loads(record["source"]["raw"]) for record in records], originals)
        self.assertEqual(records[1]["source"]["key"], 1.5)
        for index in (0, 1, 3):
            self.assertFalse({"title", "authors", "year", "doi", "url"} & records[index].keys())
        self.assertFalse({"title", "year", "doi", "url"} & records[2].keys())
        self.assertEqual(records[2]["authors"], ["Valid family"])
        suggestions = result["manual_review_suggestions"]
        self.assertEqual({item["reference_id"] for item in suggestions
                          if item["code"] == "unmapped_csl_metadata"}, {3, 4})
        self.assertEqual({item["reference_id"] for item in suggestions
                          if item["code"] == "incomplete_reference_metadata"}, {1, 2, 3, 4})
        self.assertFalse(any(item["code"] == "unmapped_metadata_year" for item in suggestions))

    def test_csl_json_maps_only_one_explicit_publication_year(self):
        supported = [
            {"date-parts": [[2024]]},
            {"date-parts": [["2024", 10, 30]]},
            {"date-parts": [[2024, 10]], "circa": False},
        ]
        unsupported = [
            {"date-parts": [[2024], [2025]]},
            {"raw": "2024"},
            {"literal": "2024"},
            {"date-parts": [[]]},
            {"date-parts": [[99]]},
            {"date-parts": [[True]]},
            {"date-parts": [[2024.5]]},
            {"date-parts": [[2024, 10, 30, 1]]},
            {"date-parts": [[2024]], "circa": True},
            "2024",
        ]
        for issued in supported + unsupported:
            with self.subTest(issued=issued):
                original = {"issued": issued}
                result = imports.parse_bibliography(json.dumps([original]), "csl-json")
                record = result["references"][0]
                self.assertEqual(json.loads(record["source"]["raw"]), original)
                year_warnings = [item for item in result["manual_review_suggestions"]
                                 if item["code"] == "unmapped_metadata_year"]
                if issued in supported:
                    self.assertEqual(record["year"], "2024")
                    self.assertEqual(year_warnings, [])
                else:
                    self.assertNotIn("year", record)
                    self.assertTrue(year_warnings)
                    self.assertTrue(all(item["reference_id"] == 1 for item in year_warnings))

    def test_csl_json_warnings_and_duplicate_keys_use_assigned_reference_ids(self):
        originals = [
            {"id": "same", "DOI": "bad-one", "title": 7, "issued": {"date-parts": [[99]]}},
            {"id": "same", "DOI": "bad-two", "author": {"family": "Wrong container"}},
        ]
        result = imports.parse_bibliography(json.dumps(originals), "csl-json", reference_ids=[7, 3])
        self.assertEqual([record["id"] for record in result["references"]], [7, 3])
        self.assertEqual([record["source"]["key"] for record in result["references"]], ["same", "same"])
        warnings = result["structural_findings"] + result["manual_review_suggestions"]
        for code in ("malformed_metadata_doi", "incomplete_reference_metadata", "unmapped_csl_metadata"):
            self.assertEqual({item["reference_id"] for item in warnings if item["code"] == code}, {7, 3})
        self.assertEqual({item["reference_id"] for item in warnings
                          if item["code"] == "unmapped_metadata_year"}, {7})
        duplicates = [item for item in warnings if item["code"] == "duplicate_source_key"]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["reference_ids"], [7, 3])
        for item in warnings:
            if "reference_id" in item:
                self.assertIn(item["reference_id"], {7, 3})
            if "reference_ids" in item:
                self.assertTrue(set(item["reference_ids"]) <= {7, 3})

    def test_csl_json_cli_connects_to_checker_with_explicit_numbering(self):
        originals = [
            {"id": "second", "title": "Second Source", "author": [{"literal": "Research Group"}],
             "issued": {"date-parts": [[2025]]}, "DOI": "10.1234/second", "URL": "https://example.org/second"},
            {"id": 71, "title": "First Source", "author": [{"given": "Jane", "family": "Doe"}],
             "issued": {"date-parts": [[2024, 10, 30]]}, "DOI": "10.1234/first", "URL": "https://example.org/first"},
        ]
        original_bytes = b"\xef\xbb\xbf" + json.dumps(originals, indent=2).replace("\n", "\r\n").encode("utf-8")
        expected_hash = hashlib.sha256(original_bytes).hexdigest()
        for extension, options in [("json", []), ("txt", ["--format", "csl-json"])]:
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, output = root / f"sources.{extension}", root / "imported"
                source.write_bytes(original_bytes)
                imported = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "import_references.py"),
                     "--input", str(source), "--output-dir", str(output), "--reference-ids", "2", "1", *options],
                    cwd=root, capture_output=True, text=True, timeout=20)
                self.assertEqual(imported.returncode, 0, imported.stderr)
                summary = json.loads(imported.stdout)
                self.assertEqual(summary["network_requests"], 0)
                self.assertEqual(summary["source_input_sha256"], expected_hash)
                import_report = json.loads((output / "import-report.json").read_text(encoding="utf-8"))
                self.assertEqual(import_report["source_input_sha256"], expected_hash)
                records = json.loads((output / "references.json").read_text(encoding="utf-8"))
                self.assertEqual([record["id"] for record in records], [2, 1])
                self.assertEqual([json.loads(record["source"]["raw"]) for record in records], originals)
                manuscript = root / "article.md"
                manuscript_bytes = ("# Article\nSources [1, 2].\n## References\n"
                                    "[1] Jane Doe. First Source. 2024. doi:10.1234/first https://example.org/first\n"
                                    "[2] Research Group. Second Source. 2025. doi:10.1234/second https://example.org/second\n").encode("utf-8")
                manuscript.write_bytes(manuscript_bytes)
                checked = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "editorial_checks.py"), "check",
                     "--manuscript", str(manuscript), "--references-json", str(output / "references.json"),
                     "--output-dir", str(root / "editorial")],
                    cwd=root, capture_output=True, text=True, timeout=20)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                self.assertEqual(json.loads(checked.stdout)["network_requests"], 0)
                editorial_report = json.loads((root / "editorial" / "editorial-report.json").read_text(encoding="utf-8"))
                self.assertEqual(editorial_report["structural_findings"], [])
                self.assertFalse(any(item["code"].startswith("metadata_")
                                     for item in editorial_report["manual_review_suggestions"]))
                self.assertEqual(source.read_bytes(), original_bytes)
                self.assertEqual(manuscript.read_bytes(), manuscript_bytes)

    def test_csl_json_invalid_input_is_rejected_before_output(self):
        for text in ('{"broken":', '{}', '[null]', '[{}, 3]', '[]'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, output = root / "sources.json", root / "imported"
                original = b"\xef\xbb\xbf" + text.encode("utf-8") + b"\r\n"
                source.write_bytes(original)
                with self.assertRaises(ValueError):
                    imports.write_import(source, output)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), original)


    def test_bibtex_cli_doi_autolinks_match_assigned_reference_numbers(self):
        source_text = (
            "@article{second,title={Second Source},author={Roe, John},year=2025,"
            "doi={10.1234/second},url={https://doi.org/10.1234/second}}\n"
            "@article{first,title={First Source},author={Doe, Jane},year=2024,"
            "doi={10.1234/first},url={https://doi.org/10.1234/first}}\n")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "sources.bib", root / "imported"
            original_source = source_text.encode("utf-8")
            source.write_bytes(original_source)
            imported = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "import_references.py"),
                 "--input", str(source), "--output-dir", str(output), "--reference-ids", "2", "1"],
                cwd=root, capture_output=True, text=True, timeout=20)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(json.loads(imported.stdout)["network_requests"], 0)
            references_file = output / "references.json"
            original_json = references_file.read_bytes()
            records = json.loads(original_json)
            self.assertEqual([record["id"] for record in records], [2, 1])
            manuscript = root / "article.md"
            original_manuscript = (
                "# Article\nSources [1, 2].\n## References\n"
                "[1] Doe, Jane. First Source. 2024. <https://doi.org/10.1234/first>\n"
                "[2] Roe, John. Second Source. 2025. <https://doi.org/10.1234/second>\n"
            ).encode("utf-8")
            manuscript.write_bytes(original_manuscript)
            checked = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "editorial_checks.py"), "check",
                 "--manuscript", str(manuscript), "--references-json", str(references_file),
                 "--output-dir", str(root / "editorial")],
                cwd=root, capture_output=True, text=True, timeout=20)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["network_requests"], 0)
            report = json.loads((root / "editorial" / "editorial-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["structural_findings"], [])
            self.assertFalse(any(item["code"].startswith("metadata_")
                                 for item in report["manual_review_suggestions"]))
            self.assertEqual(report["metrics"]["reference_entries"], 2)
            self.assertEqual(report["metrics"]["recognized_body_citations"], [1, 2])
            self.assertEqual(source.read_bytes(), original_source)
            self.assertEqual(references_file.read_bytes(), original_json)
            self.assertEqual(manuscript.read_bytes(), original_manuscript)

    def test_doi_autolinks_keep_real_malformed_mismatch_and_duplicate_findings(self):
        references = json.loads("""[
            {"id": 1, "title": "Bad Source", "doi": "not-a-doi"},
            {"id": 2, "title": "Second Source", "doi": "10.1234/other"},
            {"id": 3, "title": "Third Source", "doi": "10.1234/actual"}
        ]""")
        original_json = json.dumps(references)
        manuscript = (
            "# Article\nSources [1, 2, 3].\n## References\n"
            "[1] Bad Source. <https://doi.org/not-a-doi>\n"
            "[2] Second Source. <https://doi.org/10.1234/actual>\n"
            "[3] Third Source. <https://doi.org/10.1234/actual>\n")
        result = editorial.check_manuscript(manuscript, references)
        findings = result["structural_findings"]
        self.assertEqual({item["reference_id"] for item in findings
                          if item["code"] == "malformed_doi"}, {1})
        self.assertEqual({item["reference_id"] for item in findings
                          if item["code"] == "malformed_metadata_doi"}, {1})
        self.assertEqual({item["reference_id"] for item in findings
                          if item["code"] == "metadata_doi_mismatch"}, {2})
        self.assertEqual([item["reference_ids"] for item in findings
                          if item["code"] == "duplicate_doi"], [[2, 3]])
        self.assertEqual(json.dumps(references), original_json)


_BIBTEX_ENTRY_COMMENT = '% ignored } ) , = # @ " @misc{phantom,title="unterminated\n'


@pytest.mark.parametrize("opening,closing", [("{", "}"), ("(", ")")], ids=["braces", "parentheses"])
@pytest.mark.parametrize("fields", [
    "<comment>title={Source},year=2024",
    "title <comment>={Source},year=2024",
    "title= <comment>{Source},year=2024",
    "title={Source} <comment>,year=2024",
    "title={Source}, <comment>year=2024",
    "title={Source},year=2024 <comment>",
    "title={Source},year=2024, <comment>",
], ids=["before-first-field", "before-equals", "before-value", "before-comma",
        "after-comma", "after-last-value", "after-last-comma"])
def test_bibtex_entry_comments_accept_field_boundaries(opening, closing, fields):
    entry = "@article" + opening + "key," + fields.replace("<comment>", _BIBTEX_ENTRY_COMMENT) + closing

    records = imports.parse_bibliography(entry, "bibtex")["references"]

    assert len(records) == 1
    assert records[0]["title"] == "Source"
    assert records[0]["year"] == "2024"
    assert records[0]["source"] == {"format": "bibtex", "key": "key", "raw": entry}


@pytest.mark.parametrize("opening,closing", [("{", "}"), ('"', '"')], ids=["braced", "quoted"])
@pytest.mark.parametrize("payload", [
    r"% leading literal with {nested {DNA}} and \%",
    "First\tline\n% literal at line start\nLast {DNA} with 50% and \\%",
    r'50% completion with {nested {DNA}}, \"quoted\" and \%',
], ids=["leading-percent", "multiline-percent", "inline-percent"])
@pytest.mark.parametrize("outside_comment", [False, True], ids=["existing-literal", "with-comment"])
def test_bibtex_entry_comments_preserve_literal_percent(opening, closing, payload, outside_comment):
    url = "https://example.org/a%20b?value=%7Bdata%7D#part"
    between = _BIBTEX_ENTRY_COMMENT if outside_comment else ""
    entry = ("@article{literal,title=" + opening + payload + closing + "," + between +
             "url=" + opening + url + closing + "}")

    records = imports.parse_bibliography(entry, "bibtex")["references"]

    assert len(records) == 1
    assert records[0]["title"] == payload
    assert records[0]["url"] == url
    assert records[0]["source"]["raw"] == entry


@pytest.mark.parametrize("separator", [
    " <comment># ",
    " # <comment>",
    " <comment># <comment>",
], ids=["before-hash", "after-hash", "both-sides"])
def test_bibtex_entry_comments_preserve_supplied_macros_and_concatenation(separator):
    definitions = ('@string{prefix={A 50% }}\n'
                   '@string{suffix="\\% {DNA}"}\n'
                   '@string{publicationYear="2024"}\n')
    expression = separator.replace("<comment>", _BIBTEX_ENTRY_COMMENT).join(
        ["PreFiX", "{Title }", "SuFfIx"])
    entry = "@article{key,title=" + expression + ",year=PublicationYear}"

    result = imports.parse_bibliography(definitions + entry, "bibtex")
    records = result["references"]

    assert len(records) == 1
    assert records[0]["title"] == r"A 50% Title \% {DNA}"
    assert records[0]["year"] == "2024"
    assert records[0]["source"]["raw"] == entry
    assert not any(item["code"] == "unresolved_bibtex_string"
                   for item in result["manual_review_suggestions"])


def test_bibtex_entry_comments_do_not_define_unsupplied_macros():
    first = ('@article{first,title=notDefined, '
             '% @string{notDefined={Counterfeit}}\nyear=2024}')
    definition = "@string{notDefined={Supplied later}}"
    second = "@article{second,title=notDefined}"

    result = imports.parse_bibliography("\n".join([first, definition, second]), "bibtex")
    records = result["references"]

    assert [record["source"]["key"] for record in records] == ["first", "second"]
    assert [record["source"]["raw"] for record in records] == [first, second]
    assert "title" not in records[0]
    assert records[1]["title"] == "Supplied later"
    assert [item["reference_id"] for item in result["manual_review_suggestions"]
            if item["code"] == "unresolved_bibtex_string"] == [1]


def test_bibtex_entry_comments_preserve_raw_boundaries_tabs_crlf_and_input_bytes(tmp_path):
    comment = _BIBTEX_ENTRY_COMMENT.replace("\n", "\r\n")
    first = ("@article{one,\r\n\t" + comment +
             "\ttitle=label # {원본\t50%\r\n% 값 안의 줄\r\n{DNA}}, " + comment +
             "\tyear=2024\r\n}")
    second = ('@misc(two,\r\n\ttitle="{Second}\t\\% value", ' + comment +
              "\turl={https://example.org/a%20b}\r\n)")
    text = ("% outside @misc{not-a-record,title=ignored}\r\n"
            "@string{label={김\t}, " + comment + "}\r\n" + first +
            "\r\n% between @string{label={Ignored}}\r\n" + second +
            "\r\n% after @misc{also-ignored}\r\n")
    original = b"\xef\xbb\xbf" + text.encode("utf-8")
    source, output = tmp_path / "sources.bib", tmp_path / "imported"
    source.write_bytes(original)

    summary = imports.write_import(source, output, reference_ids=[7, 3])
    records = json.loads((output / "references.json").read_text(encoding="utf-8"))
    report = json.loads((output / "import-report.json").read_text(encoding="utf-8"))

    assert [record["id"] for record in records] == [7, 3]
    assert [record["source"]["key"] for record in records] == ["one", "two"]
    assert [record["source"]["raw"] for record in records] == [first, second]
    assert records[0]["title"] == "김\t원본\t50%\r\n% 값 안의 줄\r\n{DNA}"
    assert records[1]["title"] == "{Second}\t\\% value"
    assert records[1]["url"] == "https://example.org/a%20b"
    assert summary["reference_count"] == 2
    assert summary["source_input_sha256"] == hashlib.sha256(original).hexdigest()
    assert report["source_input_sha256"] == summary["source_input_sha256"]
    assert summary["source_rewritten"] is False
    assert report["source_rewritten"] is False
    assert summary["network_requests"] == report["network_requests"] == 0
    assert source.read_bytes() == original


@pytest.mark.parametrize("text", [
    "@article{key,title={Source} % only fake }\n",
    "@article{key,title={Source} % only fake ,\nyear=2024}",
    "@article{key,title % only fake =\n{Source}}",
    "@article{key,title= % only fake {Source}\n,year=2024}",
    "@article{key,title={Source} # % only fake {Suffix}\n}",
    "@article{key, % outside\ntitle={No closing brace\n",
    '@article{key, % outside\ntitle="No closing quote\n',
], ids=["missing-entry-close", "missing-comma", "missing-equals", "missing-value",
        "missing-concatenation-part", "unclosed-braced-value", "unclosed-quoted-value"])
def test_bibtex_entry_comments_cannot_repair_malformed_input(text, tmp_path):
    source, output = tmp_path / "invalid.bib", tmp_path / "imported"
    original = text.encode("utf-8")
    source.write_bytes(original)

    with pytest.raises(ValueError, match="Invalid BibTeX"):
        imports.write_import(source, output)

    assert not output.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize("newline,bom", [("\n", b""), ("\r\n", b"\xef\xbb\xbf")], ids=["lf", "crlf-bom"])
@pytest.mark.parametrize("entry,line,column,expected", [
    ("@article{broken,\n  title={Retained}\n  year=2024\n}", 5, 3, "Expected '}'"),
    ("@article{broken,\n  title {Retained},\n  year=2024\n}", 4, 9, "Expected '='"),
    ("@article{broken,\n  title={Retained},\n  year= % ignored } , = # @fake\n}", 6, 1, None),
    ("@article{broken,\n  title={Retained} # % ignored {Suffix}\n}\n",
     4, 20, "Expected a BibTeX value after '#'"),
    # End at the value: nested_expr versions differ in trailing whitespace consumption.
    ("@article{broken,\n  title={No closing brace", 4, 26, "Expected '}'"),
    ('@article{broken,\n  title="No closing quote\n', 5, 1, "Expected '\"'"),
    ("@article{broken,\n  title={Retained}\n", 5, 1, "Expected '}'"),
    ("@article(broken,\n  title={Retained}\n", 5, 1, "Expected ')'"),
], ids=["missing-comma", "missing-equals", "missing-value", "dangling-concatenation",
        "unclosed-braced-value", "unclosed-quoted-value", "unclosed-entry-brace", "unclosed-entry-parenthesis"])
def test_bibtex_error_location_reports_failed_syntax_without_output(
        entry, line, column, expected, newline, bom, tmp_path):
    text = "% supplied header\n\n" + entry
    original = bom + text.replace("\n", newline).encode("utf-8")
    source, output = tmp_path / "invalid.bib", tmp_path / "imported"
    source.write_bytes(original)

    with pytest.raises(ValueError) as failure:
        imports.write_import(source, output)

    assert not output.exists()
    assert source.read_bytes() == original
    message = str(failure.value)
    assert message.startswith(f"Invalid BibTeX at line {line}, column {column}:")
    if expected is not None:
        assert expected in message


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_bibtex_error_location_uses_original_second_entry_offsets(newline, tmp_path):
    text = ("% bibliography\n"
            "@misc{first,\n"
            "  title={첫 원고 50%}\n"
            "}\n"
            "\n"
            "% second entry follows\n"
            "@article{broken,\n"
            "\ttitle={한글} # % missing value\n"
            "}\n")
    source, output = tmp_path / "two-entries.bib", tmp_path / "imported"
    original = text.replace("\n", newline).encode("utf-8")
    source.write_bytes(original)

    with pytest.raises(ValueError) as failure:
        imports.write_import(source, output)

    assert not output.exists()
    assert source.read_bytes() == original
    # Columns follow source characters: the tab is one character, as are 한 and 글.
    assert str(failure.value).startswith("Invalid BibTeX at line 8, column 13:")


if __name__ == "__main__":
    unittest.main()
