import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, writeFile, link, symlink, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { validateSaveDestination, writeArtifactCopy } from '../dist/artifacts.js';

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
