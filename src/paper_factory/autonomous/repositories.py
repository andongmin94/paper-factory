"""Bounded public GitHub discovery for small CPU software studies.

Scores describe feasibility signals, never scientific novelty or a successful
experiment. No credential store, token variable or repository code is read or
executed here. Only fixed GitHub REST endpoints are contacted.
"""

import base64
import binascii
from dataclasses import dataclass, field
import json
import re
import time
import tomllib
from urllib.parse import quote, urlsplit

import httpx

API = "https://api.github.com"
MAX_PAGES = 3
PAGE_SIZE = 100
MAX_INSPECT = 10
MAX_REQUESTS = 33
MAX_SECONDS = 90
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024
MAX_REPOSITORY_KIB = 100_000
LANGUAGES = {"Python", "JavaScript", "TypeScript"}
OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")


def _owner(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Provide a GitHub owner or an HTTPS GitHub profile URL")
    value = value.strip()
    if value.startswith("github.com/"):
        value = "https://" + value
    if "://" in value:
        parts = urlsplit(value)
        try:
            valid = (parts.scheme == "https" and parts.hostname == "github.com"
                     and parts.username is None and parts.password is None
                     and parts.port is None and not parts.query and not parts.fragment)
        except ValueError:
            valid = False
        segments = parts.path.strip("/").split("/")
        if not valid or len(segments) != 1 or parts.path not in {"/" + segments[0], "/" + segments[0] + "/"}:
            raise ValueError("Use a plain HTTPS GitHub profile URL without credentials or parameters")
        value = segments[0]
    if not OWNER.fullmatch(value) or "--" in value:
        raise ValueError("Invalid GitHub owner name")
    return value


@dataclass
class _Budget:
    started: float = field(default_factory=time.monotonic)
    requests: int = 0

    def remaining(self) -> float:
        return MAX_SECONDS - (time.monotonic() - self.started)


def _client() -> httpx.Client:
    # Default proxy/TLS configuration remains in effect; no user token is used.
    return httpx.Client(follow_redirects=False, timeout=20,
                        headers={"Accept": "application/vnd.github+json",
                                 "X-GitHub-Api-Version": "2022-11-28",
                                 "User-Agent": "PaperFactory-public-repository-discovery"})


def _json(client: httpx.Client, path: str, budget: _Budget, params: dict | None = None) -> object:
    remaining = budget.remaining()
    if budget.requests >= MAX_REQUESTS or remaining <= 0:
        raise ValueError("GitHub discovery inspection budget reached")
    budget.requests += 1
    try:
        with client.stream("GET", API + path, params=params, follow_redirects=False,
                           timeout=min(20, remaining)) as response:
            if response.url.scheme != "https" or response.url.host != "api.github.com" or response.url.port not in {None, 443}:
                raise ValueError("GitHub response escaped the public API origin")
            if response.status_code != 200:
                raise ValueError(f"GitHub public API returned HTTP {response.status_code}")
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ValueError("GitHub response exceeds the discovery size limit")
                if budget.remaining() <= 0:
                    raise ValueError("GitHub discovery inspection budget reached")
                body.extend(chunk)
    except httpx.HTTPError as error:
        # A proxy diagnostic may contain connection details. Never copy it.
        raise ValueError(f"GitHub public request failed: {type(error).__name__}") from None
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("GitHub public API returned malformed JSON") from None


def _candidate(record: object, owner: str) -> dict | None:
    if not isinstance(record, dict):
        return None
    name = record.get("name")
    identity = record.get("owner")
    full_name = record.get("full_name")
    if (not isinstance(name, str) or not REPOSITORY.fullmatch(name) or name in {".", ".."}
            or not isinstance(identity, dict) or not isinstance(identity.get("login"), str)
            or identity["login"].casefold() != owner.casefold()
            or not isinstance(full_name, str) or full_name.casefold() != f"{owner}/{name}".casefold()):
        return None
    expected_url = f"https://github.com/{identity['login']}/{name}"
    if record.get("html_url") != expected_url:
        return None
    size = record.get("size")
    branch = record.get("default_branch")
    language = record.get("language")
    if (any(record.get(flag) is not False for flag in ("archived", "fork", "private", "disabled"))
            or isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_REPOSITORY_KIB
            or not isinstance(language, str) or language not in LANGUAGES
            or not isinstance(branch, str) or not branch or len(branch) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in branch)):
        return None
    license_record = record.get("license")
    spdx = license_record.get("spdx_id") if isinstance(license_record, dict) else None
    licensed = isinstance(spdx, str) and spdx not in {"", "NOASSERTION"}
    score = 30 if record["language"] == "Python" else 26
    score += 18 if size <= 1024 else 12 if size <= 10_000 else 5 if size <= 50_000 else 0
    reasons = [f"{record['language']} source", f"GitHub-reported size {size:,} KiB"]
    if licensed:
        score += 10
        reasons.append("GitHub reports an identified license")
    return {"name": name, "url": expected_url, "language": record["language"], "score": score,
            "reasons": reasons, "licensed": licensed, "branch": branch}


def _file(client: httpx.Client, prefix: str, entry: dict, branch: str, budget: _Budget) -> str:
    size = entry.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_FILE_BYTES:
        raise ValueError("Inspection file is absent, empty or above the 64 KiB limit")
    data = _json(client, prefix + "/" + quote(entry["name"], safe=""), budget, {"ref": branch})
    if (not isinstance(data, dict) or data.get("type") != "file" or data.get("encoding") != "base64"
            or data.get("name") != entry["name"] or data.get("path") != entry["name"]
            or not isinstance(data.get("content"), str) or len(data["content"]) > 2 * MAX_FILE_BYTES):
        raise ValueError("GitHub inspection file record is malformed")
    try:
        raw = base64.b64decode("".join(data["content"].split()), validate=True)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Decoded inspection file exceeds 64 KiB")
        return raw.decode("utf-8")
    except (UnicodeDecodeError, binascii.Error):
        raise ValueError("Inspection file is not valid UTF-8/base64") from None


def _manifest_signals(name: str, text: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    if name == "package.json":
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Package manifest is not an object")
        scripts = data.get("scripts", {})
        test = scripts.get("test", "") if isinstance(scripts, dict) else ""
        commands = "\n".join(value for value in scripts.values() if isinstance(value, str)) if isinstance(scripts, dict) else ""
        workspace = bool(data.get("workspaces")) or bool(re.search(r"--filter\b|\b(?:lerna|turbo)\b|pnpm\s+-r\b", commands))
        if isinstance(test, str) and test.strip() and not re.search(r"no test specified|echo\s|exit\s+1", test, re.I):
            score += 12
            reasons.append("package manifest declares a test command (not executed)")
        if any(data.get(key) for key in ("main", "exports", "bin")):
            score += 10
            reasons.append("package manifest declares a library or CLI entrypoint")
        dependencies = data.get("dependencies", {})
        if not isinstance(dependencies, dict):
            raise ValueError("Package dependencies are malformed")
        score += 8 if not dependencies and not workspace else 3 if dependencies and len(dependencies) <= 12 else 0
        if not dependencies:
            reasons.append("root package declares no production dependencies" + ("; workspace package dependencies are uninspected" if workspace else ""))
        if workspace:
            score -= 6
            reasons.append("workspace build structure requires later component/dependency inspection")
        if re.search(r"\b(?:powershell|pwsh|dotnet|cargo|cmake|msbuild)\b", commands, re.I):
            score -= 18
            reasons.append("manifest includes native/platform build commands; standalone Node feasibility is unverified")
        if set(dependencies) & {"electron", "next", "react", "react-native", "@tensorflow/tfjs-node"}:
            score -= 8
            reasons.append("framework/host dependencies require later pure-component assessment")
    else:
        data = tomllib.loads(text)
        project = data.get("project", {})
        tool = data.get("tool", {})
        if not isinstance(project, dict) or not isinstance(tool, dict):
            raise ValueError("Python project manifest is malformed")
        score += 6
        reasons.append("Python project manifest inspected")
        if project.get("scripts"):
            score += 8
            reasons.append("Python manifest declares CLI entrypoints")
        if "pytest" in tool:
            score += 10
            reasons.append("Python manifest contains pytest configuration (not executed)")
        dependencies = project.get("dependencies", [])
        if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
            raise ValueError("Python dependencies are malformed")
        if "dependencies" in project:
            score += 8 if not dependencies else 3 if len(dependencies) <= 12 else 0
        if any(re.match(r"(?:torch|tensorflow|cupy|jax)(?:\W|$)", item, re.I) for item in dependencies):
            score -= 12
            reasons.append("compute-heavy dependencies require later CPU feasibility assessment")
    return score, reasons


def _inspect(client: httpx.Client, owner: str, candidate: dict, budget: _Budget) -> int:
    """Return the number of optional checks that could not be completed."""
    prefix = f"/repos/{owner}/{quote(candidate['name'], safe='')}/contents"
    try:
        listing = _json(client, prefix, budget, {"ref": candidate["branch"]})
        if not isinstance(listing, list) or len(listing) > 1000:
            raise ValueError("GitHub root contents listing is malformed or too large")
    except ValueError:
        return 1
    entries = {}
    directories = set()
    for item in listing:
        if (not isinstance(item, dict) or not isinstance(item.get("name"), str)
                or item.get("path") != item["name"] or "/" in item["name"] or "\\" in item["name"]):
            continue
        if item.get("type") == "dir":
            directories.add(item["name"].casefold())
        elif item.get("type") == "file":
            entries[item["name"]] = item
    if directories & {"test", "tests", "__tests__"}:
        candidate["score"] += 12
        candidate["reasons"].append("root test directory observed (tests not executed)")
    if directories & {"src", "lib"}:
        candidate["score"] += 6
        candidate["reasons"].append("source/library directory observed")
    missed = 0
    manifest = "pyproject.toml" if candidate["language"] == "Python" else "package.json"
    if manifest in entries:
        try:
            text = _file(client, prefix, entries[manifest], candidate["branch"], budget)
            score, reasons = _manifest_signals(manifest, text)
            candidate["score"] += score
            candidate["reasons"].extend(reasons)
        except (ValueError, tomllib.TOMLDecodeError):
            missed += 1
    readme = next((name for name in entries if name.casefold() == "readme.md"), None)
    if readme:
        try:
            text = _file(client, prefix, entries[readme], candidate["branch"], budget)
            terms = {term for term in ("parser", "validator", "algorithm", "transform", "recovery", "serialization", "midi", "transcript")
                     if re.search(r"\b" + term + r"\b", text, re.I)}
            if terms:
                candidate["score"] += min(9, len(terms) * 3)
                candidate["reasons"].append("README describes potentially measurable mechanisms: " + ", ".join(sorted(terms)))
            if re.search(r"\b(?:pure functions?|deterministic tests?|unit tests?)\b", text, re.I):
                candidate["score"] += 6
                candidate["reasons"].append("README describes pure functions or controlled tests")
        except ValueError:
            missed += 1
    return missed


def select_repositories(owner_or_url: str, *, count: int = 3) -> dict:
    """Rank actual public repositories using bounded feasibility heuristics.

    Return fewer than ``count`` when no suitable candidates are available;
    never substitute names or invent metadata after a failed request.
    """
    owner = _owner(owner_or_url)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 3:
        raise ValueError("Repository count must be an integer from 1 to 3")
    budget = _Budget()
    limitations = ["Selection is a feasibility heuristic; no novelty, answerable question or completed experiment is established.",
                   "Only public, non-fork, active Python/JavaScript/TypeScript repositories at most 100,000 KiB are eligible.",
                   "Metadata and at most ten small root/manifest/README inspections do not prove CPU-only execution or passing tests."]
    records = []
    with _client() as client:
        for page in range(1, MAX_PAGES + 1):
            try:
                data = _json(client, f"/users/{owner}/repos", budget,
                             {"per_page": PAGE_SIZE, "page": page, "type": "owner", "sort": "full_name", "direction": "asc"})
                if not isinstance(data, list) or len(data) > PAGE_SIZE:
                    raise ValueError("GitHub repository listing is malformed")
            except ValueError as error:
                if page == 1:
                    raise ValueError(f"Public repository discovery failed: {error}") from None
                limitations.append("Later repository pages were unavailable; selection uses the successfully retrieved pages.")
                break
            records.extend(data)
            if len(data) < PAGE_SIZE:
                break
            if page == MAX_PAGES:
                limitations.append("Listing reached the 300-record limit; additional repositories were not considered.")
        candidates = {}
        for record in records:
            candidate = _candidate(record, owner)
            if candidate is not None:
                candidates.setdefault(candidate["name"].casefold(), candidate)
        preliminary = sorted(candidates.values(), key=lambda item: (-item["score"], item["name"].casefold()))
        missed = sum(_inspect(client, owner, candidate, budget) for candidate in preliminary[:MAX_INSPECT])
        if len(preliminary) > MAX_INSPECT:
            limitations.append("Only the ten leading metadata candidates received optional file inspection.")
        if missed:
            limitations.append(f"{missed} optional inspection checks were unavailable, oversized or malformed; their evidence was not scored.")
    selected = sorted(preliminary, key=lambda item: (-item["score"], item["name"].casefold()))[:count]
    if len(selected) < count:
        limitations.append(f"Only {len(selected)} eligible repositories were found; no replacements were fabricated.")
    if any(not candidate["licensed"] for candidate in selected):
        limitations.append("Some selected repositories have no identified SPDX license in GitHub metadata; permission requires later assessment.")
    return {"owner": owner, "repositories": [
        {"name": item["name"], "url": item["url"], "language": item["language"],
         "reason": "; ".join(item["reasons"]), "score": item["score"]} for item in selected
    ], "considered": len(records), "limitations": limitations}
