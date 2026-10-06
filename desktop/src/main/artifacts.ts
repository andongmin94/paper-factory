import { createHash, randomUUID } from 'node:crypto';
import { lstat, mkdir, open, readFile, realpath, rename, rm, unlink } from 'node:fs/promises';
import { basename, dirname, isAbsolute, join, relative, sep } from 'node:path';
import { EngineError } from './engine.js';
import type { OpenDialogOptions, OpenDialogReturnValue, SaveDialogOptions, SaveDialogReturnValue } from 'electron';

export const artifactFormats: Record<string, { name: string; extension: string }> = {
  'export-pdf': { name: 'PDF 문서', extension: 'pdf' }, 'export-docx': { name: 'Word 문서', extension: 'docx' },
  'export-md': { name: 'Markdown 원고와 그림', extension: 'md' }, 'export-tex': { name: 'TeX 원고와 그림', extension: 'tex' },
  reproducibility: { name: '재현 패키지', extension: 'zip' }, validation: { name: '검증 결과', extension: 'json' },
};

export function validateSaveDestination(value: unknown): string {
  if (typeof value !== 'string' || !value.trim() || value.length > 4096 || /[\u0000-\u001f\u007f]/.test(value) || !isAbsolute(value)) {
    throw new EngineError('SAVE_PATH_INVALID', '다른 저장 위치를 선택하세요.');
  }
  return value;
}

export interface ArtifactFile { path: string; sha256: string; size: number }
export interface ResolvedArtifact extends ArtifactFile { companions: Array<ArtifactFile & { name: string }> }
export interface ArtifactCopy { name: string; bytes: Buffer }
export interface VerifiedArtifact { path: string; files: ArtifactCopy[] }

const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

function validateFileName(name: string): void {
  if (typeof name !== 'string' || !name || name.length > 200 || /[<>:"/\\|?*\u0000-\u001f\u007f]/.test(name) ||
    /[. ]$/.test(name) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name)) {
    throw new EngineError('ARTIFACT_INVALID', '결과 파일 이름을 확인할 수 없습니다.');
  }
}

export async function readVerifiedArtifact(artifact: ResolvedArtifact, engineHome: string): Promise<VerifiedArtifact> {
  const base = await realpath(engineHome);
  const read = async (file: ArtifactFile) => {
    if (!file || typeof file.path !== 'string' || !isAbsolute(file.path) || !/^[a-f0-9]{64}$/.test(file.sha256) ||
      !Number.isSafeInteger(file.size) || file.size < 0) throw new EngineError('ARTIFACT_INVALID', '결과 파일 정보를 확인할 수 없습니다.');
    const info = await lstat(file.path);
    if (!info.isFile() || info.isSymbolicLink()) throw new EngineError('ARTIFACT_INVALID', '결과 파일 경로를 확인할 수 없습니다.');
    const path = await realpath(file.path);
    const rel = relative(base, path);
    if (rel === '' || rel === '..' || rel.startsWith('..' + sep) || isAbsolute(rel)) throw new EngineError('ARTIFACT_INVALID', '결과 파일 경로를 확인할 수 없습니다.');
    const bytes = await readFile(path);
    if (bytes.length !== file.size || sha(bytes) !== file.sha256) throw new EngineError('ARTIFACT_CHANGED', '보관된 결과 파일이 변경되었습니다.');
    return { path, bytes };
  };
  const primary = await read(artifact);
  if (!Array.isArray(artifact.companions)) throw new EngineError('ARTIFACT_INVALID', '그림 파일 정보를 확인할 수 없습니다.');
  const name = basename(primary.path);
  validateFileName(name);
  const files: ArtifactCopy[] = [{ name, bytes: primary.bytes }];
  const names = new Set([name.toLowerCase()]);
  for (const companion of artifact.companions) {
    validateFileName(companion.name);
    if (!/^figure-\d+\.png$/.test(companion.name) || names.has(companion.name.toLowerCase())) {
      throw new EngineError('ARTIFACT_INVALID', '그림 파일 이름을 확인할 수 없습니다.');
    }
    const verified = await read(companion);
    if (dirname(verified.path) !== dirname(primary.path) || basename(verified.path) !== companion.name) {
      throw new EngineError('ARTIFACT_INVALID', '그림 파일 경로를 확인할 수 없습니다.');
    }
    names.add(companion.name.toLowerCase());
    files.push({ name: companion.name, bytes: verified.bytes });
  }
  return { path: primary.path, files };
}

export async function saveArtifactWithDialog(options: {
  artifact: VerifiedArtifact; artifactId: string; researchId: string; documentsPath: string; protectedRoot: string;
  chooseFile: (options: SaveDialogOptions) => Promise<SaveDialogReturnValue>;
  chooseDirectory: (options: OpenDialogOptions) => Promise<OpenDialogReturnValue>;
}): Promise<boolean> {
  const { artifact, artifactId, researchId, documentsPath, protectedRoot, chooseFile, chooseDirectory } = options;
  if (!Object.hasOwn(artifactFormats, artifactId)) throw new EngineError('ARTIFACT_INVALID', '결과 파일 형식을 확인할 수 없습니다.');
  const format = artifactFormats[artifactId];
  if (basename(artifact.path) !== artifact.files[0]?.name || !artifact.path.toLowerCase().endsWith(`.${format.extension}`)) {
    throw new EngineError('ARTIFACT_INVALID', '결과 파일 형식을 확인할 수 없습니다.');
  }
  if (format.extension === 'md' || format.extension === 'tex') {
    const choice = await chooseDirectory({
      title: `${format.name} 저장`, buttonLabel: '이 폴더에 저장',
      message: '선택한 위치에 원고와 PNG 그림을 담은 새 폴더를 만듭니다.',
      defaultPath: documentsPath, properties: ['openDirectory', 'dontAddToRecent'],
    });
    if (choice.canceled || !choice.filePaths.length) return false;
    const folderName = `Paper Factory-${researchId.slice(-12)}-${format.extension}-${randomUUID().slice(0, 8)}`;
    await writeArtifactBundle(artifact.files, choice.filePaths[0], folderName, protectedRoot);
  } else {
    if (artifact.files.length !== 1) throw new EngineError('ARTIFACT_INVALID', '결과 파일 형식을 확인할 수 없습니다.');
    const choice = await chooseFile({
      title: `${format.name} 저장`, buttonLabel: '저장', defaultPath: join(documentsPath, basename(artifact.path)),
      filters: [{ name: format.name, extensions: [format.extension] }], properties: ['dontAddToRecent'],
    });
    if (choice.canceled || !choice.filePath) return false;
    await writeArtifactCopy(artifact.files[0].bytes, choice.filePath, protectedRoot);
  }
  return true;
}

async function destinationOutsideApp(destinationPath: string, protectedRoot: string): Promise<string> {
  const destination = validateSaveDestination(destinationPath);
  // An explicit export destination must not overwrite the app's authentication or frozen research data.
  const parent = await realpath(dirname(destination));
  const protectedPath = await realpath(protectedRoot);
  const target = join(parent, basename(destination));
  const rel = relative(protectedPath, target);
  if (rel === '' || (rel !== '..' && !rel.startsWith('..' + sep) && !isAbsolute(rel))) {
    throw new EngineError('SAVE_PATH_INVALID', '앱 데이터 폴더 밖의 저장 경로를 선택하세요.');
  }
  return target;
}

async function verifyOverwriteTarget(target: string): Promise<void> {
  try {
    const info = await lstat(target);
    if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1) throw new EngineError('SAVE_PATH_INVALID', '일반 파일의 저장 경로를 선택하세요.');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
}

async function writeVerifiedFile(bytes: Buffer, target: string): Promise<void> {
  const file = await open(target, 'wx');
  try { await file.writeFile(bytes); await file.sync(); } finally { await file.close(); }
  if (sha(await readFile(target)) !== sha(bytes)) throw new EngineError('SAVED_ARTIFACT_CHANGED', '저장한 파일의 무결성을 확인할 수 없습니다.');
}

export async function writeArtifactCopy(bytes: Buffer, destinationPath: string, protectedRoot: string): Promise<void> {
  const target = await destinationOutsideApp(destinationPath, protectedRoot);
  await verifyOverwriteTarget(target);
  const temporary = join(dirname(target), `.paper-factory-${randomUUID()}.tmp`);
  try {
    await writeVerifiedFile(bytes, temporary);
    await verifyOverwriteTarget(target);
    await rename(temporary, target);
  } finally { await unlink(temporary).catch(error => { if (error.code !== 'ENOENT') throw error; }); }
}

export async function writeArtifactBundle(files: ArtifactCopy[], parentPath: string, folderName: string, protectedRoot: string): Promise<string> {
  validateFileName(folderName);
  if (!files.length) throw new EngineError('ARTIFACT_INVALID', '저장할 결과 파일이 없습니다.');
  const names = new Set<string>();
  for (const file of files) {
    validateFileName(file.name);
    if (names.has(file.name.toLowerCase())) throw new EngineError('ARTIFACT_INVALID', '결과 파일 이름이 중복되었습니다.');
    names.add(file.name.toLowerCase());
  }
  const target = await destinationOutsideApp(join(validateSaveDestination(parentPath), folderName), protectedRoot);
  // Publish a complete new folder in one rename; existing exports are never merged or overwritten.
  try { await lstat(target); throw new EngineError('SAVE_PATH_INVALID', '이미 존재하는 결과 폴더입니다. 다른 위치를 선택하세요.'); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  const temporary = join(dirname(target), `.paper-factory-${randomUUID()}.tmp`);
  await mkdir(temporary);
  try {
    for (const file of files) await writeVerifiedFile(file.bytes, join(temporary, file.name));
    await rename(temporary, target);
    return target;
  } finally { await rm(temporary, { recursive: true, force: true }); }
}
