// Paper Factory addition: preserve upstream notices in the compiled package.
import { copyFile, mkdir } from 'node:fs/promises';

for (const filename of ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'docs/dependency-inventory.json']) {
  const destination = new URL(`dist/${filename}`, import.meta.url);
  await mkdir(new URL('./', destination), { recursive: true });
  await copyFile(new URL(filename, import.meta.url), destination);
}
