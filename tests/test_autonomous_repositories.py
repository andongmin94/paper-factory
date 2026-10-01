import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from paper_factory.autonomous import repositories as picker


def repo(name, *, language="Python", size=500, **changes):
    value = {"name": name, "full_name": f"researcher/{name}", "owner": {"login": "researcher"},
             "html_url": f"https://github.com/researcher/{name}", "language": language,
             "size": size, "default_branch": "main", "archived": False, "fork": False,
             "private": False, "disabled": False, "license": {"spdx_id": "MIT"}}
    value.update(changes)
    return value


def file_record(name, text):
    return {"type": "file", "name": name, "path": name, "size": len(text.encode()),
            "encoding": "base64", "content": base64.b64encode(text.encode()).decode(),
            "download_url": "https://untrusted.invalid/do-not-follow"}


def install_client(monkeypatch, handler):
    monkeypatch.setattr(picker, "_client", lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True))


def test_structural_library_evidence_outranks_frontend_popularity(monkeypatch):
    requests = []
    library = '[project]\nname="codec"\ndependencies=[]\n[project.scripts]\ncodec="codec:main"\n[tool.pytest.ini_options]\ntestpaths=["tests"]\n'
    frontend = json.dumps({"name": "popular-site", "dependencies": {"next": "1", "react": "1"}})
    files = {"codec": {"pyproject.toml": library, "README.md": "Pure functions for serialization; deterministic tests."},
             "popular-site": {"package.json": frontend}, "simple": {}}

    def handler(request):
        requests.append(request)
        assert request.url.host == "api.github.com"
        assert "authorization" not in request.headers
        if request.url.path == "/users/researcher/repos":
            assert request.url.params["per_page"] == "100"
            return httpx.Response(200, json=[repo("popular-site", language="TypeScript", size=100, stargazers_count=100_000),
                                            repo("simple"), repo("codec", size=1200)])
        name = request.url.path.split("/")[3]
        contents = files[name]
        if request.url.path.endswith("/contents"):
            entries = [file_record(filename, text) for filename, text in contents.items()]
            if name == "codec":
                entries.extend([{"type": "dir", "name": item, "path": item} for item in ("src", "tests")])
            return httpx.Response(200, json=entries)
        filename = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=file_record(filename, contents[filename]))

    monkeypatch.setenv("GITHUB_TOKEN", "synthetic-value-must-not-be-used")
    install_client(monkeypatch, handler)
    result = picker.select_repositories("https://github.com/researcher/", count=3)
    assert result["owner"] == "researcher" and result["considered"] == 3
    assert [item["name"] for item in result["repositories"]] == ["codec", "simple", "popular-site"]
    winner = result["repositories"][0]
    assert winner["url"] == "https://github.com/researcher/codec"
    assert "pytest" in winner["reason"] and "not executed" in winner["reason"]
    assert any("feasibility heuristic" in text for text in result["limitations"])
    assert not any(request.url.host == "untrusted.invalid" for request in requests)


@pytest.mark.parametrize("value", ["", "../researcher", "owner/repo", "https://github.com/owner/repo",
                                   "http://github.com/owner", "https://evil.invalid/owner",
                                   "https://github.com@evil.invalid/owner", "https://token@github.com/owner",
                                   "https://github.com:443/owner", "https://github.com/owner?tab=repositories",
                                   "https://github.com/owner#fragment", "https://github.com//owner",
                                   "https://github.com/%2e%2e", "owner--name", "-owner", "owner\nname"])
def test_invalid_owner_never_opens_network(monkeypatch, value):
    monkeypatch.setattr(picker, "_client", lambda: pytest.fail("Invalid owner reached network"))
    with pytest.raises(ValueError):
        picker.select_repositories(value)


@pytest.mark.parametrize("count", [0, 4, -1, True, 1.5, "3"])
def test_count_is_bounded_before_network(monkeypatch, count):
    monkeypatch.setattr(picker, "_client", lambda: pytest.fail("Invalid count reached network"))
    with pytest.raises(ValueError, match="integer from 1 to 3"):
        picker.select_repositories("researcher", count=count)


@pytest.mark.parametrize("source", ["researcher", "github.com/researcher", "https://github.com/researcher"])
def test_supported_owner_forms_have_fixed_request_origin(monkeypatch, source):
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, json=[])

    install_client(monkeypatch, handler)
    result = picker.select_repositories(source, count=1)
    assert result["repositories"] == []
    assert len(seen) == 1 and str(seen[0]).startswith("https://api.github.com/users/researcher/repos?")


def test_excludes_forks_archived_empty_large_unsupported_and_untrusted_records(monkeypatch):
    values = [repo("forked", fork=True), repo("archived", archived=True), repo("empty", size=0),
              repo("huge", size=picker.MAX_REPOSITORY_KIB + 1), repo("cpp", language="C++"),
              repo("private", private=True), repo("disabled", disabled=True), repo("wrong-owner", owner={"login": "outsider"}),
              repo("wrong-url", html_url="https://evil.invalid/repository"), repo("wrong-full", full_name=["malformed"]),
              repo("wrong-language", language=[]), repo("boolean-size", size=True),
              repo("usable", license=None), {"name": "malformed"}]

    def handler(request):
        return httpx.Response(200, json=values if "/users/" in request.url.path else [])

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher")
    assert result["considered"] == len(values)
    assert [item["name"] for item in result["repositories"]] == ["usable"]
    assert any("no replacements" in text for text in result["limitations"])
    assert any("license" in text for text in result["limitations"])


@pytest.mark.parametrize("response", [httpx.Response(403), httpx.Response(503),
                                     httpx.Response(200, text="not JSON"), httpx.Response(200, json={"message": "wrong shape"})])
def test_listing_failures_do_not_fabricate_repositories(monkeypatch, response):
    install_client(monkeypatch, lambda _: response)
    with pytest.raises(ValueError, match="discovery failed"):
        picker.select_repositories("researcher")


def test_redirects_are_not_followed_even_with_redirect_enabled_client(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://evil.invalid/steal"})

    install_client(monkeypatch, handler)
    with pytest.raises(ValueError, match="HTTP 302"):
        picker.select_repositories("researcher")
    assert len(seen) == 1 and seen[0].url.host == "api.github.com"


def test_response_stream_is_bounded(monkeypatch):
    install_client(monkeypatch, lambda _: httpx.Response(200, content=b" " * (picker.MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(ValueError, match="size limit"):
        picker.select_repositories("researcher")


def test_optional_malformed_manifest_is_disclosed_and_not_scored(monkeypatch):
    bad = file_record("package.json", "{ invalid")

    def handler(request):
        if "/users/" in request.url.path:
            return httpx.Response(200, json=[repo("library", language="JavaScript")])
        return httpx.Response(200, json=[bad] if request.url.path.endswith("/contents") else bad)

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher", count=1)
    assert len(result["repositories"]) == 1
    assert "test command" not in result["repositories"][0]["reason"]
    assert any("1 optional" in text for text in result["limitations"])


def test_oversized_file_is_not_requested(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if "/users/" in request.url.path:
            return httpx.Response(200, json=[repo("library", language="JavaScript")])
        assert request.url.path.endswith("/contents")
        return httpx.Response(200, json=[{"name": "package.json", "path": "package.json", "type": "file", "size": picker.MAX_FILE_BYTES + 1}])

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher", count=1)
    assert len(seen) == 2 and any("oversized" in text for text in result["limitations"])


def test_default_no_test_placeholder_does_not_count_as_tests(monkeypatch):
    manifest = file_record("package.json", json.dumps({"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}))

    def handler(request):
        if "/users/" in request.url.path:
            return httpx.Response(200, json=[repo("library", language="JavaScript")])
        return httpx.Response(200, json=[manifest] if request.url.path.endswith("/contents") else manifest)

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher", count=1)
    assert "test command" not in result["repositories"][0]["reason"]


def test_workspace_root_without_dependencies_is_not_ranked_as_standalone_node(monkeypatch):
    manifests = {
        "native-workspace": {"workspaces": ["packages/*"], "scripts": {"test": "pnpm --filter desktop test", "build": "powershell scripts/build.ps1 && dotnet build"}},
        "pure-library": {"exports": "./index.js", "scripts": {"test": "node --test"}, "dependencies": {}},
    }

    def handler(request):
        if "/users/" in request.url.path:
            return httpx.Response(200, json=[repo(name, language="JavaScript") for name in manifests])
        name = request.url.path.split("/")[3]
        value = file_record("package.json", json.dumps(manifests[name]))
        return httpx.Response(200, json=[value] if request.url.path.endswith("/contents") else value)

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher", count=2)
    assert [item["name"] for item in result["repositories"]] == ["pure-library", "native-workspace"]
    native = result["repositories"][1]
    assert "workspace package dependencies are uninspected" in native["reason"]
    assert "native/platform build" in native["reason"]


def test_listing_pagination_stops_at_three_pages(monkeypatch):
    seen = []

    def handler(request):
        page = int(request.url.params["page"])
        seen.append(page)
        return httpx.Response(200, json=[repo(f"repository-{page}-{n}", language="Go") for n in range(100)])

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher")
    assert seen == [1, 2, 3] and result["considered"] == 300
    assert any("300-record" in text for text in result["limitations"])


def test_later_page_failure_retains_only_observed_records(monkeypatch):
    def handler(request):
        if request.url.params["page"] == "1":
            return httpx.Response(200, json=[repo(f"repository-{n}", language="Go") for n in range(100)])
        return httpx.Response(403)

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher")
    assert result["considered"] == 100 and result["repositories"] == []
    assert any("Later repository pages" in text for text in result["limitations"])


def test_optional_inspections_obey_request_cap(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        if "/users/" in request.url.path:
            return httpx.Response(200, json=[repo("alpha"), repo("beta"), repo("gamma")])
        return httpx.Response(200, json=[file_record("pyproject.toml", '[project]\nname="example"')])

    monkeypatch.setattr(picker, "MAX_REQUESTS", 2)
    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher")
    assert len(seen) == 2 and len(result["repositories"]) == 3
    assert any("optional inspection" in text for text in result["limitations"])


def test_elapsed_budget_blocks_inspection_without_network(monkeypatch):
    seen = []
    budget = picker._Budget(started=0.0)
    ticks = iter([0.0, 0.0, picker.MAX_SECONDS + 1.0])
    monkeypatch.setattr(picker, "time", SimpleNamespace(monotonic=lambda: next(ticks, picker.MAX_SECONDS + 1.0)))
    monkeypatch.setattr(picker, "_Budget", lambda: budget)

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[repo("library")])

    install_client(monkeypatch, handler)
    result = picker.select_repositories("researcher", count=1)
    assert len(seen) == 1 and result["repositories"][0]["name"] == "library"
    assert any("optional inspection" in text for text in result["limitations"])


def test_network_diagnostics_do_not_copy_proxy_details(monkeypatch):
    def handler(request):
        raise httpx.ProxyError("synthetic-private-proxy-detail")

    install_client(monkeypatch, handler)
    with pytest.raises(ValueError) as error:
        picker.select_repositories("researcher")
    assert "ProxyError" in str(error.value) and "synthetic-private" not in str(error.value)
