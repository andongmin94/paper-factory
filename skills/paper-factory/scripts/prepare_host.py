"""Prepare the selected private or provided host without an OS installer."""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import urllib.parse
import venv
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_EXECUTABLE = 256 * 1024 * 1024
TRANSPORT = {'httpx', 'httpcore', 'h11', 'anyio', 'idna', 'certifi', 'typing-extensions', 'socksio'}

CONVERTER_CHECK = '''
import hashlib, importlib.util, json, pathlib, sys
from pypdf import PdfReader
from docx import Document
from paper_factory.conversion import convert
from paper_factory.workflow import WorkflowService
from PIL import Image
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot
root = pathlib.Path(sys.argv[1])
figure = root / 'converter-check.png'
plot, axis = pyplot.subplots(figsize=(3, 2))
axis.plot([0, 1], [0, 1])
plot.savefig(figure)
pyplot.close(plot)
assert figure.read_bytes().startswith(b'\\x89PNG\\r\\n\\x1a\\n')
with Image.open(figure) as image:
    image.verify()
with Image.open(figure) as image:
    image.load()
    assert image.format == 'PNG' and image.width > 0 and image.height > 0
source = root / 'converter-check.md'
source.write_text('# Bundled converter check\\n\\nTrusted diagnostic only.\\n\\n![Trusted diagnostic](converter-check.png)\\n\\n| Fixture | Count |\\n| --- | ---: |\\n| Diagnostic | 1 |\\n', encoding='utf-8')
outputs = {}
for extension in ('pdf', 'docx', 'tex'):
    output = root / ('converter-check.' + extension)
    receipt = convert(source, output)
    raw = output.read_bytes()
    outputs[extension] = {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'receipt': receipt}
reader = PdfReader(root / 'converter-check.pdf', strict=True)
assert not reader.is_encrypted and len(reader.pages) == 1
assert 'Trusted diagnostic only.' in reader.pages[0].extract_text()
assert any('Trusted diagnostic only.' in p.text for p in Document(root / 'converter-check.docx').paragraphs)
assert len(Document(root / 'converter-check.docx').inline_shapes) == 1
assert len(Document(root / 'converter-check.docx').tables) == 1
assert 'Trusted diagnostic only.' in (root / 'converter-check.tex').read_text(encoding='utf-8')
assert '\\\\includegraphics' in (root / 'converter-check.tex').read_text(encoding='utf-8')
spec = importlib.util.spec_from_file_location('prepared_module_capture', sys.argv[2])
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)
modules = context.capture_modules(sys.argv[3])
manifest = root / 'prepared-modules.json'
manifest.write_text(json.dumps(modules, indent=2) + '\\n', encoding='utf-8')
print(json.dumps({'pdf_header': (root / 'converter-check.pdf').read_bytes().startswith(b'%PDF-'),
                  'pages': len(reader.pages), 'diagnostic_only': True, 'research_paper': False,
                  'png': {'size': figure.stat().st_size, 'sha256': hashlib.sha256(figure.read_bytes()).hexdigest()},
                  'modules': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                              'files': len(modules['files']), 'distributions': modules['distributions']},
                  'outputs': outputs}))
'''


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def ordinary(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (path, *path.parents)):
        raise ValueError('Linked preparation path is forbidden')
    if path.exists() and (not stat.S_ISREG(path.stat().st_mode) or path.stat().st_nlink != 1):
        raise ValueError('Preparation input must be an ordinary single-link file')
    return path


def verified_package():
    inventory = json.loads(ordinary(ROOT / 'inventory.json').read_bytes())
    for name, expected in inventory['files'].items():
        if (not name or PurePosixPath(name).is_absolute() or '\\' in name or ':' in name
                or any(part in {'', '.', '..'} for part in name.split('/'))):
            raise ValueError('Invalid package inventory path')
        path = ordinary(ROOT / name)
        if not path.is_file() or path.stat().st_size != expected['size'] or digest(path) != expected['sha256']:
            raise ValueError('Installed package bytes changed')
    return len(inventory['files'])


def host_profile():
    aliases = {'AMD64': 'x86_64', 'amd64': 'x86_64', 'x64': 'x86_64', 'aarch64': 'arm64'}
    machine = aliases.get(platform.machine(), platform.machine())
    system = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'macos'}.get(platform.system())
    if (sys.implementation.name != 'cpython' or sys.version_info[:2] not in ((3, 12), (3, 13), (3, 14))
            or sysconfig.get_config_var('Py_GIL_DISABLED')
            or (system, machine) not in {('windows', 'x86_64'), ('linux', 'x86_64'), ('macos', 'x86_64'), ('macos', 'arm64')}):
        raise ValueError('No pinned preparation profile for this host. Host script access and CPython3.12,3.13 or3.14 on Windows/Linux x86_64 or macOS x86_64/arm64 are required; no installer is invoked.')
    if system == 'linux':
        library, version = platform.libc_ver()
        if library != 'glibc' or tuple(int(x) for x in version.split('.')[:2]) < (2, 28):
            raise ValueError('Pinned Linux wheels require glibc2.28 or newer')
    if system == 'macos' and tuple(int(x) for x in platform.mac_ver()[0].split('.')[:2]) < (14, 0):
        raise ValueError('Pinned macOS wheel profiles require macOS14 or newer; actual macOS execution remains unverified')
    return f'{system}-{machine}-cp3{sys.version_info.minor}', f'{system}-{machine}'


def artifact_url(url, *, redirect=False):
    parsed = urllib.parse.urlsplit(url)
    origin = parsed.hostname in {'files.pythonhosted.org', 'nodejs.org'}
    pandoc = parsed.hostname == 'github.com' and re.fullmatch(
        r'/jgm/pandoc/releases/download/[0-9.]+/pandoc-[0-9.]+-(?:arm64|x86_64)-macOS\.zip', parsed.path)
    relay = redirect and parsed.hostname == 'release-assets.githubusercontent.com'
    if (parsed.scheme != 'https' or not (origin or pandoc or relay)
            or parsed.username or parsed.password or parsed.port is not None or parsed.fragment):
        raise ValueError('Dependency URL is outside the pinned official artifact origins')
    return url


def download_transport(data, manifest, profile):
    """Load only verified pure upstream wheels, preserving inherited SOCKS/TLS."""
    target = data / 'download-transport'
    target.mkdir()
    selected = [manifest['wheels'][name] for name in manifest['profiles'][profile]['wheels']
                if manifest['wheels'][name]['name'] in TRANSPORT]
    if {item['name'] for item in selected} != TRANSPORT:
        raise ValueError('Pinned bootstrap transport closure is incomplete')
    occupied = set()
    for record in selected:
        source = ordinary(ROOT / 'wheelhouse' / record['filename'])
        if source.stat().st_size != record['size'] or digest(source) != record['sha256']:
            raise ValueError('Pinned bootstrap transport wheel changed')
        with zipfile.ZipFile(source) as wheel:
            if wheel.testzip():
                raise ValueError('Bootstrap transport wheel CRC failed')
            for info in wheel.infolist():
                name = info.filename
                if info.is_dir():
                    continue
                if (PurePosixPath(name).is_absolute() or '\\' in name or ':' in name
                        or any(p in {'', '.', '..'} for p in name.split('/'))
                        or stat.S_ISLNK(info.external_attr >> 16) or info.file_size > 4 * 1024 * 1024
                        or name.casefold() in occupied):
                    raise ValueError('Unsafe bootstrap transport wheel entry')
                occupied.add(name.casefold())
                output = target.joinpath(*PurePosixPath(name).parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('xb') as stream:
                    stream.write(wheel.read(info))
    # This modifies only this helper process; neither host packages nor OS PATH.
    # Removing already loaded copies prevents a host HTTPX version from taking
    # precedence over the explicitly pinned transport.
    module_names = {'httpx', 'httpcore', 'h11', 'anyio', 'idna', 'certifi', 'typing_extensions', 'socksio'}
    if any(name.split('.')[0] in module_names for name in sys.modules):
        raise ValueError('Prepare the pinned transport in a fresh helper process')
    sys.path.insert(0, str(target))
    import httpx
    return httpx.Client(trust_env=True, timeout=60, follow_redirects=False)


def artifact(cache, record, *, client=None):
    name = record['filename']
    if PurePosixPath(name).name != name or '\\' in name or ':' in name:
        raise ValueError('Invalid dependency artifact filename')
    expected = record['sha256']
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('Invalid dependency artifact digest')
    limit = record.get('size', record.get('max_bytes', MAX_DOWNLOAD))
    if type(limit) is not int or not 0 < limit <= MAX_DOWNLOAD:
        raise ValueError('Dependency download exceeds the bounded artifact policy')
    target = ordinary(cache / name)
    if target.exists():
        if (target.stat().st_size > limit or digest(target) != expected
                or ('size' in record and target.stat().st_size != record['size'])):
            raise ValueError('Retained dependency cache bytes changed; preserve this failure')
        return target, False
    # Reuse exact original wheels when a maintainer checkout supplies them.
    bundled = ROOT / 'wheelhouse' / name
    partial = ordinary(cache / (name + '.partial'))
    if partial.exists():
        raise ValueError('Retained partial dependency download requires inspection')
    downloaded = not bundled.is_file()
    with partial.open('xb') as output:
        if not downloaded:
            source = ordinary(bundled)
            if source.stat().st_size > limit:
                raise ValueError('Bundled dependency exceeds its declared size bound')
            with source.open('rb') as stream:
                shutil.copyfileobj(stream, output)
        else:
            if client is None:
                raise ValueError('A verified inherited-proxy transport is required for dependency downloads')
            url = artifact_url(record['url'])
            pandoc_redirect = urllib.parse.urlsplit(url).hostname == 'github.com'
            for hop in range(4):
                with client.stream('GET', url, follow_redirects=False) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if hop == 3 or 'location' not in response.headers:
                            raise ValueError('Official artifact redirect exceeds its bounded policy')
                        # Check the next origin before sending the next request.
                        url = artifact_url(urllib.parse.urljoin(url, response.headers['location']), redirect=pandoc_redirect)
                        continue
                    response.raise_for_status()
                    total = 0
                    for chunk in response.iter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > limit:
                            raise ValueError('Dependency response exceeds its pinned size bound')
                        output.write(chunk)
                    break
    if digest(partial) != expected or ('size' in record and partial.stat().st_size != record['size']):
        raise ValueError('Official dependency bytes differ from the pinned digest/size')
    partial.rename(target)
    return target, downloaded


def wheel_receipt(path, record):
    with zipfile.ZipFile(path) as wheel:
        if wheel.testzip():
            raise ValueError('Dependency wheel failed CRC verification')
        names = wheel.namelist()
        for name in names:
            if (PurePosixPath(name).is_absolute() or '\\' in name or ':' in name
                    or any(p in {'.', '..'} for p in PurePosixPath(name).parts)):
                raise ValueError('Unsafe dependency wheel entry')
        metadata_paths = [name for name in names if name.endswith('.dist-info/METADATA')]
        if len(metadata_paths) != 1:
            raise ValueError('Dependency wheel has ambiguous metadata')
        metadata_raw = wheel.read(metadata_paths[0])
        metadata = BytesParser().parsebytes(metadata_raw)
        normalize = lambda value: re.sub('[-_.]+', '-', value).lower()
        if normalize(metadata['Name']) != normalize(record['name']) or metadata['Version'] != record['version']:
            raise ValueError('Dependency wheel identity differs from the pinned release')
        licenses = {name: hashlib.sha256(wheel.read(name)).hexdigest() for name in names
                    if not name.endswith('/') and any(word in PurePosixPath(name).name.lower()
                                                      for word in ('license', 'copying', 'copyright', 'notice'))}
        if not licenses:
            raise ValueError('Pinned dependency wheel has no retained license/notice')
        return {'name': record['name'], 'version': record['version'], 'filename': path.name,
                'size': path.stat().st_size, 'sha256': digest(path),
                'metadata_sha256': hashlib.sha256(metadata_raw).hexdigest(), 'license_files': licenses}


def prepare_node(archive, destination, family):
    destination.mkdir()
    basename = 'node.exe' if family.startswith('windows') else 'node'
    selected = {}
    if archive.name.endswith('.zip'):
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip():
                raise ValueError('Node archive CRC failed')
            root = archive.name.removesuffix('.zip')
            for name, target in {root + '/node.exe': basename, root + '/LICENSE': 'LICENSE'}.items():
                info = bundle.getinfo(name)
                if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) or info.file_size > MAX_EXECUTABLE:
                    raise ValueError('Node archive executable/license is not a bounded ordinary file')
                selected[target] = bundle.read(name)
    else:
        root = archive.name.removesuffix('.tar.xz')
        with tarfile.open(archive, 'r:xz') as bundle:
            for name, target in {root + '/bin/node': basename, root + '/LICENSE': 'LICENSE'}.items():
                info = bundle.getmember(name)
                if not info.isfile() or info.size > MAX_EXECUTABLE:
                    raise ValueError('Node archive executable/license is not a bounded ordinary file')
                with bundle.extractfile(info) as stream:
                    selected[target] = stream.read(MAX_EXECUTABLE + 1)
    for name, raw in selected.items():
        output = destination / name
        output.write_bytes(raw)
        if name == basename:
            output.chmod(0o700)
    return destination / basename


def prepare_macos_pandoc(archive, destination, record, family):
    """Extract the pinned native binary and retain original upstream notices."""
    destination.mkdir()
    binary = record['binary']
    expected_cpu = {'macos-arm64': 0x0100000c, 'macos-x86_64': 0x01000007}[family]
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() or len(bundle.namelist()) != len(set(bundle.namelist())):
            raise ValueError('Pandoc archive CRC or unique member check failed')
        name = binary['member']
        if (PurePosixPath(name).is_absolute() or '\\' in name or ':' in name
                or any(p in {'', '.', '..'} for p in name.split('/'))):
            raise ValueError('Invalid pinned Pandoc binary member')
        info = bundle.getinfo(name)
        if (info.is_dir() or stat.S_ISLNK(info.external_attr >> 16)
                or info.file_size != binary['size'] or info.file_size > MAX_EXECUTABLE):
            raise ValueError('Pandoc binary is not the bounded pinned ordinary file')
        output = destination / 'pandoc'
        with bundle.open(info) as source, output.open('xb') as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
    if output.stat().st_size != binary['size'] or digest(output) != binary['sha256']:
        raise ValueError('Pandoc binary differs from the reviewed original bytes')
    with output.open('rb') as stream:
        header = stream.read(8)
    if header[:4] != b'\xcf\xfa\xed\xfe' or int.from_bytes(header[4:8], 'little') != expected_cpu:
        raise ValueError('Pandoc Mach-O architecture differs from the actual macOS host')
    licenses = {}
    if set(record['licenses']) != {'licenses/pandoc/COPYING.md', 'licenses/pandoc/COPYRIGHT'}:
        raise ValueError('Pandoc original upstream notices are incomplete')
    for name, declaration in record['licenses'].items():
        source = ordinary(ROOT / name)
        if source.stat().st_size != declaration['size'] or digest(source) != declaration['sha256']:
            raise ValueError('Pandoc original upstream notice bytes changed')
        target = destination / PurePosixPath(name).name
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
        licenses[name] = {'size': target.stat().st_size, 'sha256': digest(target),
                          'source_url': declaration['source_url']}
    output.chmod(0o700)
    return output, {'version': record['version'], 'archive': archive.name,
                    'archive_size': archive.stat().st_size, 'archive_sha256': digest(archive),
                    'binary': binary, 'licenses': licenses}


def run(command, *, environment=None, timeout=180):
    result = subprocess.run(command, timeout=timeout, capture_output=True, env=environment,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    # Download/proxy errors can contain credentials. Retain class/status, not stderr.
    return {'command': command, 'exit_code': result.returncode, 'stdout': result.stdout.decode('utf-8', errors='replace')[-24000:],
            'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
            'stderr_sha256': hashlib.sha256(result.stderr).hexdigest(),
            'stdout_bytes': len(result.stdout), 'stderr_bytes': len(result.stderr),
            'error': None if result.returncode == 0 else 'Private prerequisite command failed; inspect the pinned artifacts and current host capabilities.'}


def checked_json(report):
    if report['exit_code'] != 0:
        raise ValueError(report['error'])
    return json.loads(report['stdout'])


def scratch_directory(data):
    data = data.expanduser().absolute()
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (data, *data.parents)):
        raise ValueError('Linked scratch path is forbidden')
    data = data.resolve()
    if data == ROOT or ROOT in data.parents or data in ROOT.parents:
        raise ValueError('Scratch must be outside installed resources')
    if data.exists() and (not data.is_dir() or any(data.iterdir())):
        raise ValueError('Use empty approved scratch for the first attempt; preserve earlier reports and failures')
    data.mkdir(parents=True, exist_ok=True)
    return data


def prerequisites(python, environment, report):
    report['stage'] = 'controller-prerequisites'
    check = run([str(python), str(ROOT / 'scripts/probe.py'), 'capabilities'], environment=environment)
    report['steps'].append({'action': 'controller-prerequisites', **check})
    capabilities = checked_json(check)
    report['capabilities'] = capabilities
    result = capabilities.get('result', {})
    report['controller_imported'] = result.get('controller_imported') is True
    if (capabilities.get('ok') is not True or not report['controller_imported']
            or result.get('http_client', {}).get('ready') is not True or result.get('mcp_imported') is not False
            or result.get('package', {}).get('verified') is not True
            or not all(item.get('importable') is True for group in result.get('dependencies', {}).values()
                       for item in group.values() if item.get('required', True))):
        raise ValueError('Selected controller prerequisites remain unavailable')


def finalize(data, python, prefix, node, pandoc, environment, report, *, mode, pdf_engine, pdflatex=None):
    environment.update(PF_HOST_MODE=mode, PF_PDF_ENGINE=pdf_engine, PYTHONPATH=str(ROOT / 'src'))
    prerequisites(python, environment, report)
    report['stage'] = 'native-converter-diagnostic'
    check = run([str(python), '-c', CONVERTER_CHECK, str(data),
                 str(ROOT / 'scripts/host_context.py'), pdf_engine], environment=environment, timeout=180)
    report['steps'].append({'action': 'native-converter-diagnostic', **check})
    converter = checked_json(check)
    report['converter_check'] = converter
    if (converter.get('pdf_header') is not True or converter.get('pages') != 1
            or not isinstance(converter.get('png'), dict) or converter['png'].get('size', 0) <= 0
            or set(converter.get('outputs', {})) != {'pdf', 'docx', 'tex'}):
        raise ValueError('Selected native converter diagnostic failed')
    modules = converter.get('modules', {})
    manifest = ordinary(data / 'prepared-modules.json')
    if (modules.get('path') != str(manifest) or not manifest.is_file()
            or manifest.stat().st_size > 2 * 1024 * 1024 or digest(manifest) != modules.get('sha256')):
        raise ValueError('Actual installed-module identity manifest is unavailable')
    environment_file = data / 'prepared-host.json'
    prepared = {'schema_version': 2, 'mode': mode, 'pdf_engine': pdf_engine,
                'python': {'path': str(python), 'prefix': str(prefix), 'sha256': digest(python)},
                'node': {'path': str(node), 'sha256': digest(node)},
                'pandoc': {'path': str(pandoc), 'sha256': digest(pandoc)},
                'pdflatex': None if pdflatex is None else {'path': str(pdflatex),
                            'target_path': str(pdflatex.resolve()), 'sha256': digest(pdflatex)},
                'modules': {'path': str(manifest), 'sha256': digest(manifest)},
                'variables': {'MPLCONFIGDIR': str(data / 'matplotlib')}}
    environment_file.write_text(json.dumps(prepared, indent=2) + '\n', encoding='utf-8')
    report.update(ok=True, stage='prepared', python=str(python), environment_file=str(environment_file),
                  environment_sha256=digest(environment_file),
                  environment={name: environment[name] for name in ('PF_NODE_BIN', 'PYPANDOC_PANDOC',
                     'PF_HOST_MODE', 'PF_PDF_ENGINE', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE', 'MPLCONFIGDIR')})
    if pdflatex is not None:
        report['environment']['PF_PDFLATEX_BIN'] = str(pdflatex)


def retained_result(data, report):
    output = data / 'bootstrap-result.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    report['retained_result'] = {'path': str(output), 'size': output.stat().st_size, 'sha256': digest(output)}
    return report


def prepare_private(data):
    checked = verified_package()
    profile, family = host_profile()
    manifest = json.loads(ordinary(ROOT / 'host-dependencies.json').read_bytes())
    if manifest.get('schema') != 1 or profile not in manifest['profiles']:
        raise ValueError('No reviewed dependency profile for the current host')
    data = scratch_directory(data)
    cache = data / 'downloads'
    cache.mkdir()
    report = {'mode': 'private', 'pdf_engine': 'typst', 'profile': profile, 'package_files_verified': checked, 'plugin_modified': False,
              'host_python_modified': False, 'os_installer_used': False, 'experiment_executed': False,
              'research_network_access_tested': False, 'isolation_checked': False, 'steps': [], 'dependencies': [],
              'dependency_manifest_sha256': digest(ROOT / 'host-dependencies.json'), 'dependency_downloads': 0,
              'stage': 'download-transport'}
    client = None
    try:
        client = download_transport(data, manifest, profile)
        report['stage'] = 'dependency-download'
        lock_lines = []
        for filename in manifest['profiles'][profile]['wheels']:
            report['current_artifact'] = filename
            declaration = manifest['wheels'][filename]
            path, downloaded = artifact(cache, declaration, client=client)
            report['dependency_downloads'] += int(downloaded)
            report['dependencies'].append(wheel_receipt(path, declaration))
            lock_lines.append(f"{declaration['name']}=={declaration['version']} --hash=sha256:{declaration['sha256']}")
        lock = data / 'dependencies.lock'
        lock.write_text('\n'.join(lock_lines) + '\n', encoding='utf-8')
        node_record = manifest['node'][family]
        report.update(stage='node-prepare', current_artifact=node_record['filename'])
        node_archive, downloaded = artifact(cache, node_record, client=client)
        report['dependency_downloads'] += int(downloaded)
        node = prepare_node(node_archive, data / 'node', family)
        report['node_asset'] = {'version': node_record['version'], 'archive': node_archive.name,
                              'archive_sha256': digest(node_archive), 'archive_size': node_archive.stat().st_size,
                              'executable_sha256': digest(node), 'license_sha256': digest(node.parent / 'LICENSE')}
        pandoc = None
        if family.startswith('macos-'):
            pandoc_record = manifest['pandoc'][family]
            report.update(stage='pandoc-prepare', current_artifact=pandoc_record['filename'])
            pandoc_archive, downloaded = artifact(cache, pandoc_record, client=client)
            report['dependency_downloads'] += int(downloaded)
            pandoc, report['pandoc_asset'] = prepare_macos_pandoc(pandoc_archive, data / 'pandoc', pandoc_record, family)
        target = data / 'runtime'
        report['stage'] = 'private-venv'
        venv.EnvBuilder(system_site_packages=False, with_pip=True, symlinks=False).create(target)
        python = target / ('Scripts/python.exe' if family.startswith('windows') else 'bin/python')
        (data / 'matplotlib').mkdir()
        environment = {**os.environ, 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                       'PF_NODE_BIN': str(node), 'MPLCONFIGDIR': str(data / 'matplotlib')}
        install = run([str(python), '-m', 'pip', '--isolated', 'install', '--no-index', '--find-links', str(cache),
                       '--require-hashes', '--disable-pip-version-check', '--no-input', '--no-cache-dir',
                       '--only-binary=:all:', '-r', str(lock)], environment=environment)
        report['steps'].append({'action': 'private-wheel-install', **install})
        if install['exit_code'] != 0:
            raise ValueError(install['error'])
        if pandoc is None:
            pandoc = target / ('Lib/site-packages/pypandoc/files/pandoc.exe' if family.startswith('windows')
                               else f'lib/python3.{sys.version_info.minor}/site-packages/pypandoc/files/pandoc')
        ordinary(pandoc)
        environment['PYPANDOC_PANDOC'] = str(pandoc)
        info = checked_json(run([str(python), '-c', 'import json,sys;print(json.dumps({"prefix":sys.prefix}))'], environment=environment))
        if Path(info['prefix']).resolve() != target.resolve():
            raise ValueError('Private interpreter prefix differs from the prepared directory')
        for binary, expected_prefix in ((node, 'v24.'), (pandoc, 'pandoc ')):
            ordinary(binary)
            check = run([str(binary), '--version'], environment=environment, timeout=15)
            if check['exit_code'] != 0 or not check['stdout'].startswith(expected_prefix):
                raise ValueError('Pinned private executable failed its actual version check')
        environment['PYTHONPATH'] = str(ROOT / 'src')
        finalize(data, python, target, node, pandoc, environment, report, mode='private', pdf_engine='typst')
    except Exception as error:
        report.update(ok=False, error={'code': 'HOST_PREPARATION_FAILED', 'exception': type(error).__name__,
                      'message': 'Private host preparation failed. Retain this scratch and its artifacts; inspect profile compatibility, pinned bytes, dependency download access and prerequisite command status.'})
    finally:
        if client is not None:
            client.close()
    return retained_result(data, report)


def provided_executable(name, explicit=None, *, keep_alias=False):
    selected = str(explicit) if explicit else shutil.which(name)
    if not selected or not Path(selected).is_absolute() or not Path(selected).is_file():
        raise ValueError('The explicitly selected provided executable is unavailable')
    path = Path(selected).absolute()
    target = ordinary(path.resolve())
    if keep_alias:
        return path
    return target


def prepare_provided(data, *, pdf_engine='typst', node=None, pandoc=None, pdflatex=None):
    checked = verified_package()
    if pdf_engine not in {'typst', 'pdflatex'}:
        raise ValueError('Select typst or pdflatex explicitly')
    if pdf_engine != 'pdflatex' and pdflatex is not None:
        raise ValueError('Typst preparation cannot select a pdflatex executable')
    data = scratch_directory(data)
    report = {'mode': 'provided', 'pdf_engine': pdf_engine, 'package_files_verified': checked,
              'plugin_modified': False, 'host_python_modified': False, 'os_installer_used': False,
              'venv_created': False, 'dependencies_installed': False, 'dependency_downloads': 0,
              'experiment_executed': False, 'research_network_access_tested': False, 'isolation_checked': False,
              'stage': 'provided-host-identities', 'steps': [],
              'identity_scope': 'Observed installed bytes and functional diagnostics; no upstream wheel authentication.'}
    try:
        if (sys.implementation.name != 'cpython' or sys.version_info[:2] not in ((3, 12), (3, 13), (3, 14))
                or sysconfig.get_config_var('Py_GIL_DISABLED')):
            raise ValueError('The provided controller needs standard-GIL CPython3.12,3.13 or3.14')
        # Preserve a provided venv's Python alias: resolving it can launch its base interpreter.
        python = Path(sys.executable).absolute()
        prefix = Path(sys.prefix).absolute()
        node = provided_executable('node', node)
        pandoc = provided_executable('pandoc', pandoc)
        pdflatex = provided_executable('pdflatex', pdflatex, keep_alias=True) if pdf_engine == 'pdflatex' else None
        (data / 'matplotlib').mkdir()
        environment = {**os.environ, 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                       'PF_NODE_BIN': str(node), 'PYPANDOC_PANDOC': str(pandoc),
                       'PF_HOST_MODE': 'provided', 'PF_PDF_ENGINE': pdf_engine, 'MPLCONFIGDIR': str(data / 'matplotlib')}
        if pdflatex is not None:
            environment['PF_PDFLATEX_BIN'] = str(pdflatex)
        else:
            environment.pop('PF_PDFLATEX_BIN', None)
        info = checked_json(run([str(python), '-c', 'import json,sys;print(json.dumps({"prefix":sys.prefix}))'], environment=environment))
        if Path(info['prefix']).resolve() != prefix.resolve():
            raise ValueError('Provided interpreter prefix changed')
        tools = [(node, 'node'), (pandoc, 'pandoc')]
        if pdflatex is not None:
            tools.append((pdflatex, 'pdflatex'))
        for binary, name in tools:
            check = run([str(binary), '--version'], environment=environment, timeout=15)
            report['steps'].append({'action': name + '-version', **check})
            if check['exit_code'] != 0:
                raise ValueError('A provided executable failed its actual version check')
            if name == 'node':
                match = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)\s*', check['stdout'])
                version = tuple(int(value) for value in match.groups()) if match else ()
                if not (version and (version[0] == 24 or version[0] == 22 and version >= (22, 16, 0))):
                    raise ValueError('Provided Node must be22.16.0+ on22.x or24.x; actual runner readiness remains required')
            elif name == 'pandoc' and not check['stdout'].startswith('pandoc '):
                raise ValueError('Provided Pandoc version identity is unavailable')
        finalize(data, python, prefix, node, pandoc, environment, report,
                 mode='provided', pdf_engine=pdf_engine, pdflatex=pdflatex)
    except Exception as error:
        report.update(ok=False, error={'code': 'HOST_PREPARATION_FAILED', 'exception': type(error).__name__,
                      'message': 'Provided host preparation failed. Retain this scratch and inspect actual installed modules, executable versions, inherited HTTP client readiness and native converter diagnostics. No download, install or fallback was attempted.'})
    return retained_result(data, report)


def prepare(data, *, mode='private', pdf_engine='typst', node=None, pandoc=None, pdflatex=None):
    if mode == 'provided':
        return prepare_provided(data, pdf_engine=pdf_engine, node=node, pandoc=pandoc, pdflatex=pdflatex)
    if mode != 'private' or pdf_engine != 'typst' or any(value is not None for value in (node, pandoc, pdflatex)):
        raise ValueError('Private preparation uses only its pinned Node, Pandoc and Typst profile')
    return prepare_private(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, type=Path)
    parser.add_argument('--mode', choices=('private', 'provided'), default='private')
    parser.add_argument('--pdf-engine', choices=('typst', 'pdflatex'), default='typst')
    parser.add_argument('--node', type=Path)
    parser.add_argument('--pandoc', type=Path)
    parser.add_argument('--pdflatex', type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.data, mode=args.mode, pdf_engine=args.pdf_engine, node=args.node, pandoc=args.pandoc, pdflatex=args.pdflatex)
        print(json.dumps({'ok': result['ok'], 'action': 'prepare-host', 'result': result}))
        sys.exit(0 if result['ok'] else 2)
    except Exception as error:
        print(json.dumps({'ok': False, 'action': 'prepare-host', 'error': {'code': 'HOST_PREPARATION_BLOCKED',
                          'exception': type(error).__name__, 'message': 'Host script access, a pinned CPython/platform profile, unchanged package bytes and approved empty scratch are required. No OS installer or execution fallback was used.'}}))
        sys.exit(2)
