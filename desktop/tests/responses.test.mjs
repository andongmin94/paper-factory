import assert from 'node:assert/strict';
import test from 'node:test';
import { ChatGPTError } from '../vendor/siwc-local/dist/errors.js';
import { listModels } from '../vendor/siwc-local/dist/models.js';
import { streamResponse } from '../vendor/siwc-local/dist/responses.js';

// Synthetic transport only: these tests never read credentials or contact OpenAI.
const fakeToken = 'synthetic-oauth-token';
const encoder = new TextEncoder();
const signal = () => new AbortController().signal;
const event = (value, newline = '\n') => `data: ${JSON.stringify(value)}${newline}${newline}`;
const delta = (text) => ({ type: 'response.output_text.delta', delta: text });
const completed = { type: 'response.completed' };

function mockFetch(t, implementation) {
  const original = globalThis.fetch;
  globalThis.fetch = implementation;
  t.after(() => { globalThis.fetch = original; });
}

function stream(chunks, headers = { 'content-type': 'text/event-stream' }) {
  let position = 0;
  return new Response(new ReadableStream({
    pull(controller) {
      if (position === chunks.length) controller.close();
      else controller.enqueue(encoder.encode(chunks[position++]));
    },
  }), { headers });
}

test('Responses uses the public OAuth route and only the supported HTTP request fields', async (t) => {
  let requests = 0;
  mockFetch(t, async (url, init) => {
    requests++;
    assert.equal(url, 'https://api.openai.com/v1/responses');
    assert.equal(init.method, 'POST');
    assert.equal(init.redirect, 'error');
    const headers = new Headers(init.headers);
    assert.equal(headers.get('authorization'), `Bearer ${fakeToken}`);
    assert.equal(headers.get('accept'), 'text/event-stream');
    assert.equal(headers.get('content-type'), 'application/json');
    assert.deepEqual(JSON.parse(init.body), {
      model: 'synthetic-model',
      input: [{ role: 'user', content: 'A synthetic test prompt.' }],
      instructions: 'A synthetic developer instruction.',
      store: false,
      stream: true,
    });
    return stream([event(delta('Completed output.')), event(completed)]);
  });
  const observed = [];
  const result = await streamResponse(fakeToken, {
    model: 'synthetic-model',
    input: 'A synthetic test prompt.',
    instructions: 'A synthetic developer instruction.',
    // Even dynamically supplied unsupported fields cannot enter the wire body.
    temperature: 1,
    max_output_tokens: 10,
    previous_response_id: 'synthetic-prior-response',
    metadata: { synthetic: true },
    onDelta: (text) => observed.push(text),
  }, signal());
  assert.equal(requests, 1);
  assert.deepEqual(observed, ['Completed output.']);
  assert.deepEqual(result, { text: 'Completed output.' });
});

test('explicit message history remains an array and instructions may be omitted', async (t) => {
  const history = [
    { role: 'developer', content: 'Context.' },
    { role: 'user', content: 'Question.' },
    { role: 'assistant', content: 'Previous answer.' },
  ];
  mockFetch(t, async (_url, init) => {
    assert.deepEqual(JSON.parse(init.body), {
      model: 'synthetic-model', input: history, store: false, stream: true,
    });
    return stream([event(delta('Answer.')), event(completed)]);
  });
  assert.deepEqual(await streamResponse(fakeToken, {
    model: 'synthetic-model', input: history,
  }, signal()), { text: 'Answer.' });
});

test('system messages are rejected before the transport is invoked', async (t) => {
  mockFetch(t, () => { assert.fail('An unsupported system message must not be transmitted.'); });
  await assert.rejects(streamResponse(fakeToken, {
    model: 'synthetic-model', input: [{ role: 'system', content: 'Rejected.' }],
  }, signal()), (error) => error instanceof ChatGPTError && error.code === 'invalid_request');
});

test('model discovery filters visibility and preserves account catalog ordering', async (t) => {
  mockFetch(t, async (url, init) => {
    assert.equal(url, 'https://api.openai.com/v1/models');
    assert.equal(new Headers(init.headers).get('authorization'), `Bearer ${fakeToken}`);
    assert.equal(init.redirect, 'error');
    return Response.json({ models: [
      { slug: 'model-z', display_name: 'First in account order', visibility: 'list' },
      { slug: 'hidden-model', display_name: 'Hidden', visibility: 'hidden' },
      { slug: 'model-a', display_name: 'Second in account order', visibility: 'list' },
      { slug: 'unspecified-model', display_name: 'Unspecified visibility' },
    ] });
  });
  assert.deepEqual(await listModels(fakeToken, signal()), [
    { slug: 'model-z', displayName: 'First in account order' },
    { slug: 'model-a', displayName: 'Second in account order' },
  ]);
});

test('CRLF split across network chunks still completes and preserves text deltas', async (t) => {
  const source = event(delta('First '), '\r\n') + event(delta('second.'), '\r\n') + event(completed, '\r\n');
  // Each CR arrives separately from the following LF.
  const chunks = source.split(/(?<=\r)/);
  mockFetch(t, async () => stream(chunks));
  const observed = [];
  assert.deepEqual(await streamResponse(fakeToken, {
    model: 'synthetic-model', input: 'Synthetic prompt.', onDelta: (text) => observed.push(text),
  }, signal()), { text: 'First second.' });
  assert.deepEqual(observed, ['First ', 'second.']);
});

test('delta text and DONE without response.completed never establish success', async (t) => {
  mockFetch(t, async () => stream([event(delta('Partial output.')), 'data: [DONE]\n\n']));
  const observed = [];
  await assert.rejects(streamResponse(fakeToken, {
    model: 'synthetic-model', input: 'Synthetic prompt.', onDelta: (text) => observed.push(text),
  }, signal()), (error) => error instanceof ChatGPTError && error.code === 'stream_interrupted');
  assert.deepEqual(observed, ['Partial output.']);
});

test('a usage-limit failure after deltas preserves its code and cannot return partial success', async (t) => {
  mockFetch(t, async () => stream([
    event(delta('Partial output.')),
    event({ type: 'response.failed', response: { error: { code: 'subscription_sharing_usage_limit_exceeded' } } }),
  ], { 'content-type': 'text/event-stream', 'x-request-id': 'synthetic-request-1' }));
  const observed = [];
  await assert.rejects(streamResponse(fakeToken, {
    model: 'synthetic-model', input: 'Synthetic prompt.', onDelta: (text) => observed.push(text),
  }, signal()), (error) => {
    assert.ok(error instanceof ChatGPTError);
    assert.equal(error.code, 'subscription_sharing_usage_limit_exceeded');
    assert.equal(error.requestId, 'synthetic-request-1');
    assert.equal(error.retryable, false);
    return true;
  });
  assert.deepEqual(observed, ['Partial output.']);
});

test('response.incomplete is a distinct failure even when partial text exists', async (t) => {
  mockFetch(t, async () => stream([event(delta('Partial.')), event({ type: 'response.incomplete' })]));
  await assert.rejects(streamResponse(fakeToken, {
    model: 'synthetic-model', input: 'Synthetic prompt.',
  }, signal()), (error) => error instanceof ChatGPTError && error.code === 'response_incomplete');
});

test('an ended stream without a terminal event is interrupted', async (t) => {
  mockFetch(t, async () => stream([event(delta('Partial.'))]));
  await assert.rejects(streamResponse(fakeToken, {
    model: 'synthetic-model', input: 'Synthetic prompt.',
  }, signal()), (error) => error instanceof ChatGPTError && error.code === 'stream_interrupted');
});

test('network reader failure after a delta is interrupted', async (t) => {
  let reads = 0;
  mockFetch(t, async () => new Response(new ReadableStream({
    pull(controller) {
      if (reads++ === 0) controller.enqueue(encoder.encode(event(delta('Partial.'))));
      else controller.error(new Error('Synthetic reader failure.'));
    },
  }), { headers: { 'content-type': 'text/event-stream' } }));
  await assert.rejects(streamResponse(fakeToken, {
    model: 'synthetic-model', input: 'Synthetic prompt.',
  }, signal()), (error) => error instanceof ChatGPTError && error.code === 'stream_interrupted');
});

test('caller cancellation during a stream is reported as cancellation', async (t) => {
  const controller = new AbortController();
  mockFetch(t, async () => stream([event(delta('Partial.')), event(completed)]));
  await assert.rejects(streamResponse(fakeToken, {
    model: 'synthetic-model', input: 'Synthetic prompt.', onDelta: () => controller.abort(),
  }, controller.signal), (error) => error instanceof ChatGPTError && error.code === 'cancelled');
});
