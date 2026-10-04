"""Offline dependency/transport checks for the packaged host prerequisites."""

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

import pytest


SKILL = Path(__file__).resolve().parents[1] / "skills/paper-factory"
SCRIPTS = SKILL / "scripts"
TRANSPORT = {"httpx", "httpcore", "h11", "anyio", "idna", "certifi", "typing-extensions", "socksio"}


def load_helper(name):
    specification = importlib.util.spec_from_file_location("cloud_packaging_" + name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture
def wheels(tmp_path):
    manifest = json.loads((SKILL / "host-dependencies.json").read_bytes())
    declarations = [item for item in manifest["wheels"].values() if item["name"] in TRANSPORT]
    assert len(declarations) == len(TRANSPORT) and {item["name"] for item in declarations} == TRANSPORT
    paths = {}
    # The bootstrap wheelhouse supplies HTTPX's declared runtime dependencies.
    for declaration in declarations:
        distribution = declaration["name"]
        assert declaration["version"] == manifest["pins"][distribution]
        assert declaration["filename"].endswith("-py3-none-any.whl")
        path = SKILL / "wheelhouse" / declaration["filename"]
        raw = path.read_bytes()
        assert len(raw) == declaration["size"]
        assert hashlib.sha256(raw).hexdigest() == declaration["sha256"]
        paths[distribution] = path
    # Certifi needs an actual PEM path even when its Python module is zip-imported.
    certificate = tmp_path / "cacert.pem"
    with zipfile.ZipFile(paths["certifi"]) as archive:
        certificate.write_bytes(archive.read("certifi/cacert.pem"))
    return paths, certificate


def client_check(wheels, *, include_socksio):
    paths, certificate = wheels
    selected = [str(path) for name, path in paths.items() if include_socksio or name != "socksio"]
    # -I -S makes the missing dependency real, independent of host site packages.
    # Importing HTTPX is permitted; the guard forbids every socket operation while
    # the actual constructor and optional SOCKS transport initialize and close.
    program = """
import importlib.util, json, os, socket, ssl, sys
sys.path[:0] = json.loads(sys.argv[1])
import httpx
clients = []
original_client = httpx.Client
def tracked_client(**options):
    assert options == {'trust_env': True}
    client = original_client(**options)
    clients.append(client)
    return client
httpx.Client = tracked_client
for key in tuple(os.environ):
    if key.lower().endswith('_proxy') or key in ('SSL_CERT_FILE', 'SSL_CERT_DIR'):
        del os.environ[key]
os.environ['ALL_PROXY'] = 'socks5://synthetic_user:synthetic_password@proxy.invalid:1080'
os.environ['SSL_CERT_FILE'] = sys.argv[2]
def forbidden(*args, **kwargs):
    raise AssertionError('A constructor-only capability check attempted network access')
socket.socket = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden
spec = importlib.util.spec_from_file_location('offline_probe', sys.argv[3])
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
report = probe.http_client()
print(json.dumps({'client': report, 'socksio': probe.modules({'socksio': 'socksio'})['socksio'],
                  'created_clients': len(clients), 'all_clients_closed': all(client.is_closed for client in clients)}))
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-c", program, json.dumps(selected),
                             str(certificate), str(SCRIPTS / "probe.py")],
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "synthetic_user" not in result.stdout and "synthetic_password" not in result.stdout
    assert "proxy.invalid" not in result.stdout and "socks5://" not in result.stdout
    return json.loads(result.stdout)


def test_bundled_socks_transport_initializes_and_closes_without_network(wheels):
    report = client_check(wheels, include_socksio=True)
    assert report["client"] == {"ready": True, "request_executed": False,
                                "environment_settings_inherited": True}
    assert report["socksio"]["importable"] is True
    assert report["created_clients"] == 1 and report["all_clients_closed"] is True


def test_missing_socks_dependency_is_blocked_without_bypassing_host_proxy(wheels):
    report = client_check(wheels, include_socksio=False)
    assert report["socksio"]["importable"] is False
    assert report["client"]["ready"] is False
    assert report["client"]["request_executed"] is False
    assert report["client"]["environment_settings_inherited"] is True
    assert report["client"]["error"]["code"] == "HTTP_CLIENT_INIT_FAILED"
    assert report["client"]["error"]["exception"] == "ImportError"
    assert report["created_clients"] == 0


def test_client_exception_never_serializes_proxy_credentials(monkeypatch):
    import httpx
    probe = load_helper("probe")
    called = []

    def rejected(**options):
        called.append(options)
        raise ValueError("Invalid proxy socks5://private_user:private_secret@private.invalid:1080")

    monkeypatch.setattr(httpx, "Client", rejected)
    report = probe.http_client()
    assert called == [{"trust_env": True}]
    assert report["ready"] is False and report["error"]["exception"] == "ValueError"
    assert "private_" not in json.dumps(report) and "socks5://" not in json.dumps(report)


@pytest.mark.parametrize("ready", [False, True])
def test_private_prepare_isolated_closure_and_actual_client_required(tmp_path, monkeypatch, ready):
    bootstrap = load_helper("prepare_host")
    root = tmp_path / 'package'
    root.mkdir()
    wheel = root / 'fixture.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('fixture-1.0.dist-info/METADATA', 'Name: fixture\nVersion: 1.0\n')
        archive.writestr('fixture-1.0.dist-info/LICENSE', 'A test fixture, not a real dependency.')
    node = root / 'node-v24.21.0-win-x64.zip'
    with zipfile.ZipFile(node, 'w') as archive:
        archive.writestr('node-v24.21.0-win-x64/node.exe', b'test executable; never run')
        archive.writestr('node-v24.21.0-win-x64/LICENSE', 'test license')
    declaration = {'name': 'fixture', 'version': '1.0', 'filename': wheel.name, 'sha256': bootstrap.digest(wheel)}
    manifest = {'schema': 1, 'profiles': {'windows-x86_64-cp312': {'wheels': [wheel.name]}},
                'wheels': {wheel.name: declaration}, 'node': {'windows-x86_64': {'filename': node.name, 'version': '24.21.0'}}}
    (root / 'host-dependencies.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(bootstrap, 'ROOT', root)
    monkeypatch.setattr(bootstrap, 'verified_package', lambda: 51)
    monkeypatch.setattr(bootstrap, 'host_profile', lambda: ('windows-x86_64-cp312', 'windows-x86_64'))
    monkeypatch.setattr(bootstrap, 'artifact', lambda cache, item, **options: (root / item['filename'], False))
    monkeypatch.setattr(bootstrap, 'download_transport', lambda *args: type('Client', (), {'close': lambda self: None})())
    options = []

    class Builder:
        def __init__(self, **values):
            options.append(values)

        def create(self, target):
            executable = target / 'Scripts/python.exe'
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b'test executable; never run')
            pandoc = target / 'Lib/site-packages/pypandoc/files/pandoc.exe'
            pandoc.parent.mkdir(parents=True)
            pandoc.write_bytes(b'test executable; never run')

    monkeypatch.setattr(bootstrap.venv, 'EnvBuilder', Builder)
    calls = []
    scratch = tmp_path / 'private'

    def fake_run(command, *, environment=None, timeout=180):
        calls.append((command, environment))
        if command[1:3] == ['-m', 'pip']:
            assert '--no-index' in command and '--require-hashes' in command
            assert '--only-binary=:all:' in command
            return {'exit_code': 0, 'stdout': '', 'error': None}
        if command[-1] == '--version':
            value = 'v24.21.0\n' if command[0].endswith('node.exe') else 'pandoc 3.8.3\n'
            return {'exit_code': 0, 'stdout': value, 'error': None}
        if command[1].endswith('probe.py'):
            value = {'ok': True, 'result': {'controller_imported': True, 'mcp_imported': False, 'package': {'verified': True},
                     'http_client': {'ready': ready}, 'dependencies': {'core': {'fixture': {'importable': True}}}}}
        elif 'prefix' in command[2]:
            value = {'prefix': str(scratch / 'runtime')}
        else:
            module_file = scratch / 'prepared-modules.json'
            module_file.write_text('{}')
            value = {'pdf_header': True, 'pages': 1, 'diagnostic_only': True, 'research_paper': False,
                     'png': {'size': 1}, 'outputs': {'pdf': {}, 'docx': {}, 'tex': {}},
                     'modules': {'path': str(module_file), 'sha256': bootstrap.digest(module_file)}}
        return {'exit_code': 0, 'stdout': json.dumps(value), 'error': None}

    monkeypatch.setattr(bootstrap, 'run', fake_run)
    report = bootstrap.prepare(scratch)
    assert report['ok'] is ready
    assert options == [{'system_site_packages': False, 'with_pip': True, 'symlinks': False}]
    assert all(env['PF_NODE_BIN'] == str(scratch / 'node/node.exe') for _, env in calls)
    assert report['experiment_executed'] is False and report['os_installer_used'] is False
    retained = json.loads(Path(report['retained_result']['path']).read_bytes())
    assert retained['ok'] is ready
    if ready:
        context = json.loads(Path(report['environment_file']).read_bytes())
        assert context['schema_version'] == 2 and context['mode'] == 'private'
        assert context['python']['prefix'] == str(scratch / 'runtime')
        assert context['node']['sha256'] == bootstrap.digest(scratch / 'node/node.exe')
        assert Path(context['variables']['MPLCONFIGDIR']).is_dir()
    else:
        assert not (scratch / 'prepared-host.json').exists()
        assert 'converter_check' not in report


@pytest.mark.parametrize('ready,optional_socksio', [(True, False), (False, False), (True, True)])
def test_provided_host_uses_actual_prefix_and_never_downloads_installs_or_bypasses_proxy(tmp_path, monkeypatch, ready, optional_socksio):
    bootstrap = load_helper('prepare_host')
    root = tmp_path / 'package'
    root.mkdir()
    node, pandoc, latex = [root / name for name in ('node', 'pandoc', 'pdflatex')]
    for path in (node, pandoc, latex):
        path.write_bytes(b'trusted executable fixture; not run')
    monkeypatch.setattr(bootstrap, 'ROOT', root)
    monkeypatch.setattr(bootstrap, 'verified_package', lambda: 41)
    def forbidden(*args, **kwargs):
        pytest.fail('Provided preparation may not download, install or create a venv')
    monkeypatch.setattr(bootstrap, 'artifact', forbidden)
    monkeypatch.setattr(bootstrap, 'download_transport', forbidden)
    monkeypatch.setattr(bootstrap.venv, 'EnvBuilder', forbidden)
    monkeypatch.setenv('ALL_PROXY', 'socks5://synthetic_user:synthetic_password@proxy.invalid:1080')
    monkeypatch.setenv('SSL_CERT_FILE', 'inherited-certificate')
    scratch = tmp_path / 'provided'
    calls = []
    def fake_run(command, *, environment=None, timeout=180):
        calls.append(command)
        assert environment['ALL_PROXY'].startswith('socks5://synthetic_user:')
        assert environment['SSL_CERT_FILE'] == 'inherited-certificate'
        assert environment['PF_HOST_MODE'] == 'provided'
        assert environment['PF_PDF_ENGINE'] == 'pdflatex'
        assert environment['PF_PDFLATEX_BIN'] == str(latex)
        assert '-m' not in command and 'pip' not in command
        if command[-1] == '--version':
            version = 'v22.16.0\n' if command[0] == str(node) else ('pandoc 3.1.11.1\n' if command[0] == str(pandoc) else 'pdfTeX 3.14159\n')
            return {'exit_code': 0, 'stdout': version, 'error': None}
        if command[1].endswith('probe.py'):
            value = {'ok': True, 'result': {'package': {'verified': True}, 'controller_imported': ready,
                     'mcp_imported': False, 'http_client': {'ready': ready},
                     'dependencies': {'core': {'httpx': {'importable': True, 'required': True},
                      'socksio': {'importable': optional_socksio, 'required': False}},
                      'export': {'typst': {'importable': False, 'required': False}}}}}
        elif 'prefix' in command[2]:
            value = {'prefix': sys.prefix}
        else:
            manifest = scratch / 'prepared-modules.json'
            manifest.write_text('{}')
            value = {'pdf_header': True, 'pages': 1, 'png': {'size': 1}, 'outputs': {'pdf': {}, 'docx': {}, 'tex': {}},
                     'modules': {'path': str(manifest), 'sha256': bootstrap.digest(manifest)}}
        return {'exit_code': 0, 'stdout': json.dumps(value), 'error': None}
    monkeypatch.setattr(bootstrap, 'run', fake_run)
    report = bootstrap.prepare(scratch, mode='provided', pdf_engine='pdflatex', node=node, pandoc=pandoc, pdflatex=latex)
    assert report['ok'] is ready
    assert report['dependency_downloads'] == 0 and report['venv_created'] is False and report['dependencies_installed'] is False
    assert report['research_network_access_tested'] is False and report['isolation_checked'] is False
    assert not (scratch / 'runtime').exists() and not (scratch / 'downloads').exists()
    assert 'synthetic_password' not in json.dumps(report) and 'proxy.invalid' not in json.dumps(report)
    if ready:
        config = json.loads(Path(report['environment_file']).read_bytes())
        assert config['python']['prefix'] == str(Path(sys.prefix).absolute())
        assert config['python']['path'] == str(Path(sys.executable).absolute())
        assert config['pdflatex']['path'] == str(latex)
        assert config['mode'] == 'provided' and config['pdf_engine'] == 'pdflatex'
        assert config['modules']['sha256'] == bootstrap.digest(Path(config['modules']['path']))
    else:
        assert not (scratch / 'prepared-host.json').exists() and 'converter_check' not in report


def test_provided_module_failure_preserves_blocked_report_without_installer(tmp_path, monkeypatch):
    bootstrap = load_helper('prepare_host')
    root = tmp_path / 'package'
    root.mkdir()
    monkeypatch.setattr(bootstrap, 'ROOT', root)
    monkeypatch.setattr(bootstrap, 'verified_package', lambda: 41)
    for name in ('node', 'pandoc'):
        (root / name).write_bytes(b'fixture')
    def run(command, **kwargs):
        if command[-1] == '--version':
            value = 'v24.21.0\n' if command[0].endswith('node') else 'pandoc 3.9\n'
        elif command[1].endswith('probe.py'):
            return {'exit_code': 2, 'error': 'Blocked native module import', 'stdout': ''}
        else:
            value = json.dumps({'prefix': sys.prefix})
        return {'exit_code': 0, 'stdout': value, 'error': None}
    monkeypatch.setattr(bootstrap, 'run', run)
    scratch = tmp_path / 'provided'
    report = bootstrap.prepare(scratch, mode='provided', node=root / 'node', pandoc=root / 'pandoc')
    assert report['ok'] is False and report['stage'] == 'controller-prerequisites'
    assert Path(report['retained_result']['path']).is_file()
    assert not (scratch / 'prepared-host.json').exists() and report['dependency_downloads'] == 0


def test_changed_cached_download_is_retained_and_never_replaced(tmp_path, monkeypatch):
    bootstrap = load_helper('prepare_host')
    artifact = tmp_path / 'verified.whl'
    artifact.write_bytes(b'changed')
    client = type('Client', (), {'stream': lambda *args, **kwargs: pytest.fail('No request is allowed')})()
    with pytest.raises(ValueError, match='cache bytes changed'):
        bootstrap.artifact(tmp_path, {'filename': artifact.name, 'sha256': hashlib.sha256(b'original').hexdigest()}, client=client)
    assert artifact.read_bytes() == b'changed'


@pytest.mark.parametrize('url', ['http://files.pythonhosted.org/file', 'https://attacker.invalid/file',
                               'https://user:secret@nodejs.org/file', 'https://nodejs.org:443/file'])
def test_unpinned_artifact_origins_block_before_download(url):
    bootstrap = load_helper('prepare_host')
    with pytest.raises(ValueError, match='outside the pinned'):
        bootstrap.artifact_url(url)


def test_native_wheel_identity_and_licenses_bound_before_install(tmp_path):
    bootstrap = load_helper('prepare_host')
    wheel = tmp_path / 'native.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('native-1.dist-info/METADATA', 'Name: native\nVersion: 1\n')
        archive.writestr('native-1.dist-info/LICENSE', 'retained license')
    receipt = bootstrap.wheel_receipt(wheel, {'name': 'native', 'version': '1'})
    assert receipt['license_files'] == {'native-1.dist-info/LICENSE': hashlib.sha256(b'retained license').hexdigest()}
    with pytest.raises(ValueError, match='identity differs'):
        bootstrap.wheel_receipt(wheel, {'name': 'other', 'version': '1'})


def test_all_host_profiles_have_pinned_python_and_marker_closure():
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.utils import canonicalize_name
    from packaging.version import Version
    manifest = json.loads((SKILL / 'host-dependencies.json').read_bytes())
    assert len(manifest['profiles']) == 12
    for profile, declaration in manifest['profiles'].items():
        system, machine, python = profile.split('-')
        version = '3.' + python[3:]
        environment = {'python_version': version, 'python_full_version': version + '.0',
                       'sys_platform': {'windows': 'win32', 'linux': 'linux', 'macos': 'darwin'}[system],
                       'platform_system': {'windows': 'Windows', 'linux': 'Linux', 'macos': 'Darwin'}[system],
                       'platform_machine': machine, 'platform_python_implementation': 'CPython',
                       'implementation_name': 'cpython', 'os_name': 'nt' if system == 'windows' else 'posix', 'extra': ''}
        selected = {manifest['wheels'][filename]['name'] for filename in declaration['wheels']}
        expected = set(manifest['pins']) - ({'pypandoc-binary'} if system == 'macos' else set())
        assert selected == expected
        for filename in declaration['wheels']:
            wheel = manifest['wheels'][filename]
            assert Version(version) in SpecifierSet(wheel['requires_python'] or '')
            for raw in wheel['requires_dist']:
                requirement = Requirement(raw)
                if requirement.marker and not requirement.marker.evaluate(environment):
                    continue
                name = canonicalize_name(requirement.name)
                assert name in selected
                assert Version(manifest['pins'][name]) in requirement.specifier


def test_bootstrap_real_pinned_transport_inherits_socks_without_a_request(tmp_path):
    program = '''
import importlib.util,json,os,pathlib,socket,ssl,sys
for key in tuple(os.environ):
    if key.lower().endswith('_proxy') or key in ('SSL_CERT_FILE','SSL_CERT_DIR'):
        del os.environ[key]
os.environ['ALL_PROXY']='socks5://fixture_user:fixture_password@proxy.invalid:1080'
def forbidden(*args,**kwargs):
    raise AssertionError('Bootstrap initialization attempted network access')
socket.socket=forbidden
socket.create_connection=forbidden
socket.getaddrinfo=forbidden
root=pathlib.Path(sys.argv[1])
spec=importlib.util.spec_from_file_location('bootstrap',root/'scripts/prepare_host.py')
bootstrap=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
data=pathlib.Path(sys.argv[2]);data.mkdir()
manifest=json.loads((root/'host-dependencies.json').read_bytes())
client=bootstrap.download_transport(data,manifest,'windows-x86_64-cp312')
import httpx,socksio
assert pathlib.Path(httpx.__file__).is_relative_to(data)
assert pathlib.Path(socksio.__file__).is_relative_to(data)
client.close()
print(json.dumps({'ready':True,'closed':client.is_closed,'request_executed':False}))
'''
    result = subprocess.run([sys.executable, '-I', '-S', '-c', program, str(SKILL), str(tmp_path / 'private')],
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'ready': True, 'closed': True, 'request_executed': False}
    assert 'fixture_user' not in result.stdout and 'fixture_password' not in result.stdout


def test_declared_proxy_dependency_wheel_and_license_are_exact():
    bootstrap = load_helper("prepare_host")
    manifest = json.loads((SKILL / "host-dependencies.json").read_bytes())
    declarations = [item for item in manifest["wheels"].values() if item["name"] in TRANSPORT]
    assert len(declarations) == len(TRANSPORT) and {item["name"] for item in declarations} == TRANSPORT
    dependencies = {item["name"]: item for item in declarations}
    dependency = dependencies["socksio"]
    assert dependency["version"] == manifest["pins"]["socksio"]
    raw = (SKILL / "wheelhouse" / dependency["filename"]).read_bytes()
    assert len(raw) == dependency["size"]
    assert hashlib.sha256(raw).hexdigest() == dependency["sha256"]
    receipt = bootstrap.wheel_receipt(SKILL / "wheelhouse" / dependency["filename"], dependency)
    assert receipt["size"] == dependency["size"] and receipt["sha256"] == dependency["sha256"]
    with zipfile.ZipFile(SKILL / "wheelhouse" / dependencies["httpx"]["filename"]) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode()
    assert "Requires-Dist: socksio==1.*; extra == 'socks'" in metadata
    with zipfile.ZipFile(SKILL / "wheelhouse" / dependency["filename"]) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name)
        assert not re.findall(r"^Requires-Dist:", metadata.decode(), flags=re.MULTILINE)
        assert receipt["metadata_sha256"] == hashlib.sha256(metadata).hexdigest()
        license_name = metadata_name.removesuffix("METADATA") + "LICENSE"
        assert receipt["license_files"] == {license_name: hashlib.sha256(archive.read(license_name)).hexdigest()}
