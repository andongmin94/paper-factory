import { createHash } from 'node:crypto';
import { lstat, open, readFile, realpath } from 'node:fs/promises';
import { basename, dirname, isAbsolute, join, relative, sep } from 'node:path';
import { EngineError } from './engine.js';

export function validateSaveDestination(value: unknown): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 4096 || /[\u0000-\u001f\u007f]/.test(value) || !isAbsolute(value)) {
    throw new EngineError('SAVE_PATH_INVALID', '저장할 파일의 절대 경로를 입력하세요. 경로는 4096자 이내여야 합니다.');
  }
  return value;
}

export async function writeArtifactCopy(bytes: Buffer, destinationPath: string, protectedRoot: string): Promise<void> {
  const destination = validateSaveDestination(destinationPath);
  // An explicit export destination must not overwrite the app's authentication or frozen research data.
  const parent = await realpath(dirname(destination));
  const protectedPath = await realpath(protectedRoot);
  const target = join(parent, basename(destination));
  const rel = relative(protectedPath, target);
  if (rel === '' || (rel !== '..' && !rel.startsWith('..' + sep) && !isAbsolute(rel))) {
    throw new EngineError('SAVE_PATH_INVALID', '앱 데이터 폴더 밖의 저장 경로를 선택하세요.');
  }
  try {
    const info = await lstat(target);
    if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1) throw new EngineError('SAVE_PATH_INVALID', '일반 파일의 저장 경로를 선택하세요.');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
  const file = await open(target, 'w');
  try { await file.writeFile(bytes); await file.sync(); } finally { await file.close(); }
  if (createHash('sha256').update(await readFile(target)).digest('hex') !== createHash('sha256').update(bytes).digest('hex')) {
    throw new EngineError('SAVED_ARTIFACT_CHANGED', '저장한 파일의 무결성을 확인할 수 없습니다.');
  }
}
