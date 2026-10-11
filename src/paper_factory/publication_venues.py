"""The supported journals and article categories have one catalog authority."""

import json
from pathlib import Path


CATALOG_PATH = Path(__file__).with_name("publication_venues.json")


def publication_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
