import { lstat, open, realpath } from 'node:fs/promises';
import { basename, dirname, isAbsolute } from 'node:path';
import { EngineError } from './engine.js';

export type SupportingEvidenceFile = { name: string; contentBase64: string };

export async function readSupportingEvidence(paths: string[]): Promise<SupportingEvidenceFile[]> {
  const invalid = () => new EngineError('SUPPORTING_EVIDENCE_INVALID', '추가 근거는 안전한 이름의 일반 UTF-8 문서(.md·.txt·.json) 1–8개여야 합니다. 파일마다 128 KiB, 합계 256 KiB까지 선택하세요.');
  if (!Array.isArray(paths) || paths.length < 1 || paths.length > 8) throw invalid();
  const files: SupportingEvidenceFile[] = [];
  const names = new Set<string>();
  let total = 0;
  for (const path of paths) {
    if (typeof path !== 'string' || !isAbsolute(path)) throw invalid();
    const name = basename(path);
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.(md|txt|json)$/i.test(name) ||
        /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name) || names.has(name.toLowerCase())) throw invalid();
    try {
      const ordinaryParents = async () => {
        let parent = dirname(path);
        while (true) {
          const info = await lstat(parent);
          if (!info.isDirectory() || info.isSymbolicLink()) throw invalid();
          const next = dirname(parent);
          if (next === parent) break;
          parent = next;
        }
      };
      await ordinaryParents();
      const before = await lstat(path, { bigint: true });
      const canonical = await realpath(path);
      const samePath = (left: string, right: string) => process.platform === 'win32'
        ? left.toLowerCase() === right.toLowerCase() : left === right;
      if (!before.isFile() || before.isSymbolicLink() || before.nlink !== 1n || before.size > 128n * 1024n) throw invalid();
      const file = await open(path, 'r');
      let bytes: Buffer;
      try {
        const opened = await file.stat({ bigint: true });
        if (!opened.isFile() || opened.nlink !== 1n || opened.dev !== before.dev || opened.ino !== before.ino ||
            opened.size !== before.size || opened.mtimeNs !== before.mtimeNs) throw invalid();
        const buffer = Buffer.alloc(128 * 1024 + 1);
        let length = 0;
        while (length < buffer.length) {
          const { bytesRead } = await file.read(buffer, length, buffer.length - length, length);
          if (!bytesRead) break;
          length += bytesRead;
        }
        const after = await file.stat({ bigint: true });
        if (length === 0 || length > 128 * 1024 || BigInt(length) !== opened.size || after.size !== opened.size ||
            after.mtimeNs !== opened.mtimeNs || after.nlink !== 1n) throw invalid();
        bytes = buffer.subarray(0, length);
      } finally { await file.close(); }
      const after = await lstat(path, { bigint: true });
      await ordinaryParents();
      if (!after.isFile() || after.isSymbolicLink() || after.nlink !== 1n || after.dev !== before.dev ||
          after.ino !== before.ino || after.size !== before.size || after.mtimeNs !== before.mtimeNs ||
          !samePath(await realpath(path), canonical)) throw invalid();
      const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
      if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text)) throw invalid();
      total += bytes.length;
      if (total > 256 * 1024) throw invalid();
      names.add(name.toLowerCase());
      files.push({ name, contentBase64: bytes.toString('base64') });
    } catch { throw invalid(); }
  }
  return files;
}
