import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import test from 'node:test';
import { EngineBridge } from '../dist/engine.js';

// Owned synthetic child: no executable, research, credentials or OS process.
function fixture() {
  const bridge = new EngineBridge('unused synthetic runtime', 'unused synthetic home', 'unused synthetic binding');
  const child = new EventEmitter(); const requests = []; let kills = 0, ends = 0;
  child.stdout = new EventEmitter(); child.stderr = { resume() {} };
  child.exitCode = null; child.signalCode = null;
  child.kill = () => { kills++; };
  child.stdin = { write(line, callback) { requests.push(JSON.parse(line)); callback?.(); return true; }, end() { ends++; } };
  bridge.attachChild(child); bridge.needsShutdown = true;
  const reply = (index, result, error) => child.stdout.emit('data', Buffer.from(JSON.stringify({ id: requests[index].id,
    ok: !error, ...(error ? { error } : { result }) }) + '\n'));
  const exit = (code, close = true) => { child.exitCode = code; child.emit('exit', code, null); if (close) child.emit('close', code, null); };
  return { bridge, child, requests, reply, exit, get kills() { return kills; }, get ends() { return ends; } };
}
async function requested(f, count = 1) {
  for (let i = 0; i < 100; i++) { if (f.requests.length >= count) return; await delay(1); }
  throw new Error('Synthetic shutdown request did not arrive');
}

test('engine close shares one shutdown and waits for both acknowledgement and actual zero-code exit', async () => {
  const f = fixture(); let settled = false;
  const closing = f.bridge.close(); assert.equal(f.bridge.close(), closing);
  closing.then(() => { settled = true; });
  await requested(f); f.reply(0, { closed: true }); await delay(1);
  assert.equal(settled, false); assert.equal(f.ends, 0); assert.equal(f.kills, 0);
  f.exit(0); await closing;
  assert.equal(f.bridge.needsShutdown, false); assert.equal(f.bridge.child, undefined);
  await f.bridge.close(); assert.equal(f.requests.length, 1);
});

test('engine cleanup rejection keeps the child alive and permits explicit shutdown retry', async () => {
  const f = fixture(); const closing = f.bridge.close();
  const rejected = assert.rejects(closing, error => error.code === 'CLEANUP_UNCONFIRMED');
  await requested(f); f.reply(0, undefined, { code: 'CLEANUP_UNCONFIRMED', message: 'Synthetic owned worker pending' });
  await rejected; assert.equal(f.kills, 0); assert.equal(f.ends, 0); assert.equal(f.bridge.needsShutdown, true);
  const retry = f.bridge.close(); await requested(f, 2); f.reply(1, { closed: true }); f.exit(0); await retry;
  assert.equal(f.bridge.needsShutdown, false); assert.equal(f.kills, 0);
});

test('exit before final stdout acknowledgement still waits for drained stdio and confirms cleanup', async () => {
  const f = fixture(); const closing = f.bridge.close();
  await requested(f); f.exit(0, false);
  assert.equal(f.bridge.child, f.child, 'Exit alone must not discard the final reply');
  f.reply(0, { closed: true }); f.child.emit('close', 0, null);
  await closing; assert.equal(f.bridge.needsShutdown, false); assert.equal(f.kills, 0);
});

test('shutdown timeout and its late reply neither kill the child nor prove successful shutdown', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = fixture(); const closing = f.bridge.close();
  const rejected = assert.rejects(closing, error => error.code === 'ENGINE_SHUTDOWN_UNCONFIRMED');
  await Promise.resolve(); t.mock.timers.tick(35_000); await rejected;
  f.reply(0, { closed: true });
  assert.equal(f.kills, 0); assert.equal(f.ends, 0); assert.equal(f.bridge.needsShutdown, true);
  const retry = f.bridge.close(); await Promise.resolve(); f.reply(1, { closed: true }); f.exit(0); await retry;
  t.mock.timers.reset();
});

test('an acknowledged shutdown with a live child cannot silently unlock after the exit deadline', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = fixture(); const closing = f.bridge.close();
  const rejected = assert.rejects(closing, error => error.code === 'ENGINE_SHUTDOWN_UNCONFIRMED');
  await Promise.resolve(); f.reply(0, { closed: true }); await Promise.resolve(); t.mock.timers.tick(10_000); await rejected;
  assert.equal(f.kills, 0); assert.equal(f.bridge.needsShutdown, true);
  const retry = f.bridge.close(); await Promise.resolve();
  assert.equal(f.requests.length, 1, 'An already acknowledged engine has left the read loop; retry only waits for exit');
  assert.equal(f.ends, 0, 'Do not end a writable channel while exit remains unconfirmed');
  f.exit(0); await retry;
  t.mock.timers.reset();
});

test('nonzero exit after acknowledgement remains unconfirmed', async () => {
  const f = fixture(); const closing = f.bridge.close();
  const rejected = assert.rejects(closing, error => error.code === 'ENGINE_SHUTDOWN_UNCONFIRMED');
  await requested(f); f.reply(0, { closed: true }); f.exit(1); await rejected;
  assert.equal(f.bridge.needsShutdown, true); assert.equal(f.kills, 0);
});

test('engine exit without acknowledgement requires recovery before another close can succeed', async () => {
  const f = fixture(); const closing = f.bridge.close();
  const rejected = assert.rejects(closing, error => error.code === 'ENGINE_INTERRUPTED');
  await requested(f);
  const { EngineError } = await import('../dist/engine.js');
  f.bridge.fail(new EngineError('ENGINE_INTERRUPTED', 'Synthetic lost engine'));
  f.exit(0); f.bridge.child = undefined; await rejected;
  let recoveries = 0;
  f.bridge.start = async () => { recoveries++; throw new EngineError('RUNTIME_UNAVAILABLE', 'Synthetic recovery failure'); };
  await assert.rejects(f.bridge.close(), error => error.code === 'RUNTIME_UNAVAILABLE');
  assert.equal(recoveries, 1); assert.equal(f.bridge.needsShutdown, true);
});
