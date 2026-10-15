import assert from 'node:assert/strict';
import test from 'node:test';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const { outputFiles } = await build({ stdin: {
  contents: "export { lookupPublicOrcidProfile } from './src/main/orcid.ts'; export { normalizeOrcidInput } from './src/shared/orcid.ts';",
  resolveDir: fileURLToPath(new URL('..', import.meta.url)), loader: 'ts',
}, bundle: true, write: false, platform: 'node', format: 'esm', target: 'node22' });
const { lookupPublicOrcidProfile, normalizeOrcidInput } = await import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString('base64')}`);
const id = '0009-0009-8671-9967';
const sourceUrl = `https://orcid.org/${id}`;
function records() {
  return {
    person: { path: `/${id}/person`, name: { visibility: 'public', 'given-names': { value: 'Sanghoon' },
      'family-name': { value: 'Kim' }, 'credit-name': null }, emails: { email: [] }, biography: null },
    employments: { path: `/${id}/employments`, 'affiliation-group': [] },
    educations: { path: `/${id}/educations`, 'affiliation-group': [] },
  };
}
function affiliation(kind, code, value = {}) {
  return { [`${kind}-summary`]: { path: `/${id}/${kind}/${code}`, 'put-code': code, visibility: 'public',
    organization: { name: 'Gyeongkuk National University' }, 'department-name': null, 'role-title': null,
    'start-date': null, 'end-date': null, ...value } };
}
async function withFetch(operation, responder = (url) => Response.json(records()[url.split('/').at(-1)])) {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return responder(url, options); };
  try { return await operation(calls); } finally { globalThis.fetch = original; }
}

test('ORCID syntax and ISO checksum reject arbitrary URLs or tokens before the network', async () => {
  assert.equal(normalizeOrcidInput(` ${id} `), id);
  assert.equal(normalizeOrcidInput(`${sourceUrl}/`), id);
  assert.equal(normalizeOrcidInput('0000-0002-1694-233x'), '0000-0002-1694-233X');
  await withFetch(async calls => {
    for (const value of [null, {}, '', '0009-0009-8671-9966', 'http://orcid.org/' + id, `https://user:secret@orcid.org/${id}`,
      `https://orcid.org/${id}?token=secret`, `https://orcid.org/${id}#private`, `https://example.org/${id}`,
      `https://pub.orcid.org/v3.0/${id}/person`, `https://orcid.org/my-orcid?orcid=${id}`, id + '\nsecret']) {
      assert.equal(normalizeOrcidInput(value), null);
      await assert.rejects(lookupPublicOrcidProfile(value), /ORCID/);
    }
    assert.equal(calls.length, 0);
  });
});

test('anonymous lookup uses only three fixed public endpoints, no credentials, and explicit provenance', async () => {
  await withFetch(async calls => {
    const result = await lookupPublicOrcidProfile(sourceUrl);
    assert.equal(result.orcid, id);
    assert.equal(result.sourceUrl, sourceUrl);
    assert.equal(result.name, 'Sanghoon Kim');
    assert.deepEqual(result.emails, []);
    assert.equal(result.biography, null);
    assert.deepEqual(result.affiliations, []);
    assert.equal(result.publicOnly, true);
    assert.equal(result.authenticated, false);
    assert(Number.isFinite(Date.parse(result.retrievedAt)));
    assert.deepEqual(calls.map(call => call.url), ['person', 'employments', 'educations'].map(section => `https://pub.orcid.org/v3.0/${id}/${section}`));
    for (const { options } of calls) {
      assert.equal(options.redirect, 'error');
      assert.equal(options.credentials, 'omit');
      assert.equal(options.headers.Accept, 'application/json');
      assert.equal('Authorization' in options.headers, false);
      assert(options.signal instanceof AbortSignal);
      assert.equal(options.signal.aborted, true); // Finished requests release the shared deadline and transport.
    }
  });
});

test('record with no public data is a successful empty profile, not an invented author or consent', async () => {
  const data = records();
  data.person.name = null;
  await withFetch(async () => {
    const result = await lookupPublicOrcidProfile(id);
    assert.equal(result.name, null);
    assert.equal(result.biography, null);
    assert.deepEqual(result.emails, []);
    assert.deepEqual(result.affiliations, []);
    assert(!('funding' in result));
    assert(!('approved' in result));
  }, url => Response.json(data[url.split('/').at(-1)]));
});

test('public credit-name wins; only public verified emails and public biography are returned', async () => {
  const data = records();
  data.person.name['credit-name'] = { value: '  김상훈 (Sanghoon Kim)  ' };
  data.person.biography = { visibility: 'PUBLIC', content: 'Public biography.\nSecond paragraph.' };
  data.person.emails.email = [
    { email: 'public@example.org', verified: true, visibility: 'public', primary: true },
    { email: 'public@example.org', verified: true, visibility: 'PUBLIC' },
    { email: 'private@example.org', verified: true, visibility: 'private' },
    { email: 'limited@example.org', verified: true, visibility: 'limited' },
    { email: 'unverified@example.org', verified: false, visibility: 'public' },
    { email: 'implicit@example.org', verified: true },
    { email: 'bad\nmail@example.org', verified: true, visibility: 'public' },
  ];
  await withFetch(async () => {
    const result = await lookupPublicOrcidProfile(id);
    assert.equal(result.name, '김상훈 (Sanghoon Kim)');
    assert.equal(result.biography, data.person.biography.content);
    assert.deepEqual(result.emails, ['public@example.org']);
  }, url => Response.json(data[url.split('/').at(-1)]));
  data.person.name.visibility = 'limited';
  data.person.biography.visibility = 'private';
  await withFetch(async () => {
    const result = await lookupPublicOrcidProfile(id);
    assert.equal(result.name, null);
    assert.equal(result.biography, null);
  }, url => Response.json(data[url.split('/').at(-1)]));
});

test('all current employment and education choices survive; past, future, private and mismatched affiliations do not', async () => {
  const data = records();
  data.employments['affiliation-group'] = [{ summaries: [
    affiliation('employment', 10, { 'role-title': 'Staff' }),
    affiliation('employment', 11, { organization: { name: 'Other University' }, 'start-date': { year: { value: '2000' } } }),
    affiliation('employment', 12, { 'end-date': { year: { value: '2001' } } }),
    affiliation('employment', 13, { 'start-date': { year: { value: '9999' } } }),
    affiliation('employment', 14, { visibility: 'limited' }),
    affiliation('employment', 15, { path: '/different-orcid/employment/15' }),
    affiliation('employment', 16, { 'start-date': { year: { value: '2020' }, month: { value: '02' }, day: { value: '31' } } }),
  ] }];
  data.educations['affiliation-group'] = [{ summaries: [
    affiliation('education', 20, { 'department-name': 'Computer Education', 'role-title': "Master's student (in progress)" }),
    affiliation('education', 21, { 'end-date': { year: { value: '2000' }, month: { value: '02' } } }),
  ] }];
  await withFetch(async () => {
    const result = await lookupPublicOrcidProfile(id);
    assert.deepEqual(result.affiliations.map(value => value.id), ['employment-10', 'employment-11', 'education-20']);
    assert.equal(result.affiliations[0].role, 'Staff');
    assert.equal(result.affiliations[1].organization, 'Other University');
    assert.equal(result.affiliations[1].startDate, '2000');
    assert.equal(result.affiliations[2].department, 'Computer Education');
    assert(result.affiliations.every(value => value.sourceUrl === sourceUrl));
  }, url => Response.json(data[url.split('/').at(-1)]));
});

test('response identifier, MIME and JSON are validated without exposing response bodies', async () => {
  for (const responder of [
    () => Response.json({ path: '/different/person' }),
    () => new Response('<html>SECRET_BODY</html>', { headers: { 'content-type': 'text/html' } }),
    () => new Response('SECRET_BODY', { headers: { 'content-type': 'application/json' } }),
    () => Response.json({}),
  ]) {
    await withFetch(async () => {
      await assert.rejects(lookupPublicOrcidProfile(id), error => /ORCID/.test(error.message) && !error.message.includes('SECRET_BODY'));
    }, responder);
  }
});

test('declared and streamed response limits reject oversize data and cancel unread streams', async () => {
  for (const declared of [true, false]) {
    let cancelled = 0;
    await withFetch(async () => {
      await assert.rejects(lookupPublicOrcidProfile(id), /허용 크기/);
      assert(cancelled > 0);
    }, () => new Response(new ReadableStream({
      start(controller) { controller.enqueue(new Uint8Array(1024 * 1024 + 1)); },
      cancel() { cancelled++; },
    }), { headers: { 'content-type': 'application/json', ...(declared ? { 'content-length': String(1024 * 1024 + 1) } : {}) } }));
  }
});

test('HTTP failures and transport errors are controlled and do not leak secrets', async () => {
  for (const status of [404, 429, 500]) {
    await withFetch(async () => { await assert.rejects(lookupPublicOrcidProfile(id), /ORCID/); }, () => new Response('SECRET_BODY', { status }));
  }
  await withFetch(async () => {
    await assert.rejects(lookupPublicOrcidProfile(id), error => /연결/.test(error.message) && !error.message.includes('SECRET'));
  }, () => { throw new Error('ORCID proxy failure https://user:SECRET@example.org'); });
});

test('shared request deadline aborts hung requests and returns a retryable timeout', async () => {
  const originalTimer = globalThis.setTimeout;
  globalThis.setTimeout = (callback) => originalTimer(callback, 5);
  try {
    await withFetch(async calls => {
      await assert.rejects(lookupPublicOrcidProfile(id), /시간이 만료/);
      assert.equal(calls.length, 3);
      assert(calls.every(call => call.options.signal.aborted));
    }, (_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('SECRET_TIMEOUT', 'AbortError')), { once: true });
    }));
  } finally { globalThis.setTimeout = originalTimer; }
});
