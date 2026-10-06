import test from 'node:test';
import assert from 'node:assert/strict';
import fsPromises, { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { syncBuiltinESMExports } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ChatGPTError } from '@siwc/local';
import { ConnectionController, safeError } from '../dist/connection.js';

async function setup(t) {
  const directory = await mkdtemp(join(tmpdir(), 'pf-connection-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  let state = { status: 'disconnected', sharing: false };
  const listeners = new Set();
  const sdk = {
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    async getSession() { return structuredClone(state); },
    async listProfiles() { return state.profileId ? [{ id: state.profileId, label: 'Connection 1', status: state.status, sharing: state.sharing }] : []; },
    async signIn() { state = { status: 'connected', sharing: true, profileId: 'test-profile' }; return state; },
    async selectProfile(id) { state.profileId = id; return state; },
    async listModels() { if (!state.sharing) throw new ChatGPTError('sign_in_required', 'secret must not leak'); return [{ slug: 'test-model', displayName: 'Test model' }]; },
    async streamResponse(options) { assert.deepEqual(options.input, [{ role: 'user', content: 'Reply with exactly: Paper Factory connection works.' }]); return { text: 'Synthetic transport success' }; },
    cancelSignIn() {},
    async disconnect() { state = { status: 'disconnected', sharing: false }; },
  };
  const published = [];
  const controller = new ConnectionController(sdk, 'test-version', join(directory, 'evidence'), snapshot => published.push(snapshot));
  t.after(() => controller.shutdown());
  await controller.initialize();
  return { sdk, controller, directory, published, listeners, getState: () => state, setState: (value) => { state = value; } };
}

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

for (const [method, busy] of [['selectProfile', 'select-profile'], ['disconnect', 'disconnect']]) {
  test(`${busy} holds an authoritative connection lease through SDK completion and state synchronization`, async (t) => {
    const { sdk, controller, published } = await setup(t);
    await controller.signIn();
    const entered = deferred(), release = deferred(), syncing = deferred(), synced = deferred();
    const original = sdk[method];
    const originalSession = sdk.getSession;
    let accountCalls = 0, blockedSdkCalls = 0;
    sdk[method] = async (...args) => {
      accountCalls++;
      entered.resolve();
      await release.promise;
      await original(...args);
    };
    const firstEvent = published.length;
    const operation = method === 'selectProfile' ? controller.selectProfile('second-profile') : controller.disconnect();
    try {
      assert.equal(controller.isBusy(), true, 'The lease exists before the SDK operation starts');
      assert.equal(controller.snapshot().busy, busy);
      await entered.promise;
      sdk.getSession = async () => { syncing.resolve(); await synced.promise; return originalSession(); };
      sdk.signIn = sdk.listModels = sdk.streamResponse = async () => { blockedSdkCalls++; throw new Error('Unexpected concurrent SDK request'); };
      const rejected = await Promise.all([
        controller.signIn(), controller.selectProfile('third-profile'), controller.disconnect(),
        controller.refreshModels(), controller.verify('test-model'),
      ]);
      assert.ok(rejected.every(snapshot => snapshot.error.code === 'connection_busy' && snapshot.busy === busy));
      assert.equal(accountCalls, 1);
      assert.equal(blockedSdkCalls, 0);
      release.resolve();
      await syncing.promise;
      assert.equal(controller.isBusy(), true, 'The lease remains until authoritative account state has been synchronized');
      assert.equal(controller.snapshot().busy, busy);
      assert.ok(published.slice(firstEvent).every(snapshot => snapshot.busy === busy), 'No idle state may be published during the account change');
      synced.resolve();
      const settled = await operation;
      assert.equal(settled.busy, null);
      assert.equal(settled.error, null);
      assert.equal(controller.isBusy(), false);
      assert.deepEqual(settled, published.at(-1));
      if (method === 'selectProfile') assert.equal(settled.session.profileId, 'second-profile');
      else assert.equal(settled.session.connected, false);
    } finally {
      release.resolve(); synced.resolve();
      await operation;
    }
  });
}

test('shutdown keeps the authoritative connection gate closed without signing out the account', async (t) => {
  const { sdk, controller, listeners } = await setup(t);
  await controller.signIn();
  let disconnects = 0, signIns = 0;
  sdk.disconnect = async () => { disconnects++; };
  sdk.signIn = async () => { signIns++; };
  await controller.shutdown();
  assert.equal(controller.snapshot().busy, null);
  assert.equal(controller.isBusy(), true);
  assert.equal(controller.snapshot().session.connected, true);
  assert.equal((await controller.signIn()).error.code, 'connection_busy');
  assert.equal(disconnects, 0);
  assert.equal(signIns, 0);
  assert.equal(listeners.size, 0);
  await controller.shutdown();
  assert.equal(disconnects, 0);
});

test('shutdown timeout retains the active request and subscription, then permits an explicit safe retry', async (t) => {
  const { sdk, controller, published, listeners } = await setup(t);
  const entered = deferred(), release = deferred();
  let signIns = 0, cancellations = 0, requestSignal;
  sdk.signIn = async ({ signal }) => {
    signIns++; requestSignal = signal; entered.resolve(); await release.promise;
    throw new ChatGPTError('cancelled', '');
  };
  sdk.cancelSignIn = () => { cancellations++; };
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const operation = controller.signIn();
  try {
    await entered.promise;
    const shutdown = controller.shutdown();
    assert.strictEqual(controller.shutdown(), shutdown, 'Repeated close attempts share one settling request');
    const failed = assert.rejects(shutdown, error => error.code === 'connection_shutdown_unconfirmed');
    t.mock.timers.tick(15_000);
    await failed;
    assert.equal(requestSignal.aborted, true);
    assert.equal(cancellations, 1);
    assert.equal(controller.isBusy(), true);
    assert.equal(controller.snapshot().busy, 'sign-in');
    assert.equal(controller.snapshot().error.code, 'connection_shutdown_unconfirmed');
    assert.deepEqual(published.at(-1), controller.snapshot());
    assert.equal(listeners.size, 1);
    assert.equal((await controller.disconnect()).error.code, 'connection_busy');
    release.resolve();
    await operation;
    assert.equal(controller.isBusy(), false);
    assert.equal(listeners.size, 1);
    await controller.shutdown();
    assert.equal(listeners.size, 0);
    assert.equal(controller.isBusy(), true);
    assert.equal(signIns, 1, 'Retrying shutdown never restarts authentication');
  } finally {
    release.resolve(); await operation;
    t.mock.timers.reset();
  }
});

test('a cancellation failure restores controller publication and preserves login until shutdown retry succeeds', async (t) => {
  const { sdk, controller, published, listeners } = await setup(t);
  await controller.signIn();
  sdk.cancelSignIn = () => { throw new Error('private cancellation details'); };
  await assert.rejects(controller.shutdown(), error => error.code === 'connection_shutdown_unconfirmed' && !error.message.includes('private'));
  assert.equal(controller.isBusy(), false);
  assert.equal(controller.snapshot().session.connected, true);
  assert.equal(listeners.size, 1);
  assert.deepEqual(published.at(-1), controller.snapshot());
  sdk.cancelSignIn = () => {};
  await controller.shutdown();
  assert.equal(listeners.size, 0);
  assert.equal(controller.snapshot().session.connected, true);
});

test('a complete append followed by an error is reconciled without duplicating the original evidence line', async (t) => {
  const { controller, directory, sdk } = await setup(t);
  const originalAppend = fsPromises.appendFile;
  let appends = 0, requests = 0;
  sdk.listModels = async () => { requests++; return []; };
  const mocked = t.mock.method(fsPromises, 'appendFile', async (...args) => {
    await originalAppend(...args);
    if (++appends === 1) throw new Error('Synthetic after-commit failure');
  });
  syncBuiltinESMExports();
  try {
    assert.equal((await controller.refreshModels()).error.code, 'evidence_write_failed');
    await controller.shutdown();
    const lines = (await readFile(join(directory, 'evidence', 'connection-checks.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
    assert.equal(lines.filter(line => line.event === 'request-started').length, 1);
    assert.equal(lines.filter(line => line.event === 'request-failed' && line.code === 'evidence_write_failed').length, 1);
    assert.equal(appends, 2);
    assert.equal(requests, 0);
  } finally { mocked.mock.restore(); syncBuiltinESMExports(); }
});

for (const suffix of ['', '\n']) {
  test(`an ${suffix ? 'invalid terminated' : 'incomplete'} append is preserved and blocks shutdown until evidence is repaired`, async (t) => {
    const { controller, directory, sdk, listeners } = await setup(t);
    const path = join(directory, 'evidence', 'connection-checks.jsonl');
    const originalJournal = await readFile(path);
    const originalAppend = fsPromises.appendFile;
    let appends = 0, requests = 0, repaired = false;
    sdk.listModels = async () => { requests++; return []; };
    const mocked = t.mock.method(fsPromises, 'appendFile', async (file, content, options) => {
      appends++;
      await originalAppend(file, String(content).slice(0, 12) + suffix, options);
      throw new Error('Synthetic partial append failure');
    });
    syncBuiltinESMExports();
    try {
      assert.equal((await controller.refreshModels()).error.code, 'evidence_write_failed');
      const damaged = await readFile(path);
      await assert.rejects(controller.shutdown(), error => error.code === 'evidence_write_failed');
      assert.equal(controller.isBusy(), true, 'Unsaved original evidence keeps account and research gates closed');
      assert.equal(listeners.size, 1);
      assert.deepEqual(await readFile(path), damaged, 'Recovery never extends or overwrites an invalid journal');
      assert.equal(appends, 1);
      assert.equal(requests, 0);
      mocked.mock.restore(); syncBuiltinESMExports();
      // Repair only this owned synthetic file; the production controller must preserve it.
      await writeFile(path, originalJournal);
      repaired = true;
      await controller.shutdown();
      const lines = (await readFile(path, 'utf8')).trim().split('\n').map(JSON.parse);
      assert.equal(lines.filter(line => line.event === 'request-started').length, 1);
      assert.equal(lines.filter(line => line.event === 'request-failed' && line.code === 'evidence_write_failed').length, 1);
      assert.equal(listeners.size, 0);
      assert.equal(requests, 0);
    } finally {
      mocked.mock.restore(); syncBuiltinESMExports();
      // Keep teardown safe even when an assertion fails before fixture repair.
      if (!repaired) await writeFile(path, originalJournal);
    }
  });
}

test('login and model discovery do not establish completed inference', async (t) => {
  const { controller, directory } = await setup(t);
  assert.equal((await controller.refreshModels()).error.code, 'sign_in_required');
  const signedIn = await controller.signIn();
  assert.equal(signedIn.session.connected, true);
  assert.equal(signedIn.verification, null);
  assert.equal((await controller.refreshModels()).verification, null);
  const result = await controller.verify('test-model');
  assert.equal(result.verification.text, 'Synthetic transport success');
  assert.equal(result.error, null);
  const records = (await readFile(join(directory, 'evidence', 'connection-checks.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  assert.equal(records.filter((r) => r.event === 'response-completed').length, 1);
  assert.match(records.at(-1).textSha256, /^[a-f0-9]{64}$/);
  assert.equal(records.at(-1).profileId, 'test-profile');
  assert.equal(JSON.stringify(records).includes('secret must not leak'), false);
});

test('revoked sharing retains identity without permitting inference', async (t) => {
  const { sdk, controller, setState } = await setup(t);
  sdk.signIn = async () => { const s = { status: 'connected', sharing: false, profileId: 'no-sharing' }; setState(s); return s; };
  const result = await controller.signIn();
  assert.equal(result.session.connected, true);
  assert.equal(result.session.sharing, false);
  assert.equal(result.error.code, 'sharing_not_enabled');
  assert.equal(result.verification, null);
});

test('interrupted, incomplete, usage-limited and empty streams never leave stale success', async (t) => {
  const { sdk, controller } = await setup(t);
  await controller.signIn();
  await controller.refreshModels();
  await controller.verify('test-model');
  for (const code of ['stream_interrupted', 'response_incomplete', 'subscription_sharing_usage_limit_exceeded']) {
    sdk.streamResponse = async () => { throw new ChatGPTError(code, 'server detail is private'); };
    const result = await controller.verify('test-model');
    assert.equal(result.verification, null);
    assert.equal(result.error.code, code);
    assert.equal(JSON.stringify(result).includes('server detail'), false);
  }
  sdk.streamResponse = async () => ({ text: '  ' });
  assert.equal((await controller.verify('test-model')).error.code, 'empty_response');
  assert.equal((await controller.verify('arbitrary-model')).error.code, 'model_not_found');
});

test('cancel waits for owned request to end and blocks simultaneous account changes', async (t) => {
  const { sdk, controller } = await setup(t);
  await controller.signIn();
  await controller.refreshModels();
  let started;
  const entered = new Promise((resolve) => { started = resolve; });
  sdk.streamResponse = ({ signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new ChatGPTError('cancelled', '')), { once: true });
    started();
  });
  const pending = controller.verify('test-model');
  await entered;
  assert.equal(controller.snapshot().busy, 'verify');
  assert.equal((await controller.disconnect()).error.code, 'connection_busy');
  const result = await controller.cancel();
  await pending;
  assert.equal(result.error.code, 'cancelled');
  assert.equal(result.busy, null);
  assert.equal(result.verification, null);
  assert.equal(result.session.connected, true);
});

test('remote revocation failure shows local signout and unconfirmed remote permission', async (t) => {
  const { sdk, controller, setState } = await setup(t);
  await controller.signIn();
  sdk.disconnect = async () => { setState({ status: 'disconnected', sharing: false }); throw new ChatGPTError('revocation_failed', ''); };
  const result = await controller.disconnect();
  assert.equal(result.session.connected, false);
  assert.equal(result.error.code, 'revocation_failed');
  assert.equal(result.error.action, 'usage');
});

test('new controller restores metadata but cannot report prior probe as fresh inference', async (t) => {
  const { sdk, controller, directory } = await setup(t);
  await controller.signIn();
  await controller.refreshModels();
  await controller.verify('test-model');
  await controller.shutdown();
  const restarted = new ConnectionController(sdk, 'test-version', join(directory, 'evidence'), () => {});
  t.after(() => restarted.shutdown());
  const restored = await restarted.initialize();
  assert.equal(restored.session.connected, true);
  assert.equal(restored.verification, null);
  assert.deepEqual(restored.models, []);
});

test('failure to save receipt cannot mark inference verified', async (t) => {
  const { controller, directory } = await setup(t);
  await controller.signIn();
  await controller.refreshModels();
  await writeFile(join(directory, 'evidence', 'connection-checks.jsonl'), '');
  await rm(join(directory, 'evidence'), { recursive: true });
  await writeFile(join(directory, 'evidence'), 'blocks directory');
  try {
    const result = await controller.verify('test-model');
    assert.equal(result.error.code, 'evidence_write_failed');
    assert.equal(result.verification, null);
    await assert.rejects(controller.shutdown(), error => error.code === 'evidence_write_failed');
  } finally {
    await rm(join(directory, 'evidence'));
    await mkdir(join(directory, 'evidence'));
  }
  await controller.shutdown();
});

test('unknown exception text and token-like messages are redacted', () => {
  assert.equal(JSON.stringify(safeError(new Error('Bearer private-access-token'))).includes('private-access-token'), false);
  assert.equal(JSON.stringify(safeError(new ChatGPTError('api_error', 'https://callback/?code=secret', false, 403))).includes('secret'), false);
  assert.equal(safeError(new ChatGPTError('storage_encryption_unavailable', '')).action, null);
});

test('pending issued registrations survive snapshots and reauthorize the same ID', async (t) => {
  const { sdk, controller, setState } = await setup(t);
  sdk.listProfiles = async () => [{ id: 'pending-registration', label: 'Connection 1', status: 'disconnected', sharing: false, pending: true }];
  const pending = await controller.initialize();
  assert.equal(pending.profiles[0].pending, true);
  sdk.signIn = async (options) => {
    assert.equal(options.profileId, 'pending-registration');
    assert.equal(options.newProfile, undefined);
    const state = { status: 'connected', sharing: true, profileId: 'pending-registration' };
    setState(state);
    return state;
  };
  assert.equal((await controller.signIn('pending-registration')).session.profileId, 'pending-registration');
});

test('login deadline differs from user cancellation without waiting nine minutes', async (t) => {
  const { sdk, controller } = await setup(t);
  let started;
  const entered = new Promise((resolve) => { started = resolve; });
  sdk.signIn = ({ signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new ChatGPTError('cancelled', '')), { once: true });
    started();
  });
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const pending = controller.signIn();
  await entered;
  t.mock.timers.tick(9 * 60_000);
  assert.equal((await pending).error.code, 'sign_in_expired');
  t.mock.timers.reset();
});

test('account-switch receipts identify the restored connection without emails or tokens', async (t) => {
  const { controller, directory } = await setup(t);
  await controller.signIn();
  await controller.selectProfile('second-profile');
  const records = (await readFile(join(directory, 'evidence', 'connection-checks.jsonl'), 'utf8')).trim().split('\n').map(JSON.parse);
  const switched = records.find((record) => record.event === 'profile-selected');
  assert.equal(switched.profileId, 'second-profile');
  assert.equal(controller.snapshot().verification, null);
  assert.deepEqual(controller.snapshot().models, []);
});
