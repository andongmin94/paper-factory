import assert from 'node:assert/strict';
import test from 'node:test';
import { listPublicRepositories } from '../dist/repositories.js';

test('account discovery rejects credential, repository and arbitrary endpoint URLs before any network call', async () => {
  const original = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; throw new Error('Unexpected network request'); };
  try {
    for (const url of ['http://github.com/owner', 'https://github.com/owner/repo', 'https://owner:secret@github.com/owner',
      'https://github.com/owner?token=secret', 'https://example.invalid/owner']) {
      await assert.rejects(listPublicRepositories(url));
    }
    assert.equal(calls, 0);
  } finally { globalThis.fetch = original; }
});

test('account discovery accepts only explicitly public repositories of the requested owner and constructs trusted URLs', async () => {
  const original = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return Response.json([
      { name: 'paper-factory', private: false, owner: { login: 'Owner' }, html_url: 'https://malicious.invalid', description: 'Public data' },
      { name: 'private-repo', private: true, owner: { login: 'owner' } },
      { name: 'unknown-visibility', owner: { login: 'owner' } },
      { name: 'different-owner', private: false, owner: { login: 'another' } },
      { name: '../escape', private: false, owner: { login: 'owner' } },
    ]);
  };
  try {
    assert.deepEqual(await listPublicRepositories('https://github.com/owner'), [
      { name: 'paper-factory', url: 'https://github.com/owner/paper-factory' },
    ]);
    assert.equal(request.url, 'https://api.github.com/users/owner/repos?type=owner&sort=updated&per_page=100');
    assert.equal(request.options.redirect, 'error');
    assert(!('Authorization' in request.options.headers));
  } finally { globalThis.fetch = original; }
});
