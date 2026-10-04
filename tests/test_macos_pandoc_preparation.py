"""Native asset identity guards without executing a foreign binary."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def asset(tmp_path, monkeypatch):
    bootstrap = helper('native_pandoc_bootstrap', ROOT / 'skills/paper-factory/scripts/prepare_host.py')
    monkeypatch.setattr(bootstrap, 'ROOT', tmp_path)
    licenses = {}
    for name in ('COPYING.md', 'COPYRIGHT'):
        path = tmp_path / 'licenses/pandoc' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = ('Original fixture notice ' + name).encode()
        path.write_bytes(raw)
        licenses['licenses/pandoc/' + name] = {'size':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(), 'source_url':'https://raw.githubusercontent.com/jgm/pandoc/fixture/' + name}

    def create(cpu):
        raw = b'\xcf\xfa\xed\xfe' + cpu.to_bytes(4, 'little') + b'original fixture binary'
        member = 'pandoc-3.9-arm64/bin/pandoc'
        archive = tmp_path / 'pandoc-3.9-arm64-macOS.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr(member, raw)
        record = {'version':'3.9', 'binary':{'member':member, 'size':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}, 'licenses':licenses}
        return archive, record, raw
    return bootstrap, create


def test_reviewed_native_asset_keeps_binary_and_original_notices_without_execution(asset, tmp_path):
    bootstrap, create = asset
    archive, record, raw = create(0x0100000c)
    binary, receipt = bootstrap.prepare_macos_pandoc(archive, tmp_path / 'native', record, 'macos-arm64')
    assert binary.read_bytes() == raw
    assert receipt['binary']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert set(receipt['licenses']) == set(record['licenses'])
    assert all((binary.parent / Path(name).name).read_bytes() == (tmp_path / name).read_bytes() for name in record['licenses'])


def test_intel_binary_in_arm64_asset_is_rejected_before_execution(asset, tmp_path):
    bootstrap, create = asset
    archive, record, _ = create(0x01000007)
    with pytest.raises(ValueError, match='Mach-O architecture'):
        bootstrap.prepare_macos_pandoc(archive, tmp_path / 'native', record, 'macos-arm64')


def test_modified_upstream_notice_is_not_accepted(asset, tmp_path):
    bootstrap, create = asset
    archive, record, _ = create(0x0100000c)
    (tmp_path / 'licenses/pandoc/COPYRIGHT').write_bytes(b'modified')
    with pytest.raises(ValueError, match='notice bytes changed'):
        bootstrap.prepare_macos_pandoc(archive, tmp_path / 'native', record, 'macos-arm64')


def test_modified_native_binary_is_not_accepted(asset, tmp_path):
    bootstrap, create = asset
    archive, record, _ = create(0x0100000c)
    record['binary']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='original bytes'):
        bootstrap.prepare_macos_pandoc(archive, tmp_path / 'native', record, 'macos-arm64')


@pytest.mark.parametrize('url,redirect', [
    ('https://github.com/attacker/pandoc/releases/download/3.9/pandoc-3.9-arm64-macOS.zip',False),
    ('https://release-assets.githubusercontent.com/unreviewed',False),
    ('https://attacker.invalid/pandoc.zip',True),
    ('https://user:secret@github.com/jgm/pandoc/releases/download/3.9/pandoc-3.9-arm64-macOS.zip',False),
], ids=['wrong-repository', 'unreviewed-release-host', 'foreign-redirect', 'embedded-credentials'])
def test_native_artifact_origin_stays_bounded(url, redirect):
    bootstrap = helper('native_pandoc_origins', ROOT / 'skills/paper-factory/scripts/prepare_host.py')
    with pytest.raises(ValueError, match='outside the pinned'):
        bootstrap.artifact_url(url, redirect=redirect)


@pytest.mark.parametrize('destination,accepted', [
    ('https://release-assets.githubusercontent.com/reviewed-fixture',True),
    ('https://attacker.invalid/unreviewed',False),
])
def test_redirect_is_validated_before_the_next_network_request(tmp_path, destination, accepted):
    bootstrap = helper('native_pandoc_redirect', ROOT / 'skills/paper-factory/scripts/prepare_host.py')
    raw = b'original artifact fixture'
    record = {'filename':'pandoc-3.9-arm64-macOS.zip',
              'url':'https://github.com/jgm/pandoc/releases/download/3.9/pandoc-3.9-arm64-macOS.zip',
              'size':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
    requests = []

    class Response:
        def __init__(self, status, headers):
            self.status_code, self.headers = status, headers
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            assert self.status_code == 200
        def iter_bytes(self, limit):
            yield raw

    class Client:
        def stream(self, method, url, *, follow_redirects):
            assert method == 'GET' and follow_redirects is False
            requests.append(url)
            return Response(302,{'location':destination}) if len(requests) == 1 else Response(200,{})

    cache = tmp_path / 'downloads'
    cache.mkdir()
    if accepted:
        path, downloaded = bootstrap.artifact(cache,record,client=Client())
        assert downloaded and path.read_bytes() == raw and requests == [record['url'],destination]
    else:
        with pytest.raises(ValueError, match='outside the pinned'):
            bootstrap.artifact(cache,record,client=Client())
        assert requests == [record['url']]
        assert (cache / (record['filename'] + '.partial')).read_bytes() == b''


def test_source_plugin_version_and_reviewed_notice_members_are_preserved():
    build = helper('native_pandoc_build', ROOT / 'scripts/build_plugin.py')
    files, _, report = build.inputs(ROOT)
    assert report['version'] == json.loads((ROOT / 'plugin.json').read_bytes())['version'] == '0.12.0'
    assert report['core_files'] == 22
    for name in ('COPYING.md', 'COPYRIGHT'):
        member = 'skills/paper-factory/licenses/pandoc/' + name
        assert files[member] == (ROOT / member).read_bytes()
