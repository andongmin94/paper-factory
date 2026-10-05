import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
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
  const controller = new ConnectionController(sdk, 'test-version', join(directory, 'evidence'), () => {});
  t.after(() => controller.shutdown());
  await controller.initialize();
  return { sdk, controller, directory, getState: () => state, setState: (value) => { state = value; } };
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
  const result = await controller.verify('test-model');
  assert.equal(result.error.code, 'evidence_write_failed');
  assert.equal(result.verification, null);
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
