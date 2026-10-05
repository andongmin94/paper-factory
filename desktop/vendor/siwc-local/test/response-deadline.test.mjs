import assert from 'node:assert/strict';
import test from 'node:test';
import { streamResponse } from '../dist/responses.js';

const encoder = new TextEncoder();
const event = (value) => encoder.encode(`data: ${JSON.stringify(value)}\n\n`);

function delayedStream(t) {
  let body;
  let requested;
  const headers = new Promise(resolve => { requested = resolve; });
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url, 'https://api.openai.com/v1/responses');
    const response = new Response(new ReadableStream({
      start(controller) {
        body = controller;
        init.signal.addEventListener('abort', () => {
          body.error(new DOMException('Synthetic cancellation', 'AbortError'));
        }, { once: true });
        body.enqueue(event({ type: 'response.output_text.delta', delta: 'partial' }));
      },
    }), { headers: { 'content-type': 'text/event-stream' } });
    requested();
    return response;
  });
  return { headers, complete() {
    body.enqueue(event({ type: 'response.output_text.delta', delta: ' complete' }));
    body.enqueue(event({ type: 'response.completed' }));
    body.close();
  } };
}

test('active SSE can complete after the former three-minute client cutoff', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const deadlines = [];
  t.mock.method(AbortSignal, 'timeout', milliseconds => {
    deadlines.push(milliseconds);
    const controller = new AbortController();
    setTimeout(() => controller.abort(new DOMException('Synthetic deadline', 'TimeoutError')), milliseconds);
    return controller.signal;
  });
  const delayed = delayedStream(t);
  const partials = [];
  const request = streamResponse('synthetic-access-token', {
    model: 'synthetic-model', input: 'Synthetic delayed completion', onDelta: text => partials.push(text),
  }, new AbortController().signal);
  const outcome = request.then(value => ({ value }), error => ({ error }));
  await delayed.headers;
  await new Promise(resolve => setImmediate(resolve));
  t.mock.timers.tick(181_000);
  delayed.complete();
  const result = await outcome;
  assert.equal(result.error, undefined);
  assert.deepEqual(result.value, { text: 'partial complete' });
  assert.deepEqual(partials, ['partial', ' complete']);
  assert.deepEqual(deadlines, [600_000]);
});

test('caller cancellation after SSE headers remains a failed partial response', async t => {
  const caller = new AbortController();
  const delayed = delayedStream(t);
  const partials = [];
  const request = streamResponse('synthetic-access-token', {
    model: 'synthetic-model', input: 'Synthetic cancelled response', onDelta: text => partials.push(text),
  }, caller.signal);
  await delayed.headers;
  await new Promise(resolve => setImmediate(resolve));
  caller.abort();
  await assert.rejects(request, { code: 'cancelled' });
  assert.deepEqual(partials, ['partial']);
});

test('the ten-minute SSE deadline still stops an unfinished partial response', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  t.mock.method(AbortSignal, 'timeout', milliseconds => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(new DOMException('Synthetic deadline', 'TimeoutError')), milliseconds);
    return controller.signal;
  });
  const delayed = delayedStream(t);
  const partials = [];
  const request = streamResponse('synthetic-access-token', {
    model: 'synthetic-model', input: 'Synthetic unfinished response', onDelta: text => partials.push(text),
  }, new AbortController().signal);
  const outcome = request.then(value => ({ value }), error => ({ error }));
  await delayed.headers;
  await new Promise(resolve => setImmediate(resolve));
  t.mock.timers.tick(600_001);
  const result = await outcome;
  assert.equal(result.value, undefined);
  assert.equal(result.error?.code, 'stream_interrupted');
  assert.deepEqual(partials, ['partial']);
});
