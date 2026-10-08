import { build } from 'esbuild';
import { mkdir, copyFile } from 'node:fs/promises';

await mkdir('dist', { recursive: true });
await build({
  entryPoints: ['src/main/main.ts'], outfile: 'dist/main.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22',
  external: ['electron'],
});
await build({
  entryPoints: ['src/main/app.ts'], outfile: 'dist/app.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22', external: ['electron', '@siwc/local'],
});
await build({
  entryPoints: ['src/main/chromium-worker.ts'], outfile: 'dist/chromium-worker.mjs',
  bundle: true, platform: 'node', format: 'esm', target: 'node22', external: ['electron'],
});
await build({
  entryPoints: ['src/main/chromium-contract.ts'], outfile: 'dist/chromium-contract.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22',
});
await build({
  entryPoints: ['src/main/preload.ts'], outfile: 'dist/preload.cjs',
  bundle: true, platform: 'node', format: 'cjs', target: 'node22', external: ['electron'],
});
// Exercise the same service implementation with fake SDK transports in node:test.
await build({
  entryPoints: ['src/main/connection.ts'], outfile: 'dist/connection.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22', external: ['@siwc/local'],
});
await build({
  entryPoints: ['src/main/research.ts'], outfile: 'dist/research.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22', external: ['@siwc/local', './engine.js'],
});
await build({
  entryPoints: ['src/main/engine.ts'], outfile: 'dist/engine.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22',
});
await build({
  entryPoints: ['src/main/repositories.ts'], outfile: 'dist/repositories.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22',
});
await build({
  entryPoints: ['src/main/artifacts.ts'], outfile: 'dist/artifacts.js',
  bundle: true, platform: 'node', format: 'esm', target: 'node22',
});
await copyFile('../LICENSE', 'dist/LICENSE');
