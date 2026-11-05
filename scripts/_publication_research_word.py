"""Apply the verified IEEE Access and JORS Word submission templates."""

from copy import deepcopy
from pathlib import Path
import re

from _publication_templates import _replace_native_text


_CITATIONS = re.compile(
    r'''(?:(?P<before>[.,;:!?])(?P<close>["'”’)]*)[ \t]*)?[ \t]*'''
    r'''(?P<cites>\[\d+(?:[ \t]*[,;–-][ \t]*\d+)*\](?:[ \t]*,?[ \t]*\[\d+(?:[ \t]*[,;–-][ \t]*\d+)*\])*)'''
    r'''(?P<after>[.,;:!?])?(?P<afterclose>["'”’)]*)'''
)
_PAREN_CITATIONS = re.compile(
    r'''(?:(?P<before>[.,;:!?])(?P<close>["'”’)]*)[ \t]*)?[ \t]*'''
    r'''(?P<cites>\(\d+(?:[ \t]*[,;–-][ \t]*\d+)*\))'''
    r'''(?P<after>[.,;:!?])?(?P<afterclose>["'”’)]*)'''
)


def _source_style(paragraph):
    # JORS's reference omits Heading1/2 and BodyText definitions. Pandoc still
    # writes those paragraph IDs; python-docx's resolved style becomes Normal.
    return next(iter(paragraph._p.xpath("./w:pPr/w:pStyle/@w:val")), "Normal")


def _heading_level(paragraph):
    match = re.fullmatch(r"Heading(\d+)", _source_style(paragraph))
    return int(match[1]) if match else None


def _citation_runs(paragraph):
    """Keep code and hyperlinks outside citation typography edits."""
    from docx.text.run import Run

    text, protected = "", []
    for element in paragraph._p.xpath(".//w:r"):
        run = Run(element, paragraph)
        style = " ".join(element.xpath("./w:rPr/w:rStyle/@w:val")).casefold()
        guarded = any(name in style for name in ("verbatim", "code")) or bool(
            element.xpath("ancestor::w:hyperlink")
        )
        text += run.text
        protected.extend([guarded] * len(run.text))
    return text, protected


def _format_citations(paragraphs, known, *, access):
    changed, unknown = 0, set()
    for paragraph in paragraphs:
        if _source_style(paragraph).casefold() in {"sourcecode", "code", "references", "aubios"}:
            continue
        text, protected = _citation_runs(paragraph)
        for match in reversed(list(_CITATIONS.finditer(text))):
            if any(protected[match.start():match.end()]):
                continue
            numbers = set(re.findall(r"\d+", match["cites"]))
            if not numbers <= known:
                unknown.update(numbers - known)
                continue
            punctuation = (match["before"] or "") + (match["after"] or "")
            closing = (match["close"] or "") + (match["afterclose"] or "")
            space = " " if closing or match.start() and not text[match.start() - 1].isspace() else ""
            citations = match["cites"].strip()
            if not access:
                citations = "(" + ", ".join(re.findall(r"\[([^]]+)\]", citations)) + ")"
            _replace_native_text(paragraph, match.start(), match.end(), [
                (closing + space + citations + punctuation, False)
            ])
            changed += 1
    return {"callout_groups_formatted": changed,
            "unknown_reference_numbers_preserved": sorted(unknown),
            "callout_style": "Bracketed numbers inside punctuation" if access else "Parenthesized numbers inside punctuation",
            "bibliography_labels": "Bracketed numbers" if access else "Numbered-period Vancouver list",
            "bibliography_metadata": "Supplied bibliographic metadata preserved"}


def _section_master(section):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    element = deepcopy(section._sectPr)
    for name in ("headerReference", "footerReference", "pgNumType", "titlePg"):
        for child in element.findall(qn("w:" + name)):
            element.remove(child)
    kind = element.find(qn("w:type"))
    if kind is None:
        kind = OxmlElement("w:type")
        element.insert(0, kind)
    kind.set(qn("w:val"), "continuous")
    return element


def _fit_images(paragraphs, width, height):
    from docx.shape import InlineShape

    for paragraph in paragraphs:
        for inline in paragraph._p.xpath(".//wp:inline"):
            shape = InlineShape(inline)
            scale = min(1, width / shape.width, height / shape.height)
            if scale < 1:
                shape.width, shape.height = round(shape.width * scale), round(shape.height * scale)


def apply_research_styles(output: Path, template: Path, venue_id: str) -> dict:
    """Map Pandoc content without replacing the publisher's styles or geometry."""
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.shared import Twips
    from docx.text.paragraph import Paragraph

    if venue_id not in {"ieee-access", "jors"}:
        raise ValueError("Research Word mapping supports only ieee-access and jors")
    access = venue_id == "ieee-access"
    document, reference = Document(output), Document(template)
    paragraphs = document.paragraphs
    if not paragraphs or _heading_level(paragraphs[0]) != 1:
        raise ValueError("The official research export requires one leading Markdown title")
    abstract_heading = next((p for p in paragraphs[1:] if _heading_level(p) == 2
                             and p.text.strip().casefold() == "abstract"), None)
    if abstract_heading is None:
        raise ValueError("The official research export requires a distinct Abstract section")
    abstract_index = paragraphs.index(abstract_heading)
    body_heading = next((p for p in paragraphs[abstract_index + 1:]
                         if _heading_level(p) is not None), None)
    if body_heading is None:
        raise ValueError("The official research export requires body sections after its abstract")
    body_index = paragraphs.index(body_heading)
    abstract_paragraphs = [p for p in paragraphs[abstract_index + 1:body_index]
                           if p.text.strip() and not p.text.lstrip().casefold().startswith("keywords:")]
    if not abstract_paragraphs:
        raise ValueError("The official research abstract is empty")

    if not access:
        # JORS does not name separate abstract/bibliography styles. These two
        # labels let Word measure their scopes, with unchanged publisher Normal.
        for name in ("Abstract", "References"):
            style = document.styles[name] if name in document.styles else document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            style.base_style = document.styles["Normal"]
            for child in list(style.element):
                if child.tag in {qn("w:pPr"), qn("w:rPr")}:
                    style.element.remove(child)

    paragraphs[0].style = document.styles["Paper Title" if access else "UP Paper Title"]
    for paragraph in paragraphs[1:abstract_index]:
        paragraph.style = document.styles["AU" if access else (
            "UP Section Heading" if _heading_level(paragraph) is not None else "Normal")]
    for paragraph in paragraphs[abstract_index + 1:body_index]:
        if paragraph.text.lstrip().casefold().startswith("keywords:"):
            paragraph.style = document.styles["IT" if access else "Normal"]
            if access:
                keywords = [word.strip() for word in paragraph.text.split(":", 1)[1].split(";") if word.strip()]
                paragraph.text = "INDEX TERMS " + ", ".join(sorted(keywords, key=str.casefold))
        else:
            paragraph.style = document.styles["Abstract"]
    if access:
        label = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.set(qn("xml:space"), "preserve")
        text.text = "ABSTRACT "
        label.append(text)
        first = abstract_paragraphs[0]._p
        first.insert(1 if first.pPr is not None else 0, label)
        abstract_heading._p.getparent().remove(abstract_heading._p)
    else:
        abstract_heading.style = document.styles["UP Section Heading"]

    body_style = "PARA" if access else "Normal"
    section_style, first_body_heading = body_style, True
    bibliography = []
    numbered_levels = {}

    def restart_heading_list(style_name):
        numbering = document.part.numbering_part.element
        source_id = document.styles[style_name].element.xpath("./w:pPr/w:numPr/w:numId/@w:val")[0]
        source = next(n for n in numbering if n.tag == qn("w:num") and n.get(qn("w:numId")) == source_id)
        new = deepcopy(source)
        number = max(int(n.get(qn("w:numId"))) for n in numbering if n.tag == qn("w:num")) + 1
        new.set(qn("w:numId"), str(number))
        for old in new.findall(qn("w:lvlOverride")):
            new.remove(old)
        override = OxmlElement("w:lvlOverride")
        override.set(qn("w:ilvl"), "0")
        start = OxmlElement("w:startOverride")
        start.set(qn("w:val"), "1")
        override.append(start)
        new.append(override)
        numbering.append(new)
        return number

    for paragraph in paragraphs[body_index:]:
        name = _source_style(paragraph)
        level = _heading_level(paragraph)
        if level is not None:
            heading = paragraph.text.strip().casefold()
            section_style = body_style
            if access:
                for deeper in list(numbered_levels):
                    if deeper > level:
                        del numbered_levels[deeper]
                style = ({2: "H1_List (No Space)" if first_body_heading else "H1_List (Space)",
                          3: "H2_Cont" if level in numbered_levels else "H2_First",
                          4: "H3", 5: "H4", 6: "H5"})[level]
                if heading in {"references", "acknowledgments", "acknowledgements", "acknowledgment",
                               "acknowledgement", "author biography", "author biographies", "about the authors"}:
                    style = "H1"
                paragraph.style = document.styles[style]
                if level in {3, 4}:
                    if level not in numbered_levels:
                        numbered_levels[level] = restart_heading_list(style)
                    paragraph._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = numbered_levels[level]
            else:
                paragraph.style = document.styles["UP Section Heading"]
            if heading == "references":
                section_style = "References"
            elif access and heading in {"author biography", "author biographies", "about the authors"}:
                section_style = "AU_Bios"
            paragraph.paragraph_format.keep_with_next = True
            first_body_heading = False
        elif name in {"Normal", "BodyText", "FirstParagraph", "Compact"}:
            paragraph.style = document.styles[section_style]
            if section_style == "References" and paragraph.text.strip():
                bibliography.append(paragraph)
                match = re.match(r"^\[(\d+)\]\s*", paragraph.text)
                if not access and match:
                    _replace_native_text(paragraph, 0, match.end(), [(match[1] + ". ", False)])
                # The canonical [n] label already exists. Disable the Access
                # style's automatic label so Word does not display it twice.
                num = paragraph._p.get_or_add_pPr().get_or_add_numPr()
                num.get_or_add_numId().val = 0
        elif access and name in {"TableCaption", "ImageCaption", "FigureCaption"}:
            paragraph.style = document.styles["Table Caption" if name == "TableCaption" else "Fig Caption"]

    front = _section_master(reference.sections[0])
    body_section = next((s for s in reference.sections if s._sectPr.find(qn("w:cols")).get(qn("w:num"), "1") == "2"), None) if access else reference.sections[0]
    if body_section is None:
        raise ValueError("The IEEE Access template is missing its two-column body")
    body = _section_master(body_section)
    body_element = document._element.body
    for old in list(body_element.iter(qn("w:sectPr"))):
        old.getparent().remove(old)
    if access:
        preceding = body_heading._p.xpath("preceding-sibling::w:p[1]")
        preceding[0].get_or_add_pPr().append(front)
    body_element.append(deepcopy(body))
    # Drop the sample parts as well as their references: no fictional DOI,
    # author running head, publication date or volume survives the conversion.
    for rel in list(document.part.rels.values()):
        if rel.reltype in {RT.HEADER, RT.FOOTER}:
            document.part.drop_rel(rel.rId)

    columns = body.find(qn("w:cols"))
    column_count = int(columns.get(qn("w:num"), "1"))
    full_width = int(body_section.page_width - body_section.left_margin - body_section.right_margin)
    column_gap = Twips(int(columns.get(qn("w:space"), "0")))
    column_width = (full_width - column_gap * (column_count - 1)) // column_count
    page_height = int(body_section.page_height - body_section.top_margin - body_section.bottom_margin)
    _fit_images(paragraphs[body_index:], column_width, page_height)

    for table in document.tables:
        # Current Access puts captions above tables; current JORS puts them
        # below. Move the exact paragraph, retaining its inline content.
        before, after = table._tbl.getprevious(), table._tbl.getnext()
        caption = None
        for element in (before, after):
            if element is not None and element.tag == qn("w:p"):
                paragraph = Paragraph(element, document._body)
                if paragraph.style.name == "Table Caption" or re.match(r"^Table\s+(?:\d+|[IVXLCDM]+)[.:]\s*\S", paragraph.text, re.I):
                    caption = paragraph
                    if access and element is after:
                        table._tbl.addprevious(element)
                    elif not access and element is before:
                        table._tbl.addnext(element)
                    if access:
                        caption.style = document.styles["Table Caption"]
                    caption.paragraph_format.keep_with_next = access
                    break
        if access:
            boundary = OxmlElement("w:p")
            properties = boundary.get_or_add_pPr()
            spacing = OxmlElement("w:spacing")
            for key, value in (("before", "0"), ("after", "0"), ("line", "1"), ("lineRule", "exact")):
                spacing.set(qn("w:" + key), value)
            properties.append(spacing)
            properties.append(deepcopy(body))
            (caption._p if caption is not None else table._tbl).addprevious(boundary)
            end = OxmlElement("w:p")
            end.get_or_add_pPr().append(deepcopy(front))
            table._tbl.addnext(end)
        table.autofit = False
        cell_width = full_width // len(table.columns)
        for column in table.columns:
            column.width = cell_width
        for index, row in enumerate(table.rows):
            properties = row._tr.get_or_add_trPr()
            if index == 0 and properties.find(qn("w:tblHeader")) is None:
                properties.append(OxmlElement("w:tblHeader"))
            if properties.find(qn("w:cantSplit")) is None:
                properties.append(OxmlElement("w:cantSplit"))
            for cell in row.cells:
                cell.width = cell_width
                for paragraph in cell.paragraphs:
                    paragraph.style = document.styles[body_style]
                    paragraph.paragraph_format.keep_with_next = index == 0 or bool(
                        not access and caption is not None and index == len(table.rows) - 1)
                    if index == 0:
                        for run in paragraph.runs:
                            run.bold = True
                _fit_images(cell.paragraphs, max(1, cell_width - Twips(216)), page_height)

    label_pattern = r"^\[(\d+)\]\s" if access else r"^(\d+)\.\s"
    known = {match[1] for p in bibliography if (match := re.match(label_pattern, p.text))}
    citation_paragraphs = paragraphs[body_index:] + [p for table in document.tables for row in table.rows
                                                   for cell in row.cells for p in cell.paragraphs]
    citation_proof = _format_citations(citation_paragraphs, known, access=access)
    document.save(output)
    return {"style_mapping": "IEEE Access native named styles" if access else "JORS UP Paper Title, UP Section Heading and Normal",
            "layout": "Publisher one-column front matter and two-column body; full-width tables" if access else "Publisher single-column A4 section",
            "measurement_styles": {"abstract": "Abstract", "references": "References"},
            "adaptations": ["Removed sample publication and author furniture; preserved supplied content and media",
                            "Native section masters retained; oversized figures fit the available column or table cell",
                            "Explicit bibliography labels replace automatic numbering"] + ([] if access else [
                                "Abstract and References measurement styles inherit the publisher Normal style without formatting changes"]),
            "citation_typography": citation_proof,
            "font_policy": "Official font names retained; local font availability and Microsoft Word page rendering require verification."}


def native_structure(docx: Path, venue_id: str) -> dict:
    """Inspect generated structure; this does not attest native Word rendering."""
    from docx import Document
    from docx.oxml.ns import qn

    if venue_id not in {"ieee-access", "jors"}:
        raise ValueError("Research Word inspection supports only ieee-access and jors")
    access = venue_id == "ieee-access"
    document = Document(docx)
    paragraphs = document.paragraphs
    title = "Paper Title" if access else "UP Paper Title"
    styles = {paragraph.style.name for paragraph in paragraphs}
    issues = []
    if not {title, "Abstract", "References"} <= styles or not paragraphs or paragraphs[0].style.name != title:
        issues.append("Native publisher title, abstract and reference styles are missing.")
    columns = [int(s._sectPr.find(qn("w:cols")).get(qn("w:num"), "1")) for s in document.sections]
    if access and (not columns or columns[0] != 1 or 2 not in columns):
        issues.append("IEEE Access requires one-column front matter and a two-column body.")
    if not access and columns != [1]:
        issues.append("JORS requires the publisher single-column section.")
    bibliography = [p for p in paragraphs if p.style.name == "References" and p.text.strip()]
    label_pattern = r"^\[(\d+)\]\s" if access else r"^(\d+)\.\s"
    labels = [int(match[1]) for p in bibliography if (match := re.match(label_pattern, p.text))]
    if labels != list(range(1, len(bibliography) + 1)):
        issues.append("Native bibliography labels must be sequential " + ("bracketed numbers." if access else "numbered-period entries."))
    if any(p._p.xpath("./w:pPr/w:numPr/w:numId/@w:val") != ["0"] for p in bibliography):
        issues.append("Explicit bibliography labels must not also receive automatic numbering.")
    known = {str(number) for number in labels}
    body = list(paragraphs) + [p for table in document.tables for row in table.rows for cell in row.cells for p in cell.paragraphs]
    for paragraph in body:
        if _source_style(paragraph).casefold() in {"sourcecode", "code", "references"}:
            continue
        text, protected = _citation_runs(paragraph)
        for match in (_CITATIONS if access else _PAREN_CITATIONS).finditer(text):
            if match["before"] and set(re.findall(r"\d+", match["cites"])) <= known and not any(protected[match.start():match.end()]):
                issues.append("Body citations must appear before terminal punctuation.")
    prefix = "index terms " if access else "keywords:"
    keywords = [p.text for p in paragraphs if p.text.casefold().startswith(prefix)]
    if any(p.style.name == "Abstract" and p.text.casefold().startswith(prefix) for p in paragraphs):
        issues.append("Keywords must not be counted as part of the Abstract style.")
    return {"issues": sorted(set(issues)), "reference_count": len(bibliography), "keywords": keywords,
            "citation_style": "bracketed_inside_punctuation" if access else "vancouver_parenthetical"}
