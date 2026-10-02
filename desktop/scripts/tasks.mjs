// Task launcher adapted from create-frontron; no shell interpolation.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, realpathSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = realpathSync.native(dirname(dirname(fileURLToPath(import.meta.url))));
const command = process.argv[2];
const args = process.argv.slice(3);
const require = createRequire(import.meta.url);
const bins = { tsc: "typescript" };
// Explicit globs cover nested application code; vendored upstream sources stay exact.
const formatFiles = [
  "src/**/*.{ts,tsx,cts,css}",
  "!src/renderer/components/ui/**",
  "!src/renderer/lib/utils.ts",
  "!src/renderer/styles/neobrutal.css",
  "!src/renderer/vendor/**",
  "scripts/*.mjs",
  "*.config.ts",
  "package.json",
  "runtime-versions.json",
  "tsconfig*.json",
];
function resolveBin(name) {
  const packageName = bins[name] ?? name;
  const manifestPath = join(root, "node_modules", packageName, "package.json");
  if (!existsSync(manifestPath)) throw new Error(`Missing ${packageName}; run npm ci first.`);
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const bin =
    typeof manifest.bin === "string"
      ? manifest.bin
      : (manifest.bin?.[name] ?? manifest.bin?.[packageName]);
  if (!bin) throw new Error(`No ${name} executable in ${packageName}.`);
  return join(dirname(manifestPath), bin);
}
function runBin(name, binArgs = []) {
  const result = spawnSync(process.execPath, [resolveBin(name), ...binArgs], {
    cwd: root,
    stdio: "inherit",
    shell: false,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
function typecheck() {
  runBin("tsc", ["-b"]);
  runBin("tsc", ["-p", "tsconfig.electron.json"]);
}
function build() {
  typecheck();
  runBin("vite", ["build"]);
}

switch (command) {
  case "dev":
    runBin("vite", args);
    break;
  case "app": {
    runBin("tsc", ["-p", "tsconfig.electron.json"]);
    const { createServer } = await import("vite");
    const vite = await createServer({ root });
    await vite.listen();
    const { ELECTRON_RUN_AS_NODE: _ignored, ...env } = process.env;
    const child = spawn(require("electron"), ["."], {
      cwd: root,
      stdio: ["pipe", "inherit", "inherit"],
      shell: false,
      windowsHide: true,
      env: { ...env, ELECTRON_RENDERER_URL: "http://127.0.0.1:5173/" },
    });
    // Ask Electron to perform its authenticated graceful backend shutdown.
    // Never terminate it while research cleanup may still be running.
    process.on("SIGINT", () => child.stdin.write("paperfactory:quit\n"));
    process.on("SIGTERM", () => child.stdin.write("paperfactory:quit\n"));
    child.once("error", async (error) => {
      console.error(error);
      await vite.close();
      process.exitCode = 1;
    });
    child.once("exit", async (code) => {
      await vite.close();
      process.exitCode = code ?? 1;
    });
    break;
  }
  case "typecheck":
    typecheck();
    break;
  case "build":
    build();
    break;
  case "package": {
    build();
    runBin("electron-builder", ["--win", "--publish", "never", ...args]);
    break;
  }
  case "test":
    runBin("vitest", ["run", ...args]);
    break;
  case "lint":
    runBin("oxlint", ["src", "scripts", "vite.config.ts", "vitest.config.ts", ...args]);
    break;
  case "format":
    runBin("oxfmt", [...formatFiles, ...args]);
    break;
  case "format:check":
    runBin("oxfmt", ["--check", ...formatFiles, ...args]);
    break;
  default:
    throw new Error(`Unknown task: ${command ?? "(missing)"}`);
}
