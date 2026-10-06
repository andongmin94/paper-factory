import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs, { mkdtemp, mkdir, readFile, readdir, writeFile, link, symlink, rm } from 'node:fs/promises';
import { syncBuiltinESMExports } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { readVerifiedArtifact, saveArtifactWithDialog, validateSaveDestination, writeArtifactBundle, writeArtifactCopy } from '../dist/artifacts.js';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const rejected = error => error.code === 'SAVE_PATH_INVALID';
async function fixture(run) {
  const home = await mkdtemp(join(tmpdir(), 'paper-factory-artifact-test-'));
  const protectedRoot = join(home, 'app-data'); await mkdir(protectedRoot);
  try { await run({ home, protectedRoot }); } finally { await rm(home, { recursive: true, force: true }); }
}

test('artifact saving requires a bounded absolute path without control characters', () => {
  for (const value of [undefined, null, {}, '', '   ', 'paper.pdf', '../paper.pdf', '\0', join(tmpdir(), 'bad\nfile.pdf'),
    join(tmpdir(), 'bad\tfile.pdf'), join(tmpdir(), 'bad\x7ffile.pdf'), join(tmpdir(), 'x'.repeat(4097))]) {
    assert.throws(() => validateSaveDestination(value), rejected);
  }
  const valid = join(tmpdir(), 'explicit export - 실제 원고.pdf');
  assert.equal(validateSaveDestination(valid), valid);
});

test('artifact copies and explicit overwrites retain exact binary bytes and source hash', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const bytes = Buffer.concat([Buffer.from('\ufeffSYNTHETIC artifact\r\n'), Buffer.from(Array.from({ length: 256 }, (_, i) => i))]);
    const sourceHash = sha(bytes), source = join(protectedRoot, 'retained.bin'); await writeFile(source, bytes);
    const destination = join(home, 'export with spaces.bin');
    await writeArtifactCopy(bytes, destination, protectedRoot);
    assert.deepEqual(await readFile(destination), bytes); assert.equal(sha(await readFile(destination)), sourceHash);
    await writeFile(destination, 'old longer output that must be replaced and truncated');
    await writeArtifactCopy(bytes.subarray(0, 4), destination, protectedRoot);
    assert.deepEqual(await readFile(destination), bytes.subarray(0, 4));
    assert.equal(sha(bytes), sourceHash); assert.equal(sha(await readFile(source)), sourceHash);
  });
});

test('save destinations cannot overwrite retained app data or a parent alias to it', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const source = join(protectedRoot, 'raw.json'); const bytes = Buffer.from('IMMUTABLE SYNTHETIC RAW'); await writeFile(source, bytes);
    await assert.rejects(writeArtifactCopy(Buffer.from('changed'), source, protectedRoot), rejected);
    const alias = join(home, 'alias'); await symlink(protectedRoot, alias, process.platform === 'win32' ? 'junction' : 'dir');
    await assert.rejects(writeArtifactCopy(Buffer.from('changed'), join(alias, 'raw.json'), protectedRoot), rejected);
    assert.deepEqual(await readFile(source), bytes);
    const sibling = join(home, 'app-data-export'); await mkdir(sibling);
    await writeArtifactCopy(bytes, join(sibling, 'paper.md'), protectedRoot);
    assert.deepEqual(await readFile(join(sibling, 'paper.md')), bytes);
  });
});

test('directories and hard links are rejected before overwrite; original bytes survive', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const directory = join(home, 'folder.pdf'); await mkdir(directory);
    await assert.rejects(writeArtifactCopy(Buffer.from('changed'), directory, protectedRoot), rejected);
    const original = join(protectedRoot, 'raw.json'); const bytes = Buffer.from('IMMUTABLE RAW'); await writeFile(original, bytes);
    const alias = join(home, 'linked.md'); await link(original, alias);
    await assert.rejects(writeArtifactCopy(Buffer.from('changed'), alias, protectedRoot), rejected);
    assert.deepEqual(await readFile(original), bytes); assert.deepEqual(await readFile(alias), bytes);
  });
});

test('a missing destination directory fails without creating folders or changing retained files', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const source = join(protectedRoot, 'retained.bin'); const bytes = Buffer.from('UNCHANGED'); await writeFile(source, bytes);
    await assert.rejects(writeArtifactCopy(bytes, join(home, 'missing', 'paper.pdf'), protectedRoot), error => error.code === 'ENOENT');
    assert.deepEqual(await readFile(source), bytes);
    await writeArtifactCopy(bytes, join(home, 'retry.pdf'), protectedRoot);
    assert.deepEqual(await readFile(join(home, 'retry.pdf')), bytes);
  });
});

test('an atomic replacement failure preserves the existing file and removes its staging file', async t => {
  await fixture(async ({ home, protectedRoot }) => {
    const destination = join(home, 'paper.pdf'); const original = Buffer.from('ORIGINAL EXPORT');
    await writeFile(destination, original);
    const mock = t.mock.method(fs, 'rename', async (source, target) => {
      assert.equal(target, destination);
      assert.deepEqual(await readFile(source), Buffer.from('REPLACEMENT'));
      throw Object.assign(new Error('Synthetic commit failure'), { code: 'EACCES' });
    });
    syncBuiltinESMExports();
    try { await assert.rejects(writeArtifactCopy(Buffer.from('REPLACEMENT'), destination, protectedRoot), { code: 'EACCES' }); }
    finally { mock.mock.restore(); syncBuiltinESMExports(); }
    assert.deepEqual(await readFile(destination), original);
    assert.deepEqual((await readdir(home)).sort(), ['app-data', 'paper.pdf']);
  });
});

test('a manuscript bundle preserves exact manuscript and PNG bytes in one new folder', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const files = [{ name: 'manuscript.md', bytes: Buffer.from('![Measured result](figure-1.png)\r\n') },
      { name: 'figure-1.png', bytes: Buffer.from([137, 80, 78, 71, 0, 255, 13, 10]) }];
    const target = await writeArtifactBundle(files, home, 'Paper Factory-export', protectedRoot);
    assert.deepEqual((await readdir(target)).sort(), ['figure-1.png', 'manuscript.md']);
    for (const file of files) assert.deepEqual(await readFile(join(target, file.name)), file.bytes);
    await assert.rejects(writeArtifactBundle([{ name: 'manuscript.md', bytes: Buffer.from('changed') }], home, 'Paper Factory-export', protectedRoot), rejected);
    assert.deepEqual(await readFile(join(target, 'manuscript.md')), files[0].bytes);
    await assert.rejects(writeArtifactBundle(files, protectedRoot, 'export', protectedRoot), rejected);
    assert.deepEqual((await readdir(protectedRoot)), []);
  });
});

test('unsafe or duplicate bundle names never create partial export folders', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    for (const name of ['../raw.json', 'dir/file.png', '..', 'NUL.png', 'bad:stream.png', 'trailing.', 'trailing ']) {
      await assert.rejects(writeArtifactBundle([{ name, bytes: Buffer.from('fixture') }], home, 'export', protectedRoot), { code: 'ARTIFACT_INVALID' });
    }
    await assert.rejects(writeArtifactBundle([
      { name: 'Figure-1.png', bytes: Buffer.from('a') }, { name: 'figure-1.png', bytes: Buffer.from('b') },
    ], home, 'export', protectedRoot), { code: 'ARTIFACT_INVALID' });
    assert.deepEqual(await readdir(home), ['app-data']);
  });
});

test('a failed bundle commit removes all staged files without touching an earlier export', async t => {
  await fixture(async ({ home, protectedRoot }) => {
    const prior = join(home, 'previous'); await mkdir(prior); await writeFile(join(prior, 'manuscript.md'), 'PRIOR');
    const mock = t.mock.method(fs, 'rename', async source => {
      assert.deepEqual((await readdir(source)).sort(), ['figure-1.png', 'manuscript.tex']);
      throw Object.assign(new Error('Synthetic folder commit failure'), { code: 'EACCES' });
    });
    syncBuiltinESMExports();
    try { await assert.rejects(writeArtifactBundle([
      { name: 'manuscript.tex', bytes: Buffer.from('\\includegraphics{figure-1.png}') },
      { name: 'figure-1.png', bytes: Buffer.from('EXACT PNG') },
    ], home, 'new-export', protectedRoot), { code: 'EACCES' }); }
    finally { mock.mock.restore(); syncBuiltinESMExports(); }
    assert.deepEqual((await readdir(home)).sort(), ['app-data', 'previous']);
    assert.equal(await readFile(join(prior, 'manuscript.md'), 'utf8'), 'PRIOR');
  });
});

test('artifact resolution checks every source hash, companion name, and source directory', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const sourceDir = join(protectedRoot, 'exports'); await mkdir(sourceDir);
    const primary = Buffer.from('![Result](figure-1.png)'), png = Buffer.from('SYNTHETIC PNG');
    const primaryPath = join(sourceDir, 'manuscript.md'), figurePath = join(sourceDir, 'figure-1.png');
    await writeFile(primaryPath, primary); await writeFile(figurePath, png);
    const proof = { path: primaryPath, sha256: sha(primary), size: primary.length,
      companions: [{ name: 'figure-1.png', path: figurePath, sha256: sha(png), size: png.length }] };
    const verified = await readVerifiedArtifact(proof, protectedRoot);
    assert.deepEqual(verified.files, [{ name: 'manuscript.md', bytes: primary }, { name: 'figure-1.png', bytes: png }]);
    for (const change of [
      { companions: undefined }, { companions: [proof.companions[0], proof.companions[0]] },
      { companions: [{ ...proof.companions[0], name: '../figure-1.png' }] },
      { companions: [{ ...proof.companions[0], name: 'figure-2.png' }] },
      { size: primary.length + 1 }, { sha256: '0'.repeat(64) },
    ]) await assert.rejects(readVerifiedArtifact({ ...proof, ...change }, protectedRoot), error => ['ARTIFACT_INVALID', 'ARTIFACT_CHANGED'].includes(error.code));
    const outside = join(home, 'figure-1.png'); await writeFile(outside, png);
    await assert.rejects(readVerifiedArtifact({ ...proof, companions: [{ ...proof.companions[0], path: outside }] }, protectedRoot), { code: 'ARTIFACT_INVALID' });
    await writeFile(figurePath, 'TAMPERED');
    await assert.rejects(readVerifiedArtifact(proof, protectedRoot), { code: 'ARTIFACT_CHANGED' });
    assert.deepEqual(await readFile(primaryPath), primary);
  });
});

test('native single-file selection can cancel or atomically replace without accepting renderer paths', async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const bytes = Buffer.from('EXACT PDF BYTES'); const destination = join(home, 'selected.pdf');
    await writeFile(destination, 'PRIOR');
    const options = { artifact: { path: join(protectedRoot, 'manuscript.pdf'), files: [{ name: 'manuscript.pdf', bytes }] },
      artifactId: 'export-pdf', researchId: 'research-abcdef123456', documentsPath: home, protectedRoot,
      chooseDirectory: async () => { assert.fail('PDF must use a file dialog'); } };
    let calls = 0;
    assert.equal(await saveArtifactWithDialog({ ...options, chooseFile: async dialog => {
      calls++; assert.deepEqual(dialog.filters, [{ name: 'PDF 문서', extensions: ['pdf'] }]);
      assert.equal(dialog.defaultPath, join(home, 'manuscript.pdf'));
      return { canceled: true, filePath: destination };
    } }), false);
    assert.equal(await readFile(destination, 'utf8'), 'PRIOR');
    assert.equal(await saveArtifactWithDialog({ ...options, chooseFile: async () => {
      calls++; return { canceled: false, filePath: destination };
    } }), true);
    assert.equal(calls, 2); assert.deepEqual(await readFile(destination), bytes);
  });
});

for (const extension of ['md', 'tex']) test(`native ${extension} selection exports its manuscript and companions together and cancels cleanly`, async () => {
  await fixture(async ({ home, protectedRoot }) => {
    const files = [{ name: `manuscript.${extension}`, bytes: Buffer.from('UNCHANGED MANUSCRIPT') },
      { name: 'figure-1.png', bytes: Buffer.from('UNCHANGED PNG') }];
    const options = { artifact: { path: join(protectedRoot, files[0].name), files }, artifactId: `export-${extension}`,
      researchId: 'research-abcdef123456', documentsPath: home, protectedRoot,
      chooseFile: async () => { assert.fail('Manuscripts must use a folder dialog'); } };
    assert.equal(await saveArtifactWithDialog({ ...options, chooseDirectory: async () => ({ canceled: true, filePaths: [home] }) }), false);
    assert.deepEqual(await readdir(home), ['app-data']);
    assert.equal(await saveArtifactWithDialog({ ...options, chooseDirectory: async dialog => {
      assert.deepEqual(dialog.properties, ['openDirectory', 'dontAddToRecent']);
      return { canceled: false, filePaths: [home] };
    } }), true);
    const [folder] = (await readdir(home)).filter(name => name !== 'app-data');
    assert.match(folder, new RegExp(`^Paper Factory-abcdef123456-${extension}-[a-f0-9]{8}$`));
    for (const file of files) assert.deepEqual(await readFile(join(home, folder, file.name)), file.bytes);
  });
});
