"""Measure this fixture's actual corpus; no invented experiment values."""

import hashlib
import json
import zlib
from pathlib import Path

data = Path("corpus.txt").read_bytes()
compressed = zlib.compress(data)
result = {
    "input_sha256": hashlib.sha256(data).hexdigest(),
    "observations": {"original_bytes": len(data), "compressed_bytes": len(compressed)},
    "metrics": {"compression_ratio": len(compressed) / len(data)},
    "calculation": "len(zlib.compress(corpus_bytes)) / len(corpus_bytes)",
    "scope": "actual measurements of the included fixture only; no general benchmark claim",
}
Path("results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
