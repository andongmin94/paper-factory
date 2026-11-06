"""The supported article categories and the official guidance actually checked."""

CS_GUIDANCE = "https://www.computer.org/publications/author-resources"
AI_GUIDANCE = "https://open.ieee.org/author-guidelines-for-artificial-intelligence-ai-generated-text/"
SOFTWARE_GUIDANCE = "https://www.computer.org/digital-library/magazines/so/cfp-ieee-software"
SP_GUIDANCE = "https://www.computer.org/digital-library/magazines/sp/cfp-real-world-security-impact"

VENUE_RULES = {
    "ieee-software": {
        "publication": "IEEE Software", "output": "word", "checked_at": "2026-10-18",
        "source_urls": [SOFTWARE_GUIDANCE, CS_GUIDANCE, AI_GUIDANCE],
        "citation_style": "superscript_outside_punctuation", "biographies": True,
        "limits": {"word_count_scope": "body_excluding_references_and_bios", "max_words": 4200,
                   "max_abstract_words": 150, "max_references": 15, "visual_word_cost": 250,
                   "min_keywords": 3, "max_keywords": 8, "insight_count": 3},
        "writer_targets": {"abstract_words": 130, "whole_words": [3200, 3800]},
    },
    "ieee-security-privacy": {
        "publication": "IEEE Security & Privacy", "output": "word", "checked_at": "2026-10-18",
        "source_urls": [SP_GUIDANCE, CS_GUIDANCE, AI_GUIDANCE],
        "citation_style": "bracketed_inside_punctuation", "biographies": True,
        "limits": {"word_count_scope": "whole_article", "min_words": 4900, "max_words": 7200,
                   "max_abstract_words": 50, "max_references": 15, "visual_word_cost": 250,
                   "min_keywords": 3, "max_keywords": 8},
        "writer_targets": {"abstract_words": 45, "whole_words": [5400, 6500]},
    },
    "ieee-access": {
        "publication": "IEEE Access", "output": "word", "checked_at": "2026-11-02",
        "source_urls": ["https://ieeeaccess.ieee.org/authors/submission-guidelines/",
                        "https://ieeeaccess.ieee.org/authors/preparing-your-article/",
                        "https://ieeeaccess.ieee.org/wp-content/uploads/2025/08/Access-Template-2024.docx"],
        "citation_style": "bracketed_inside_punctuation", "biographies": True,
        "limits": {"word_count_scope": "whole_article", "max_words": None,
                   "min_abstract_words": 150, "max_abstract_words": 250, "max_references": None,
                   "visual_word_cost": 0, "min_keywords": 3, "max_keywords": 10,
                   "recommended_max_pages": 20, "max_file_bytes": 40000000},
        "writer_targets": {"abstract_words": 200},
    },
    "jors": {
        "publication": "Journal of Open Research Software", "output": "word", "checked_at": "2026-11-02",
        "source_urls": ["https://openresearchsoftware.metajnl.com/about/submissions",
                        "https://account.openresearchsoftware.metajnl.com/index.php/up-j-jors/libraryFiles/downloadPublic/4"],
        "citation_style": "vancouver_parenthetical", "biographies": False,
        "limits": {"word_count_scope": "whole_article", "max_words": None,
                   "max_abstract_words": None, "max_references": None, "visual_word_cost": 0,
                   "min_keywords": 3, "max_keywords": 8},
        "writer_targets": {"abstract_words": 100},
        "required_sections": ["overview", "implementation and architecture", "quality control",
                              "availability", "reuse potential", "competing interests", "references"],
    },
    "joss": {
        "publication": "Journal of Open Source Software", "output": "markdown-bibtex", "checked_at": "2026-11-02",
        "source_urls": ["https://joss.readthedocs.io/en/latest/paper.html",
                        "https://joss.readthedocs.io/en/latest/submitting.html"],
        "citation_style": "apa_author_date", "biographies": False,
        "limits": {"min_words": 750, "max_words": 1750},
    },
}

EXPORT_VENUES = tuple(VENUE_RULES)
WORD_VENUES = tuple(venue for venue in EXPORT_VENUES if VENUE_RULES[venue]["output"] == "word")

# These venues accept a host-prepared manuscript. They do not use a retained
# Word template or the JOSS adapter. Roles refer to the private preparation bundle.
PREPARED_MANUSCRIPTS = {"emse": ("editable_docx", ".docx"),
                        "jmlr-mloss": ("review_pdf", ".pdf")}
VENUES = (*EXPORT_VENUES, *PREPARED_MANUSCRIPTS)
