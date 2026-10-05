import assert from 'node:assert/strict';
import { mkdtemp, writeFile, mkdir, link, symlink, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import test from 'node:test';
import { readSupportingEvidence } from '../dist/research.js';

async function fixture(run) {
  const home = await mkdtemp(join(tmpdir(), 'paper-factory-supporting-test-'));
  const file = async (name, bytes) => { const path = join(home, name); await writeFile(path, bytes); return path; };
  try { await run({ home, file }); } finally { await rm(home, { recursive: true, force: true }); }
}
const rejected = error => error.code === 'SUPPORTING_EVIDENCE_INVALID' && !/[A-Za-z]:[\\/]|paper-factory-supporting-test-/.test(error.message);

test('native supporting-file validation preserves exact UTF-8, BOM and newline bytes without exposing paths', async () => {
  await fixture(async ({ file }) => {
    const bytes = Buffer.from('\ufeff# 실제 원문\r\nSources and dates are user claims.\n');
    const input = await file('Official-spec.MD', bytes);
    const result = await readSupportingEvidence([input]);
    assert.deepEqual(result, [{ name: 'Official-spec.MD', contentBase64: bytes.toString('base64') }]);
    assert.deepEqual(Buffer.from(result[0].contentBase64, 'base64'), bytes);
    assert.equal(JSON.stringify(result).includes(input), false);
  });
});

test('file-count, per-file and total-byte limits are enforced before import', async () => {
  await fixture(async ({ file }) => {
    await assert.rejects(readSupportingEvidence([]), rejected);
    const small = await file('small.txt', 'x');
    await assert.rejects(readSupportingEvidence(Array(9).fill(small)), rejected);
    const exact = await file('exact.md', Buffer.alloc(128 * 1024, 120));
    const second = await file('second.json', Buffer.alloc(128 * 1024, 120));
    assert.equal((await readSupportingEvidence([exact, second])).length, 2);
    const oversized = await file('oversized.txt', Buffer.alloc(128 * 1024 + 1, 120));
    await assert.rejects(readSupportingEvidence([oversized]), rejected);
    await assert.rejects(readSupportingEvidence([exact, second, small]), rejected);
  });
});

test('unsafe names, duplicate basenames, empty/binary text and malformed UTF-8 cannot become supporting evidence', async () => {
  await fixture(async ({ file, home }) => {
    for (const [name, contents] of [
      ['bad.exe', 'text'], ['unsafe name.md', 'text'],
      ['empty.txt', ''], ['binary.json', Buffer.from([0])], ['control.txt', Buffer.from([0x7f])],
      ['invalid.md', Buffer.from([0xc3, 0x28])],
    ]) await assert.rejects(readSupportingEvidence([await file(name, contents)]), rejected);
    await assert.rejects(readSupportingEvidence([join(home, 'CON.txt')]), rejected);
    const first = await file('duplicate.txt', 'original');
    const directory = join(home, 'nested'); await mkdir(directory);
    const second = join(directory, 'duplicate.txt'); await writeFile(second, 'different');
    await assert.rejects(readSupportingEvidence([first, second]), rejected);
    await assert.rejects(readSupportingEvidence(['relative.md']), rejected);
  });
});

test('directories and multiply-linked files are rejected as native supporting documents', async () => {
  await fixture(async ({ file, home }) => {
    const directory = join(home, 'folder.md'); await mkdir(directory);
    await assert.rejects(readSupportingEvidence([directory]), rejected);
    const original = await file('original.txt', 'fixture');
    const linked = join(home, 'linked.txt'); await link(original, linked);
    await assert.rejects(readSupportingEvidence([original]), rejected);
    await assert.rejects(readSupportingEvidence([linked]), rejected);
  });
});

test('directory symbolic links cannot redirect a selected ordinary file', async () => {
  await fixture(async ({ file, home }) => {
    await file('original.txt', 'fixture');
    const redirect = join(home, 'redirect');
    await symlink(home, redirect, process.platform === 'win32' ? 'junction' : 'dir');
    await assert.rejects(readSupportingEvidence([join(redirect, 'original.txt')]), rejected);
  });
});
