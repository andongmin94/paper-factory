import { lstat, realpath, unlink } from "node:fs/promises";
import path from "node:path";

// Reuse npm's SDK and remove its demo before app integrity is computed.
export default async function afterExtract(context) {
  if (context.electronPlatformName !== "win32") throw new Error("Build on native Windows.");
  const project = await realpath(context.packager.projectDir);
  const output = await realpath(context.appOutDir);
  const relative = path.relative(project, output);
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("The application output must stay inside the desktop project.");
  }
  for (const name of ["resources/default_app.asar", "version"]) {
    const filename = path.join(output, name);
    const entry = await lstat(filename).catch((error) => {
      if (error.code !== "ENOENT") throw error;
      return null;
    });
    if (!entry) continue;
    if (!entry.isFile()) throw new Error("Unexpected Electron demo asset.");
    await unlink(filename);
  }
}
