import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { ChatGPTError } from '@siwc/local';
import { apiError } from '../vendor/siwc-local/dist/errors.js';
import { ConnectionController } from '../dist/connection.js';

async function failureReceipt(t, error) {
  const parent = resolve(tmpdir());
  const directory = await mkdtemp(join(parent, 'pf-connection-diagnostics-'));
  assert.equal(dirname(directory), parent);
  const evidenceDir = join(directory, 'evidence');
  const sdk = {
    subscribe() { return () => {}; },
    async getSession() { return { status: 'connected', sharing: true, profileId: 'synthetic-profile' }; },
    async listProfiles() { return []; },
    async listModels() { return [{ slug: 'synthetic-model', displayName: 'Synthetic model' }]; },
    async streamResponse() { throw error; },
    cancelSignIn() {},
  };
  const controller = new ConnectionController(sdk, 'synthetic-version', evidenceDir, () => {});
  t.after(async () => {
    await controller.shutdown();
    await rm(directory, { recursive: true, force: true });
  });
  await controller.initialize();
  await controller.refreshModels();
  const snapshot = await controller.verify('synthetic-model');
  const receiptText = await readFile(join(evidenceDir, 'connection-checks.jsonl'), 'utf8');
  const receipt = receiptText.trim().split('\n').map(JSON.parse).findLast((record) => record.event === 'request-failed');
  assert.equal(snapshot.verification, null);
  return { snapshot, receipt, receiptText };
}

test('structured SDK errors retain field and shape diagnostics without private response content', async (t) => {
  const marker = 'synthetic-private-value-never-persist';
  const error = apiError({ error: {
    code: 'subscription_sharing_usage_limit_exceeded',
    message: marker,
    param: 'model',
    input: { access_token: marker },
    ctx: { email: marker },
    unexpected_private_field: marker,
  } }, 200, 'synthetic-request-id');
  const { snapshot, receipt, receiptText } = await failureReceipt(t, error);
  assert.equal(receipt.code, 'subscription_sharing_usage_limit_exceeded');
  assert.equal(receipt.httpStatus, 200);
  assert.equal(receipt.requestId, 'synthetic-request-id');
  assert.equal(receipt.param, 'model');
  assert.equal(receipt.responseShape, '{error:{code:string,message:string,param:string,input:redacted,ctx:redacted,other:1}}');
  assert.equal(receiptText.includes(marker), false);
  assert.equal(receiptText.includes('access_token'), false);
  assert.equal(receiptText.includes('unexpected_private_field'), false);
  assert.equal(snapshot.error.action, 'usage');
  assert.equal(JSON.stringify(snapshot).includes('responseShape'), false);
  assert.equal(JSON.stringify(snapshot).includes('synthetic-request-id'), false);
});

test('safe admission detail shape survives without the raw detail string', async (t) => {
  const { receipt, receiptText } = await failureReceipt(t, apiError({ detail: 'synthetic private admission detail' }, 403));
  assert.equal(receipt.code, 'api_error');
  assert.equal(receipt.httpStatus, 403);
  assert.equal(receipt.responseShape, '{detail:string}');
  assert.equal(receiptText.includes('synthetic private admission detail'), false);
});

test('known indexed parameter paths and nested redacted shape labels are retained', async (t) => {
  const { receipt } = await failureReceipt(t, new ChatGPTError('invalid_request', 'private message', false, 400, {
    param: 'input[0].content[1].type',
    responseShape: '{detail:[{type:string,loc:array,input:redacted,ctx:redacted}]}',
  }));
  assert.equal(receipt.param, 'input[0].content[1].type');
  assert.equal(receipt.responseShape, '{detail:[{type:string,loc:array,input:redacted,ctx:redacted}]}');
});

test('shape grammar and size bounds reject injected labels, values, suffixes, and excessive nesting', async (t) => {
  for (const responseShape of [
    '{error:{access_token:string}}',
    '{error:{message:synthetic_secret}}',
    '{error:{message:"synthetic private body"}}',
    '{detail:string}synthetic_secret',
    '{error:{response:{error:{code:string}}}}',
    '{other:1000001}',
    '{error:string,}',
    '{detail:string}\n',
    'string'.repeat(500),
  ]) {
    const { receipt } = await failureReceipt(t, new ChatGPTError('api_error', 'synthetic private exception', false, 400, {
      param: 'model', responseShape,
    }));
    assert.equal(Object.hasOwn(receipt, 'responseShape'), false);
    assert.equal(receipt.param, 'model');
  }
});

test('unknown, token-like, control-character, and oversized parameter values are omitted', async (t) => {
  for (const param of [
    'synthetic_secret_token',
    'input[0].access_token',
    'input[123456].type',
    'model\nsynthetic_secret',
    'model?code=synthetic_secret',
    'input' + '.content'.repeat(30),
  ]) {
    const { receipt } = await failureReceipt(t, new ChatGPTError('api_error', 'private exception', false, 400, {
      param, responseShape: '{detail:string}',
    }));
    assert.equal(Object.hasOwn(receipt, 'param'), false);
    assert.equal(receipt.responseShape, '{detail:string}');
  }
});

test('ordinary exception diagnostic lookalikes are never trusted', async (t) => {
  const error = Object.assign(new Error('synthetic private exception'), {
    param: 'model', responseShape: '{detail:string}', requestId: 'synthetic-request-id', status: 400,
  });
  const { receipt, receiptText } = await failureReceipt(t, error);
  assert.equal(receipt.code, 'connection_error');
  for (const key of ['param', 'responseShape', 'requestId', 'httpStatus']) assert.equal(Object.hasOwn(receipt, key), false);
  assert.equal(receiptText.includes('synthetic private exception'), false);
});
