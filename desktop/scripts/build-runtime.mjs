import assert from 'node:assert/strict';
import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createReadStream, createWriteStream } from 'node:fs';
import { access, chmod, copyFile, cp, lstat, mkdir, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';
import { Readable } from 'node:stream';
import * as tar from 'tar';

// Maintainer build tool only. The desktop app neither imports this file nor downloads runtimes.
const desktop = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repository = resolve(desktop, '..');
const manifestPath = join(desktop, 'runtime-manifest.json');
const sha = (raw) => createHash('sha256').update(raw).digest('hex');
const manifestBytes = await readFile(manifestPath);
const manifest = JSON.parse(manifestBytes);
assert.equal(manifest.schemaVersion, 1);
const options = new Map();
for (let i = 2; i < process.argv.length; i += 2) {
  assert(['--platform', '--arch'].includes(process.argv[i]), 'Only --platform and --arch are supported');
  assert(process.argv[i + 1], 'Missing target option value');
  options.set(process.argv[i], process.argv[i + 1]);
}
const platform = options.get('--platform') ?? process.platform;
const arch = options.get('--arch') ?? process.arch;
const target = `${platform}-${arch}`;
const profile = manifest.profiles[target];
const nativeProfile = manifest.profiles[`${process.platform}-${process.arch}`];
assert(profile && nativeProfile, 'Build target and build host must be Windows x64 or macOS x64/arm64');
const workRoot = join(repository, '.paper-factory', 'standalone-runtime-builder');
const cache = join(workRoot, 'cache');
const attempt = join(workRoot, `build-${target}-${randomUUID()}`);
const staging = join(attempt, 'runtime');
const output = join(desktop, 'runtime', target);

async function ownedDirectory(path, parent) {
  const absolute = resolve(path);
  assert(absolute.startsWith(resolve(parent) + sep) && absolute !== resolve(parent), 'Builder path escapes its owned directory');
  for (let current = absolute; current !== dirname(current); current = dirname(current)) {
    try { assert(!(await lstat(current)).isSymbolicLink(), 'Linked builder path is forbidden'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  await mkdir(absolute, { recursive: true });
  return absolute;
}
await ownedDirectory(cache, join(repository, '.paper-factory'));
await ownedDirectory(attempt, workRoot);
await ownedDirectory(staging, attempt);
await ownedDirectory(dirname(output), desktop);

async function digest(path) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest('hex');
}
async function checkedFile(path, expected) {
  assert(!(await lstat(path)).isSymbolicLink() && (await stat(path)).isFile(), 'Runtime input must be an ordinary file');
  assert(/^[a-f0-9]{64}$/.test(expected.sha256), 'Missing reviewed SHA256');
  if (expected.size !== undefined) assert.equal((await stat(path)).size, expected.size, `Artifact size mismatch: ${expected.filename ?? path}`);
  assert.equal(await digest(path), expected.sha256, `Artifact SHA256 mismatch: ${expected.filename ?? path}`);
}
const hostPath = resolve(desktop, manifest.hostDependencies.path);
await checkedFile(hostPath, manifest.hostDependencies);
const host = JSON.parse(await readFile(hostPath));
const quickjsArchive = resolve(desktop, manifest.quickjs.archive);
const quickjsMetadata = resolve(desktop, manifest.quickjs.metadata);
await checkedFile(quickjsArchive, manifest.quickjs);
await checkedFile(quickjsMetadata, { sha256: manifest.quickjs.metadataSha256 });

const origins = new Set(['github.com', 'raw.githubusercontent.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', 'nodejs.org', 'files.pythonhosted.org']);
async function artifact(record) {
  assert(record.filename && !/[\\/]/.test(record.filename), 'Invalid artifact filename');
  const destination = join(cache, `${record.sha256}-${record.filename}`);
  try { await checkedFile(destination, record); return destination; }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  let url = new URL(record.url);
  let response;
  for (let redirects = 0; redirects <= 5; redirects += 1) {
    assert(url.protocol === 'https:' && origins.has(url.hostname) && !url.username && !url.password, 'Unreviewed artifact origin');
    response = await fetch(url, { redirect: 'manual', signal: AbortSignal.timeout(120_000), headers: { 'user-agent': 'Paper-Factory-runtime-build' } });
    if (response.status >= 300 && response.status < 400 && response.headers.has('location')) {
      url = new URL(response.headers.get('location'), url);
      await response.body?.cancel();
      continue;
    }
    break;
  }
  assert(response?.ok && response.body, `Artifact download failed: ${record.filename}, HTTP ${response?.status}`);
  const maximum = record.size ?? record.max_bytes ?? 128 * 1024 * 1024;
  let downloaded = 0;
  async function* bounded() {
    for await (const chunk of Readable.fromWeb(response.body)) {
      downloaded += chunk.length;
      assert(downloaded <= maximum, `Artifact exceeds reviewed size: ${record.filename}`);
      yield chunk;
    }
  }
  const temporary = join(attempt, `${randomUUID()}.download`);
  await pipeline(bounded(), createWriteStream(temporary, { flags: 'wx' }));
  await checkedFile(temporary, record);
  await rename(temporary, destination);
  console.log(`Verified ${record.filename}`);
  return destination;
}

function archiveName(name) {
  assert(typeof name === 'string' && !isAbsolute(name) && !/[\\:\0]/.test(name), 'Unsafe archive member');
  const parts = name.replace(/\/$/, '').split('/');
  assert(parts.every((part) => part && part !== '.' && part !== '..'), 'Archive member escapes root');
  return parts;
}
async function extractBootstrap(archive, destination) {
  await ownedDirectory(destination, attempt);
  let bytes = 0;
  const entries = new Set();
  await tar.t({ file: archive, strict: true, onReadEntry(entry) {
    const parts = archiveName(entry.path);
    assert.equal(parts[0], 'python');
    assert(!entries.has(entry.path), 'Duplicate archive member');
    entries.add(entry.path);
    assert(['Directory', 'File', 'SymbolicLink'].includes(entry.type), 'Unexpected Python archive member type');
    bytes += entry.size;
    assert(bytes < 768 * 1024 * 1024, 'Python extraction byte boundary exceeded');
    if (entry.type === 'SymbolicLink') {
      const link = resolve(destination, dirname(entry.path), entry.linkpath);
      assert(!isAbsolute(entry.linkpath) && link.startsWith(join(destination, 'python') + sep), 'Python archive link escapes root');
    }
  } });
  await tar.x({ file: archive, cwd: destination, strict: true, preservePaths: false, noMtime: true });
}

async function run(executable, args, environment, label, timeout = 180_000) {
  const result = await new Promise((resolveResult, reject) => {
    const child = spawn(executable, args, { cwd: attempt, env: environment, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error(`${label} timed out`)); }, timeout);
    child.on('error', (error) => { clearTimeout(timer); reject(error); });
    for (const [stream, append] of [[child.stdout, (part) => { stdout += part; }], [child.stderr, (part) => { stderr += part; }]]) {
      stream.setEncoding('utf8');
      stream.on('data', (part) => { append(part); if (stdout.length + stderr.length > 8 * 1024 * 1024) { child.kill(); reject(new Error(`${label} output exceeded boundary`)); } });
    }
    child.on('close', (code) => { clearTimeout(timer); resolveResult({ code, stdout, stderr }); });
  });
  await writeFile(join(attempt, `${label}.log`), result.stdout + result.stderr);
  assert.equal(result.code, 0, `${label} failed; preserved log: ${join(attempt, `${label}.log`)}\n${result.stderr.slice(-2500)}`);
  return result;
}
const environment = { ...process.env, PYTHONNOUSERSITE: '1', PYTHONDONTWRITEBYTECODE: '1', PIP_CONFIG_FILE: process.platform === 'win32' ? 'NUL' : '/dev/null' };
delete environment.PYTHONPATH;
delete environment.PYTHONHOME;
const bootstrapArchive = await artifact(nativeProfile.python);
await extractBootstrap(bootstrapArchive, join(attempt, 'bootstrap'));
const bootstrap = join(attempt, 'bootstrap', nativeProfile.paths.python);
const bootstrapIdentity = await run(bootstrap, ['-I', '-B', '-c', 'import sys,json;print(json.dumps({"version":sys.version.split()[0],"prefix":sys.prefix}))'], environment, 'bootstrap-identity');
assert.equal(JSON.parse(bootstrapIdentity.stdout).version, manifest.pythonVersion);

const helper = join(attempt, 'assemble.py');
await writeFile(helper, String.raw`
import hashlib, json, os, shutil, stat, sys, tarfile, zipfile
from pathlib import Path, PurePosixPath

def name(value):
    parts = value.rstrip('/').split('/')
    if not value or PurePosixPath(value).is_absolute() or chr(92) in value or ':' in value or chr(0) in value or any(p in ('', '.', '..') for p in parts):
        raise ValueError('Unsafe archive path')
    return parts

def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=False)
    names, total = set(), 0
    if str(archive).endswith('.zip'):
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if bundle.testzip(): raise ValueError('Archive CRC failure')
            for entry in entries:
                parts = name(entry.filename)
                key = entry.filename.casefold()
                if key in names or stat.S_ISLNK(entry.external_attr >> 16): raise ValueError('Duplicate or linked ZIP entry')
                names.add(key)
                total += entry.file_size
                if total > 768 * 1024 * 1024: raise ValueError('Archive byte boundary exceeded')
            bundle.extractall(destination)
    else:
        with tarfile.open(archive, 'r:*') as bundle:
            for entry in bundle.getmembers():
                parts = name(entry.name)
                if entry.name in names or not (entry.isfile() or entry.isdir() or entry.issym() or entry.islnk()):
                    raise ValueError('Invalid TAR entry')
                names.add(entry.name)
                total += entry.size
                if total > 768 * 1024 * 1024: raise ValueError('Archive byte boundary exceeded')
                if entry.issym() or entry.islnk():
                    link = (destination / (Path(entry.name).parent if entry.issym() else Path()) / entry.linkname).resolve()
                    if Path(entry.linkname).is_absolute() or not link.is_relative_to(destination.resolve()):
                        raise ValueError('Archive link escapes root')
            bundle.extractall(destination, filter='data')
    # The distributable payload uses ordinary files, including Python executable aliases.
    for entry in sorted(destination.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if entry.is_symlink():
            source = entry.resolve(strict=True)
            if not source.is_relative_to(destination.resolve()) or not source.is_file(): raise ValueError('Unsafe extracted link')
            entry.unlink()
            shutil.copy2(source, entry)
        elif entry.is_file() and entry.stat().st_nlink != 1:
            materialized = entry.with_name(entry.name + '.paper-factory-copy')
            if materialized.exists(): raise ValueError('Archive materialization collision')
            shutil.copy2(entry, materialized)
            os.replace(materialized, entry)

if sys.argv[1] == 'unpack':
    unpack(Path(sys.argv[2]), Path(sys.argv[3]))
elif sys.argv[1] == 'member':
    archive, output, member = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
    name(member)
    with zipfile.ZipFile(archive) as bundle:
        matches = [entry for entry in bundle.infolist() if entry.filename == member]
        assert len(matches) == 1
        entry = matches[0]
        assert not entry.is_dir() and not stat.S_ISLNK(entry.external_attr >> 16) and entry.file_size <= 256 * 1024 * 1024
        with bundle.open(entry) as source, output.open('xb') as destination:
            shutil.copyfileobj(source, destination)
        output.chmod(0o755)
elif sys.argv[1] == 'quickjs':
    archive, destination, metadata = Path(sys.argv[2]), Path(sys.argv[3]), json.loads(Path(sys.argv[4]).read_bytes())
    with zipfile.ZipFile(archive) as bundle:
        inventory = bundle.read('quickjs-runtime/inventory.json')
        assert hashlib.sha256(inventory).hexdigest() == metadata['inventory_sha256']
        files = json.loads(inventory)['files']
        assert set(bundle.namelist()) == {'quickjs-runtime/inventory.json', *('quickjs-runtime/' + p for p in files)}
        for path, record in files.items():
            name(path)
            data = bundle.read('quickjs-runtime/' + path)
            assert len(data) == record['size'] and hashlib.sha256(data).hexdigest() == record['sha256']
    unpack(archive, destination)
else:
    raise ValueError('Unknown assembly operation')
`);
const unpack = async (archive, destination, label) => run(bootstrap, ['-I', '-B', helper, 'unpack', archive, destination], environment, label);
const targetArchive = await artifact(profile.python);
await unpack(targetArchive, join(attempt, 'python-extracted'), 'python-extract');
await rename(join(attempt, 'python-extracted', 'python'), join(staging, 'python'));

const wheelRecords = host.profiles[profile.hostProfile].wheels.map((filename) => host.wheels[filename]);
const wheelDirectory = join(attempt, 'wheels');
await mkdir(wheelDirectory);
for (let i = 0; i < wheelRecords.length; i += 4) {
  await Promise.all(wheelRecords.slice(i, i + 4).map(async (record) => {
    const source = await artifact(record);
    await copyFile(source, join(wheelDirectory, record.filename));
  }));
}
const lock = join(attempt, 'dependencies.lock');
await writeFile(lock, wheelRecords.map((record) => `${record.name}==${record.version} --hash=sha256:${record.sha256}`).join('\n') + '\n');
const sitePackages = join(staging, profile.paths.sitePackages);
const wheelPlatforms = [...new Set(wheelRecords.flatMap((record) => record.filename.slice(0, -4).split('-').at(-1).split('.')).filter((name) => name !== 'any'))];
const install = await run(bootstrap, ['-I', '-B', '-m', 'pip', '--isolated', 'install', '--no-index', '--no-input', '--no-cache-dir', '--disable-pip-version-check',
  '--no-compile', '--no-deps', '--only-binary=:all:', '--require-hashes', '--find-links', wheelDirectory, '--target', sitePackages,
  '--implementation', 'cp', '--abi', 'cp314', '--python-version', '3.14', ...wheelPlatforms.flatMap((name) => ['--platform', name]), '-r', lock], environment, 'wheel-install');
console.log(`Installed ${wheelRecords.length} pinned runtime wheels without index access`);
// --target generates host-specific console launchers; the app invokes explicit modules only.
for (const name of ['bin', 'Scripts']) {
  const launchers = resolve(sitePackages, name);
  assert(launchers.startsWith(resolve(staging) + sep) && launchers.startsWith(resolve(sitePackages) + sep), 'Console launcher cleanup escapes staging');
  try { assert((await lstat(launchers)).isDirectory() && !(await lstat(launchers)).isSymbolicLink(), 'Unexpected console launcher path'); }
  catch (error) { if (error.code === 'ENOENT') continue; throw error; }
  await rm(launchers, { recursive: true });
}
// pip belongs to the maintainer bootstrap, not the installed application's interpreter.
for (const entry of await readdir(sitePackages, { withFileTypes: true })) {
  if (entry.name !== 'pip' && !/^pip-[0-9][A-Za-z0-9.+_-]*\.dist-info$/.test(entry.name)) continue;
  const tool = resolve(sitePackages, entry.name);
  assert(tool.startsWith(resolve(staging) + sep) && tool.startsWith(resolve(sitePackages) + sep), 'Build tool cleanup escapes staging');
  assert(entry.isDirectory() && !(await lstat(tool)).isSymbolicLink(), 'Unexpected pip build tool path');
  await rm(tool, { recursive: true });
}
const interpreterLaunchers = resolve(staging, 'python', platform === 'win32' ? 'Scripts' : 'bin');
for (const entry of await readdir(interpreterLaunchers, { withFileTypes: true })) {
  if (!/^pip(?:3(?:\.14)?)?(?:\.exe)?$/.test(entry.name)) continue;
  const launcher = resolve(interpreterLaunchers, entry.name);
  assert(launcher.startsWith(resolve(staging) + sep) && launcher.startsWith(interpreterLaunchers + sep), 'pip launcher cleanup escapes staging');
  assert(entry.isFile() && !(await lstat(launcher)).isSymbolicLink(), 'Unexpected pip launcher path');
  await rm(launcher);
}

const nodeRecord = host.node[profile.hostFamily];
const nodeArchive = await artifact(nodeRecord);
const nodeArchiveRoot = nodeRecord.filename.replace(/\.(?:zip|tar\.xz)$/, '');
const nodeDestination = join(staging, profile.paths.node);
await mkdir(dirname(nodeDestination), { recursive: true });
await mkdir(join(staging, 'licenses', 'node'), { recursive: true });
const nodeLicense = join(staging, 'licenses', 'node', 'LICENSE');
if (platform === 'win32') {
  // The app needs no npm tree; its nested paths exceed Windows extraction limits.
  await run(bootstrap, ['-I', '-B', helper, 'member', nodeArchive, nodeDestination, `${nodeArchiveRoot}/node.exe`], environment, 'node-extract');
  await run(bootstrap, ['-I', '-B', helper, 'member', nodeArchive, nodeLicense, `${nodeArchiveRoot}/LICENSE`], environment, 'node-license-extract');
} else {
  const nodeExtracted = join(attempt, 'node-extracted');
  await unpack(nodeArchive, nodeExtracted, 'node-extract');
  const nodeRoot = join(nodeExtracted, nodeArchiveRoot);
  await copyFile(join(nodeRoot, 'bin/node'), nodeDestination);
  await copyFile(join(nodeRoot, 'LICENSE'), nodeLicense);
}
if (platform !== 'win32') {
  const pandocRecord = host.pandoc[profile.hostFamily];
  const pandocArchive = await artifact(pandocRecord);
  const binary = join(attempt, 'pandoc-binary');
  // Upstream archives also contain command aliases. Only the reviewed regular executable is packaged.
  await run(bootstrap, ['-I', '-B', helper, 'member', pandocArchive, binary, pandocRecord.binary.member], environment, 'pandoc-extract');
  await checkedFile(binary, pandocRecord.binary);
  await mkdir(join(staging, 'pandoc'));
  await copyFile(binary, join(staging, profile.paths.pandoc));
}
if (platform === 'darwin') {
  for (const executable of [profile.paths.python, profile.paths.node, profile.paths.pandoc]) {
    const path = join(staging, executable);
    assert((await lstat(path)).isFile() && !(await lstat(path)).isSymbolicLink() && (await stat(path)).nlink === 1, 'Executable must be a materialized ordinary file');
    await chmod(path, 0o755);
  }
}
await run(bootstrap, ['-I', '-B', helper, 'quickjs', quickjsArchive, join(attempt, 'quickjs-extracted'), quickjsMetadata], environment, 'quickjs-extract');
await cp(join(attempt, 'quickjs-extracted', 'quickjs-runtime'), join(staging, 'quickjs-runtime'),
  { recursive: true, errorOnExist: true, force: false });

const enginePackage = join(sitePackages, 'paper_factory');
await cp(join(repository, 'src', 'paper_factory'), enginePackage, { recursive: true, filter: (source) => !source.split(sep).some((name) => name === '__pycache__') && !/\.py[co]$/.test(source) });
await cp(join(sitePackages, manifest.fontSource), join(staging, 'fonts'), { recursive: true });
const licenseRows = [];
async function collectLicenses(root, prefix) {
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) { await collectLicenses(path, prefix); continue; }
    const noticePath = relative(prefix, path).replaceAll('\\', '/');
    if (!entry.isFile() || !/(?:^|[\/_.-])(license|licence|copying|copyright|notice|ofl|authors)(?:[\/_.-]|$)/i.test(noticePath)) continue;
    const source = relative(staging, path).replaceAll('\\', '/');
    const stored = `licenses/upstream/${source}`;
    const destination = join(staging, stored);
    await mkdir(dirname(destination), { recursive: true });
    await copyFile(path, destination);
    licenseRows.push({ source, path: stored, size: (await stat(path)).size, sha256: await digest(path) });
  }
}
await collectLicenses(join(staging, 'python'), join(staging, 'python'));
await collectLicenses(join(staging, 'quickjs-runtime'), join(staging, 'quickjs-runtime'));
await mkdir(join(staging, 'licenses', 'python-build-standalone'));
for (let i = 0; i < manifest.pythonLicenses.length; i += 4) {
  await Promise.all(manifest.pythonLicenses.slice(i, i + 4).map(async (record) => {
    const original = await artifact(record);
    await copyFile(original, join(staging, 'licenses', 'python-build-standalone', record.filename));
  }));
}
for (const name of ['COPYING.md', 'COPYRIGHT']) {
  const path = join(desktop, 'runtime-inputs', 'licenses', 'pandoc', name);
  const record = host.pandoc['macos-x86_64'].licenses[`licenses/pandoc/${name}`];
  await checkedFile(path, record);
  await mkdir(join(staging, 'licenses', 'pandoc'), { recursive: true });
  await copyFile(path, join(staging, 'licenses', 'pandoc', name));
}
await mkdir(join(staging, 'licenses', 'paper-factory'));
await copyFile(join(repository, 'LICENSE'), join(staging, 'licenses', 'paper-factory', 'LICENSE'));
await copyFile(join(desktop, 'third-party', 'runtime-NOTICES.md'), join(staging, 'licenses', 'runtime-NOTICES.md'));
await writeFile(join(staging, 'licenses', 'license-inventory.json'), JSON.stringify({ schemaVersion: 1, preservedOriginalNotices: licenseRows, pythonBuildStandaloneNotices: manifest.pythonLicenses, wheelArtifacts: wheelRecords.map(({ name, version, filename, url, sha256, license }) => ({ name, version, filename, url, sha256, license })) }, null, 2) + '\n');

const isNative = platform === process.platform && arch === process.arch;
let probe = { actualHostTested: false, reason: 'Foreign platform payload assembled; native execution is required on the matching host.' };
if (isNative) {
  const probeDirectory = join(attempt, 'probe');
  await mkdir(probeDirectory);
  const probeEnvironment = { ...environment, PATH: '', PF_NODE_BIN: join(staging, profile.paths.node), PYPANDOC_PANDOC: join(staging, profile.paths.pandoc),
    TYPST_FONT_PATHS: join(staging, 'fonts'), TEMP: probeDirectory, TMP: probeDirectory, TMPDIR: probeDirectory };
  const probeScript = join(attempt, 'probe.py');
  await writeFile(probeScript, String.raw`
import hashlib, importlib, importlib.metadata, importlib.util, json, pathlib, sys
modules = ['ssl', 'sqlite3', 'lzma', 'pydantic', 'pydantic_core', 'httpx', 'bs4', 'pypdf', 'docx', 'lxml', 'typst', 'paper_factory.workflow', 'paper_factory.ipc']
root, scratch = map(pathlib.Path, sys.argv[1:3])
for module in modules:
    imported = importlib.import_module(module)
    if getattr(imported, '__file__', None):
        assert pathlib.Path(imported.__file__).resolve().is_relative_to(root / 'python'), module
assert pathlib.Path(sys.prefix).resolve() == (root / 'python').resolve()
assert sys.flags.isolated and sys.flags.dont_write_bytecode
assert importlib.util.find_spec('pip') is None, 'Build-only pip leaked into application runtime'
assert not any(d.metadata['Name'].lower() == 'pip' for d in importlib.metadata.distributions()), 'Build-only pip metadata leaked into application runtime'
from paper_factory.autonomous.quickjs_runner import QuickJSRunner
runner = QuickJSRunner(root / 'quickjs-runtime', supervisor_root=scratch / 'quickjs-supervisor')
runtime = runner.status()
assert runtime['ready'] and runtime['backend'] == 'quickjs-wasm' and runtime['runtimes'] == ['quickjs'] and runtime['cleanup_confirmed'], runtime
source = scratch / 'probe.md'
source.write_text('# Bundled runtime probe\n\nTrusted runtime diagnostic only.\n\n한국어 글꼴 검증을 진행합니다.\n\n| Fixture | Count |\n| --- | ---: |\n| Probe | 1 |\n', encoding='utf-8')
from paper_factory.conversion import convert
outputs = {}
for extension in ('pdf', 'docx', 'tex'):
    output = scratch / ('probe.' + extension)
    receipt = convert(source, output)
    raw = output.read_bytes()
    outputs[extension] = {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'receipt': receipt}
from pypdf import PdfReader
from docx import Document
pdf = PdfReader(scratch / 'probe.pdf', strict=True)
assert len(pdf.pages) == 1 and 'Trusted runtime diagnostic only.' in pdf.pages[0].extract_text()
assert '한국어 글꼴 검증을 진행합니다.' in pdf.pages[0].extract_text()
document = Document(scratch / 'probe.docx')
assert not document.inline_shapes and len(document.tables) == 1
assert any('Trusted runtime diagnostic only.' in p.text for p in document.paragraphs)
assert 'Trusted runtime diagnostic only.' in (scratch / 'probe.tex').read_text(encoding='utf-8')
print(json.dumps({'actualHostTested': True, 'python': sys.version.split()[0], 'isolated': bool(sys.flags.isolated), 'pipExcluded': True, 'imports': modules, 'quickjs': runtime, 'converters': outputs, 'pdfPages': len(pdf.pages), 'researchPaper': False, 'distributions': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}}))
`);
  const pythonProbe = await run(join(staging, profile.paths.python), ['-I', '-B', probeScript, staging, probeDirectory], probeEnvironment, 'runtime-probe');
  probe = JSON.parse(pythonProbe.stdout);
  probe.node = (await run(join(staging, profile.paths.node), ['--version'], probeEnvironment, 'node-probe')).stdout.trim();
  probe.pandoc = (await run(join(staging, profile.paths.pandoc), ['--version'], probeEnvironment, 'pandoc-probe')).stdout.split(/\r?\n/)[0];
  assert.equal(probe.node, `v${nodeRecord.version}`);
  assert.equal(probe.python, manifest.pythonVersion);
}
await writeFile(join(attempt, 'probe-receipt.json'), JSON.stringify(probe, null, 2) + '\n');
const files = [];
async function inventory(root) {
  for (const entry of (await readdir(root, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
    const path = join(root, entry.name);
    assert(!entry.isSymbolicLink(), 'Distributable runtime must contain no symbolic links');
    if (entry.isDirectory()) await inventory(path);
    else {
      assert(entry.isFile(), 'Unexpected runtime file type');
      files.push({ path: relative(staging, path).replaceAll('\\', '/'), size: (await stat(path)).size, sha256: await digest(path) });
    }
  }
}
await inventory(staging);
const inventoryData = { schemaVersion: 1, platform, arch, executables: { python: profile.paths.python, node: profile.paths.node, pandoc: profile.paths.pandoc },
  paths: { quickjs: profile.paths.quickjs, fonts: profile.paths.fonts, sitePackages: profile.paths.sitePackages },
  sourceManifestSha256: sha(manifestBytes), engineModule: manifest.engineModule, actualHostTested: isNative, files };
const inventoryBytes = Buffer.from(JSON.stringify(inventoryData, null, 2) + '\n');
await writeFile(join(staging, 'runtime-inventory.json'), inventoryBytes);
try { await access(output); await rename(output, join(attempt, 'previous-runtime')); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
await rename(staging, output);
const bindingPath = join(desktop, 'third-party', 'runtime-inventory-binding.json');
let binding = { schemaVersion: 1, profiles: {} };
try { binding = JSON.parse(await readFile(bindingPath)); assert.equal(binding.schemaVersion, 1); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
binding.profiles[target] = { inventorySha256: sha(inventoryBytes), sourceManifestSha256: sha(manifestBytes), executables: inventoryData.executables, fileCount: files.length, actualHostTested: isNative };
await writeFile(bindingPath, JSON.stringify(binding, null, 2) + '\n');
const receipt = { schemaVersion: 1, builtAt: new Date().toISOString(), target, output, sourceManifestSha256: sha(manifestBytes), inventorySha256: sha(inventoryBytes),
  fileCount: files.length, payloadBytes: files.reduce((sum, file) => sum + file.size, 0), dependencies: wheelRecords.map(({ name, version, sha256 }) => ({ name, version, sha256 })),
  pythonArchive: profile.python, nodeArchive: nodeRecord, quickjsArchiveSha256: manifest.quickjs.sha256, actualHostTested: isNative, probeReceipt: join(attempt, 'probe-receipt.json'),
  applicationLaunchTested: false, macOSInstallationTested: false, noRuntimeDownloads: true };
await writeFile(join(attempt, 'build-receipt.json'), JSON.stringify(receipt, null, 2) + '\n');
console.log(JSON.stringify({ target, output, inventorySha256: receipt.inventorySha256, fileCount: files.length, payloadBytes: receipt.payloadBytes, actualHostTested: isNative, receipt: join(attempt, 'build-receipt.json') }, null, 2));
