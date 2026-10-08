"""Labelled desktop boundary tests only: no model, workflow, database, or SCI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

desktop = Path(__file__).resolve().parents[1]
repository = desktop.parent
sys.path.insert(0, str(repository / "src"))
from paper_factory.autonomous.browser_runner import BrowserRunner

sys.stdin.reconfigure(encoding="utf-8", errors="strict")
sys.stdout.reconfigure(encoding="utf-8", errors="strict")


def binding(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


value = json.load(sys.stdin)
scratch = repository / ".paper-factory" / "chromium-desktop-tests-01415" / uuid.uuid4().hex
runner = BrowserRunner({"executable": binding(desktop / "node_modules/electron/dist/electron.exe"),
    "worker": binding(desktop / "dist/chromium-worker.mjs"), "assets": [],
    "app_entry": binding(desktop / "dist/main.js")}, supervisor_root=scratch)
handles = []
started = time.monotonic()
try:
    runner._runtime()
    cancel_after = value.get("cancel_after")
    receipt = runner._execute(value["packet"], purpose="probe", on_handle=handles.append,
        cancel=(lambda: time.monotonic() - started >= cancel_after) if cancel_after is not None else None)
    raw = receipt.pop("raw_response")
    (scratch / "worker-response.jsonl").write_bytes(raw)
    receipt["raw_response_sha256"] = hashlib.sha256(raw).hexdigest()
    receipt["raw_response_bytes"] = len(raw)
    receipt["owned_handles"] = handles
    receipt["label"] = "No-model/no-SCI isolated Chromium desktop boundary test"
    receipt["scientific_execution_attempts"] = 0
    receipt["model_requests"] = 0
finally:
    runner.close()
receipt["journal"] = json.loads((scratch / "owned-workers.json").read_text())
(scratch / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, separators=(",", ":")))
