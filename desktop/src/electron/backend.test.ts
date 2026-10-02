// @vitest-environment node
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { Backend, boundedBytes } from "./backend.js";

const fixtures: { directory: string; backend: Backend }[] = [];
async function fixture(refuseShutdown = false, exitCode = 0): Promise<Backend> {
  const directory = await mkdtemp(path.join(os.tmpdir(), "paperfactory-backend-test-"));
  const filename = path.join(directory, "server.mjs");
  await writeFile(
    filename,
    `
    import { createServer } from 'node:http';
    const token = 'a'.repeat(43);
    let refuse = ${refuseShutdown};
    let leaked = 0;
    const server = createServer((req,res) => {
      const origin = 'http://127.0.0.1:' + server.address().port;
      if (req.headers.authorization !== 'Bearer ' + token || req.headers.origin !== origin) { res.writeHead(403);res.end('{}'); return; }
      if(req.url === '/api/redirect') { res.writeHead(302,{location:origin+'/api/leak'}); res.end();return; }
      if(req.url === '/api/leak') leaked++;
      if(req.url === '/api/classified-failure') { res.writeHead(400, {'content-type':'application/json'});res.end(JSON.stringify({code:'AUTH_STORAGE_INVALID',error:'Synthetic safe connection failure'}));return; }
      if(req.url === '/api/invalid-code') { res.writeHead(400, {'content-type':'application/json'});res.end(JSON.stringify({code:'AUTH_REQUIRED\\nprivate-token',error:'Synthetic failure'}));return; }
      if(req.url === '/api/oversized-code') { res.writeHead(400, {'content-type':'application/json'});res.end(JSON.stringify({code:'A'.repeat(65),error:'Synthetic failure'}));return; }
      if(req.url === '/api/crash') { res.writeHead(200, {'content-type':'application/json'});res.end('{}');setTimeout(()=>process.exit(9),50);return; }
      if(req.url === '/api/allow-shutdown') refuse = false;
      if(req.url === '/api/desktop/shutdown') {
        res.writeHead(refuse ? 409 : 200, {'content-type':'application/json'});res.end('{}');
        if(!refuse) server.close(() => process.exit(${exitCode}));
        return;
      }
      res.writeHead(200, {'content-type':'application/json'});res.end(JSON.stringify({authenticated:true,leaked}));
    });
    server.listen(0,'127.0.0.1',()=>process.stdout.write(JSON.stringify({url:'http://127.0.0.1:'+server.address().port,token})+'\\n'));
  `,
  );
  const backend = new Backend({
    executable: process.execPath,
    args: [filename],
    cwd: directory,
    env: process.env,
    startupMs: 5000,
    shutdownMs: 5000,
  });
  fixtures.push({ directory, backend });
  await backend.start();
  return backend;
}

afterEach(async () => {
  for (const { backend, directory } of fixtures.splice(0)) {
    if (backend.ready) await backend.json("/api/allow-shutdown", { method: "POST", body: "{}" });
    await backend.stop().catch((error: unknown) => {
      if (backend.ready) throw error;
    });
    if (
      path.dirname(directory) !== path.resolve(os.tmpdir()) ||
      !path.basename(directory).startsWith("paperfactory-backend-test-")
    )
      throw new Error("Unexpected fixture directory");
    await rm(directory, { recursive: true, force: true });
  }
});

describe("dedicated backend lifecycle", () => {
  it("authenticates requests, rejects redirects and waits for the actual process exit", async () => {
    const backend = await fixture();
    expect(backend.ready).toBe(true);
    expect(await backend.json("/api/health")).toEqual({ authenticated: true, leaked: 0 });
    await expect(backend.fetch("/api/redirect")).rejects.toThrow();
    expect(await backend.json("/api/health")).toEqual({ authenticated: true, leaked: 0 });
    await backend.stop();
    expect(backend.ready).toBe(false);
    await expect(backend.json("/api/health")).rejects.toThrow();
  });
  it("keeps the process alive after a cleanup refusal and permits a later safe retry", async () => {
    const backend = await fixture(true);
    await expect(backend.stop()).rejects.toThrow("안전하게 종료");
    expect(backend.ready).toBe(true);
    expect(await backend.json("/api/health")).toEqual({ authenticated: true, leaked: 0 });
    await backend.json("/api/allow-shutdown", { method: "POST", body: "{}" });
    await backend.stop();
    expect(backend.ready).toBe(false);
  });
  it("preserves a bounded classified error code in the message serialized by Electron IPC", async () => {
    const backend = await fixture();
    await expect(backend.json("/api/classified-failure")).rejects.toThrow(
      "[AUTH_STORAGE_INVALID] Synthetic safe connection failure",
    );
    await expect(backend.json("/api/invalid-code")).rejects.toThrow(/^Synthetic failure$/);
    await expect(backend.json("/api/oversized-code")).rejects.toThrow(/^Synthetic failure$/);
    expect(backend.ready).toBe(true);
  });
  it("enforces streaming response bounds independently of content-length", async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(3));
        controller.enqueue(new Uint8Array(3));
        controller.close();
      },
    });
    await expect(boundedBytes(new Response(stream), 5)).rejects.toThrow("크기");
    expect(await boundedBytes(new Response(new Uint8Array([1, 2, 3])), 5)).toEqual(
      Buffer.from([1, 2, 3]),
    );
  });
  it("rejects a nonzero process exit even after the shutdown endpoint accepts", async () => {
    const backend = await fixture(false, 7);
    await expect(backend.stop()).rejects.toThrow("비정상적으로 종료");
    expect(backend.ready).toBe(false);
    await expect(backend.stop()).rejects.toThrow("비정상적으로 종료");
  });
  it("marks an unexpected process exit unavailable without pretending cleanup succeeded", async () => {
    const backend = await fixture();
    await backend.json("/api/crash");
    await expect.poll(() => backend.ready).toBe(false);
    await expect(backend.json("/api/health")).rejects.toThrow("연결되어 있지");
    await expect(backend.stop()).rejects.toThrow("비정상적으로 종료");
  });
});
