"""Research-journal Word structure, citation content and layout invariants."""

from io import BytesIO
from pathlib import Path
import sys
from xml.etree import ElementTree
import zipfile

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _publication_research_word import apply_research_styles, native_structure


def reference(tmp_path, venue):
    """Synthetic publisher-style fixtures contain no redistributed templates."""
    doc = Document()
    names = (["Paper Title", "AU", "Abstract", "IT", "PARA", "H1_List (No Space)",
              "H1_List (Space)", "H1", "H2_First", "H2_Cont", "AU_Bios", "Fig Caption", "Table Caption", "References"]
             if venue == "ieee-access" else ["UP Paper Title", "UP Section Heading"])
    for name in names:
        if name not in doc.styles:
            doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH).base_style = doc.styles["Normal"]
    doc.styles.add_style("Verbatim Char", WD_STYLE_TYPE.CHARACTER)
    doc.styles.add_style("Source Code", WD_STYLE_TYPE.PARAGRAPH)
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.27), Inches(11.69)
    section.left_margin = section.right_margin = Inches(1)
    section.header.paragraphs[0].text = "SAMPLE AUTHOR AND PUBLICATION DATE"
    section.footer.paragraphs[0].text = "VOLUME XX"
    if venue == "ieee-access":
        doc.add_section(WD_SECTION_START.CONTINUOUS)._sectPr.find(qn("w:cols")).set(qn("w:num"), "2")
        # Existing synthetic numbering suffices to exercise independent list
        # instances; the actual publisher A/B pattern is checked with its file.
        doc.styles["H2_First"].element.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 1
    path = tmp_path / f"{venue}-synthetic-reference.docx"
    doc.save(path)
    return path


def authored(tmp_path, venue, template):
    doc = Document(template)
    for child in list(doc._element.body):
        if child.tag != qn("w:sectPr"):
            doc._element.body.remove(child)
    doc.add_paragraph("A supported software result", "Heading 1")
    doc.add_paragraph("A. Author | Retained Research Laboratory")
    doc.add_paragraph("Abstract", "Heading 2")
    doc.add_paragraph("A concrete retained result supports a bounded software decision.")
    doc.add_paragraph("Keywords: software; architecture; testing")
    doc.add_paragraph("Introduction", "Heading 2")
    body = doc.add_paragraph()
    body.add_run("The result survives ").bold = True
    body.add_run("review. [1], [2]")
    code = doc.add_paragraph("Literal code remains. ")
    code.add_run("[1]").style = doc.styles["Verbatim Char"]
    doc.add_paragraph("Example program. [1]", "Source Code")
    doc.add_paragraph("An unbound number remains. [9]")
    doc.add_paragraph("References", "Heading 2")
    doc.add_paragraph("[1] A. Writer, Retained source, 2025.")
    doc.add_paragraph("[2] B. Writer, Independent source, 2026.")
    if venue == "jors":
        # The actual publisher reference omits these standard definitions;
        # Pandoc retains their IDs in the document paragraphs nevertheless.
        doc.styles["Heading 1"].delete()
        doc.styles["Heading 2"].delete()
    path = tmp_path / f"{venue}-article.docx"
    doc.save(path)
    return path


@pytest.mark.parametrize("venue", ["ieee-access", "jors"])
def test_maps_selected_publisher_without_losing_content(tmp_path, venue):
    template = reference(tmp_path, venue)
    path = authored(tmp_path, venue, template)
    doc = Document(path)
    equation = doc.add_paragraph("As established. ")
    math, run, text = (OxmlElement(name) for name in ("m:oMath", "m:r", "m:t"))
    text.text = "x"
    run.append(text)
    math.append(run)
    equation._p.append(math)
    equation.add_run("[1].")
    next(p for p in doc.paragraphs if p.text == "References")._p.addprevious(equation._p)
    math_xml = ElementTree.tostring(math)
    doc.save(path)
    original_template = template.read_bytes()
    proof = apply_research_styles(path, template, venue)
    doc = Document(path)
    assert template.read_bytes() == original_template
    assert native_structure(path, venue)["issues"] == []
    assert native_structure(path, venue)["reference_count"] == 2
    body = next(p for p in doc.paragraphs if p.text.startswith("The result"))
    assert body.text == ("The result survives review [1], [2]." if venue == "ieee-access"
                         else "The result survives review (1, 2).")
    assert body.runs[0].bold
    equation = next(p for p in doc.paragraphs if p.text.startswith("As established"))
    assert "".join(equation._p.xpath("./w:r/w:t/text() | ./m:oMath//m:t/text()")) == (
        "As established. x [1]." if venue == "ieee-access" else "As established. x (1).")
    assert ElementTree.tostring(equation._p.xpath("./m:oMath")[0]) == math_xml
    assert next(p for p in doc.paragraphs if p.text.startswith("Literal code")).text.endswith(". [1]")
    assert next(p for p in doc.paragraphs if p.style.name == "Source Code").text.endswith(". [1]")
    assert next(p for p in doc.paragraphs if p.text.startswith("An unbound")).text.endswith(". [9]")
    assert proof["citation_typography"]["unknown_reference_numbers_preserved"] == ["9"]
    assert proof["measurement_styles"] == {"abstract": "Abstract", "references": "References"}
    refs = [p for p in doc.paragraphs if p.style.name == "References"]
    assert refs[0].text.startswith("[1] " if venue == "ieee-access" else "1. ")
    assert all(p._p.xpath("./w:pPr/w:numPr/w:numId/@w:val") == ["0"] for p in refs)
    if venue == "ieee-access":
        assert next(p for p in doc.paragraphs if p.style.name == "Abstract").text.startswith("ABSTRACT ")
        assert next(p for p in doc.paragraphs if p.style.name == "IT").text == "INDEX TERMS architecture, software, testing"
    else:
        assert next(p for p in doc.paragraphs if p.text == "Abstract").style.name == "UP Section Heading"
        assert doc.styles["Abstract"].base_style.name == "Normal"
        assert doc.styles["References"].base_style.name == "Normal"
    with zipfile.ZipFile(path) as package:
        assert not any(name.startswith(("word/header", "word/footer")) for name in package.namelist())


@pytest.mark.parametrize("venue", ["ieee-access", "jors"])
def test_tables_and_figures_fit_without_replacing_media_or_prose(tmp_path, venue):
    template = reference(tmp_path, venue)
    path = authored(tmp_path, venue, template)
    doc = Document(path)
    refs = next(p for p in doc.paragraphs if p.text == "References")
    stream = BytesIO()
    Image.new("RGB", (600, 120), "navy").save(stream, format="PNG")
    image_bytes = stream.getvalue()
    picture_paragraph = doc.add_paragraph()
    picture_paragraph.add_run().add_picture(BytesIO(image_bytes), width=Inches(9))
    refs._p.addprevious(picture_paragraph._p)
    table = doc.add_table(rows=2, cols=2)
    for row_index, row in enumerate(table.rows):
        for col_index, cell in enumerate(row.cells):
            cell.text = f"retained cell {row_index}:{col_index}"
    # Match Pandoc's highlighted Python runs, which do not use Verbatim Char.
    for name in ("NormalTok", "DecValTok"):
        doc.styles.add_style(name, WD_STYLE_TYPE.CHARACTER)
    code = table.cell(1, 0).add_paragraph(style="Source Code")
    for text, style in (("result = [", "NormalTok"), ("1", "DecValTok"), ("]", "NormalTok")):
        code.add_run(text).style = doc.styles[style]
    refs._p.addprevious(table._tbl)
    caption = doc.add_paragraph("Table 1. Retained content")
    if venue == "ieee-access":
        table._tbl.addnext(caption._p)
    else:
        table._tbl.addprevious(caption._p)
    doc.save(path)
    code_runs = [run._r.xml for run in Document(path).tables[0].cell(1, 0).paragraphs[-1].runs]
    proof = apply_research_styles(path, template, venue)
    doc = Document(path)
    table = doc.tables[0]
    assert [[cell.text for cell in row.cells] for row in table.rows] == [
        ["retained cell 0:0", "retained cell 0:1"], ["retained cell 1:0\nresult = [1]", "retained cell 1:1"]]
    code = table.cell(1, 0).paragraphs[-1]
    assert code.style.name == "Source Code"
    assert [run._r.xml for run in code.runs] == code_runs
    assert proof["citation_typography"]["callout_groups_formatted"] == 1
    caption = next(p for p in doc.paragraphs if p.text.startswith("Table 1."))
    assert (caption._p.getnext() is table._tbl if venue == "ieee-access" else table._tbl.getnext() is caption._p)
    assert native_structure(path, venue)["issues"] == []
    section = next((s for s in doc.sections if s._sectPr.find(qn("w:cols")).get(qn("w:num")) == "2"), doc.sections[0])
    width = int(section.page_width - section.left_margin - section.right_margin)
    if venue == "ieee-access":
        from docx.shared import Twips
        width = (width - Twips(int(section._sectPr.find(qn("w:cols")).get(qn("w:space"))))) // 2
    assert doc.inline_shapes[0].width <= width
    assert abs(doc.inline_shapes[0].width - doc.inline_shapes[0].height * 5) < 5
    with zipfile.ZipFile(path) as package:
        assert image_bytes in [package.read(name) for name in package.namelist() if name.startswith("word/media/")]


@pytest.mark.parametrize("venue", ["ieee-access", "jors"])
def test_inspector_rejects_broken_labels_layout_and_callouts(tmp_path, venue):
    template = reference(tmp_path, venue)
    path = authored(tmp_path, venue, template)
    apply_research_styles(path, template, venue)
    doc = Document(path)
    refs = [p for p in doc.paragraphs if p.style.name == "References"]
    refs[1].text = refs[0].text
    next(p for p in doc.paragraphs if p.text.startswith("The result")).text = (
        "A retained result. [1]" if venue == "ieee-access" else "A retained result. (1)")
    for section in doc.sections:
        section._sectPr.find(qn("w:cols")).set(qn("w:num"), "1" if venue == "ieee-access" else "2")
    doc.save(path)
    issues = native_structure(path, venue)["issues"]
    assert len(issues) == 3
    assert any("sequential" in issue for issue in issues)
    assert any("column" in issue for issue in issues)
    assert any("punctuation" in issue for issue in issues)


def test_rejects_empty_abstract_without_overwriting_output(tmp_path):
    template = reference(tmp_path, "jors")
    path = authored(tmp_path, "jors", template)
    doc = Document(path)
    next(p for p in doc.paragraphs if p.text.startswith("A concrete retained")).text = ""
    doc.save(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="abstract is empty"):
        apply_research_styles(path, template, "jors")
    assert path.read_bytes() == before


def test_access_subheading_numbering_restarts_each_section(tmp_path):
    template = reference(tmp_path, "ieee-access")
    path = authored(tmp_path, "ieee-access", template)
    doc = Document(path)
    refs = next(p for p in doc.paragraphs if p.text == "References")
    for text, style in [("First subsection", "Heading 3"), ("Second subsection", "Heading 3"),
                        ("Another section", "Heading 2"), ("Restarted subsection", "Heading 3")]:
        paragraph = doc.add_paragraph(text, style)
        refs._p.addprevious(paragraph._p)
    doc.save(path)
    apply_research_styles(path, template, "ieee-access")
    doc = Document(path)
    headings = [p for p in doc.paragraphs if "subsection" in p.text]
    ids = [p._p.xpath("./w:pPr/w:numPr/w:numId/@w:val")[0] for p in headings]
    assert ids[0] == ids[1]
    assert ids[2] != ids[1]
    assert [p.style.name for p in headings] == ["H2_First", "H2_Cont", "H2_First"]
    for number in {ids[0], ids[2]}:
        num = next(n for n in doc.part.numbering_part.element if n.tag == qn("w:num") and n.get(qn("w:numId")) == number)
        assert num.xpath("./w:lvlOverride/w:startOverride/@w:val") == ["1"]
