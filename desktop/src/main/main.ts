// Scientific child mode must branch before importing the account/UI application.
import { app } from 'electron';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
if (process.argv.includes('--paper-factory-chromium-worker')) {
  const worker = app.isPackaged ? join(process.resourcesPath, 'chromium-worker.mjs') : join(root, 'chromium-worker.mjs');
  const index = process.argv.indexOf('--worker');
  if (index < 0 || process.argv[index + 1] === undefined || resolve(process.argv[index + 1]!) !== resolve(worker)) app.exit(1);
  else void import(pathToFileURL(worker).href).catch(() => app.exit(1));
} else {
  void import(pathToFileURL(join(root, 'app.js')).href).catch(() => app.exit(1));
}
