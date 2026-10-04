"""Exercise vetted Python packages inside the actual native Windows worker."""
import json
import os
from pathlib import Path

import pytest

from paper_factory.autonomous import windows_runtime
from paper_factory.autonomous.windows_runner import WindowsRunner


@pytest.mark.skipif(os.name != "nt", reason="Native AppContainer integration requires Windows")
def test_actual_native_vetted_dependencies_and_cleanup(tmp_path):
    runner = WindowsRunner()
    status = runner.status()
    if not status["ready"]:
        pytest.skip(status["reason"])
    required = {"mido", "pydantic", "httpx"}
    if not required <= set(status["dependencies"]):
        pytest.skip("Install scripts/research-runtime-requirements.txt for vetted dependency integration")

    source, code, output = (tmp_path / name for name in ("source", "code", "output"))
    source.mkdir()
    code.mkdir()
    original = "def transform(note):\n    return (note + 12) % 128\n"
    (source / "production.py").write_text(original, encoding="utf-8")
    (code / "experiment.py").write_text('''import importlib.metadata
import io, json, os, pathlib, sys
import mido
from pydantic import BaseModel, Field, ValidationError
import httpx
sys.path.insert(0, os.environ["PF_SOURCE_ROOT"])
from production import transform

class Note(BaseModel):
    pitch: int = Field(ge=0, le=127)

midi = mido.MidiFile()
track = mido.MidiTrack()
midi.tracks.append(track)
track.append(mido.Message("note_on", note=transform(60), velocity=100, time=0))
track.append(mido.Message("note_off", note=72, velocity=0, time=120))
buffer = io.BytesIO()
midi.save(file=buffer)
encoded = buffer.getvalue()
restored = mido.MidiFile(file=io.BytesIO(encoded))
notes = [message.note for message in restored.tracks[0] if message.type == "note_on"]
validated = Note.model_validate({"pitch": notes[0]})
try:
    Note.model_validate({"pitch": 128})
    invalid_rejected = False
except ValidationError:
    invalid_rejected = True
# Request construction exercises HTTPX without a client or any network request.
request = httpx.Request("POST", "https://example.invalid/check", json=validated.model_dump())
result = {
    "midi_roundtrip": notes == [72], "midi_bytes": len(encoded),
    "pydantic_value": validated.pitch, "pydantic_invalid_rejected": invalid_rejected,
    "httpx_method": request.method, "httpx_content": json.loads(request.content),
    "versions": {name: importlib.metadata.version(name) for name in ("mido", "pydantic", "httpx")},
}
pathlib.Path(os.environ["PF_OUTPUT_ROOT"], "observations.json").write_text(json.dumps(result), encoding="utf-8")
''', encoding="utf-8")

    handles = []
    def retain(handle):
        handles.append(handle)
        (tmp_path / "handle.json").write_text(json.dumps(handle, indent=2), encoding="utf-8")
    result = runner.run(source, code, output, runtime="python", entrypoint="experiment.py",
                        production_entrypoint="production.py:transform", timeout_seconds=20,
                        on_handle=retain)
    (tmp_path / "runner-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert result["status"] == "succeeded", {
        key: result.get(key) for key in ("status", "code", "error", "reason", "exit_code", "cleanup_confirmed", "stderr")
    }
    assert result["cleanup_confirmed"] is True
    assert result["production_calls"] == [{"path": "production.py", "function": "transform", "calls": 1}]
    observed = json.loads(Path(result["output_path"]).read_text(encoding="utf-8"))
    assert observed == {
        "midi_roundtrip": True, "midi_bytes": 34,
        "pydantic_value": 72, "pydantic_invalid_rejected": True,
        "httpx_method": "POST", "httpx_content": {"pitch": 72},
        "versions": {"mido": "1.3.3", "pydantic": "2.13.5", "httpx": "0.28.1"},
    }
    assert handles and windows_runtime.process_ticks(handles[0]["pid"]) is None
    assert not Path(handles[0]["staging_root"]).exists()
    assert (source / "production.py").read_text(encoding="utf-8") == original
