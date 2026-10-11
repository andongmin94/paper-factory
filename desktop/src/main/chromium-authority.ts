// This closure is installed in a blank renderer before any untrusted script.
// The returned object is retained only as a CDP remote handle, never on window.
export function rendererAuthority(bindingName: string, nonce: string, kind: 'production' | 'experiment' | 'measurement') {
  'use strict'; // Survives toString() and CDP reevaluation outside the original ESM context.
  const apply = Reflect.apply, descriptor = Object.getOwnPropertyDescriptor, define = Object.defineProperty;
  const hasOwn = Object.hasOwn;
  const ownKeys = Reflect.ownKeys, prototype = Object.getPrototypeOf, objectPrototype = Object.prototype;
  const create = Object.create, setPrototype = Object.setPrototypeOf, ArrayClass = Array;
  const stringify = JSON.stringify, parse = JSON.parse, array = Array.isArray, finite = Number.isFinite;
  const wellFormed = String.prototype.isWellFormed;
  const PromiseClass = Promise, MapClass = Map, ErrorClass = Error, string = String;
  const mapGet = Map.prototype.get, mapSet = Map.prototype.set, mapDelete = Map.prototype.delete;
  const mapSize = descriptor(Map.prototype, 'size')!.get!;
  const createElement = Document.prototype.createElement, appendChild = Node.prototype.appendChild, head = document.head;
  const scriptSource = descriptor(HTMLScriptElement.prototype, 'src')!.set!;
  const addEvent = EventTarget.prototype.addEventListener;
  const body = document.body, fontSet = document.fonts, FontFaceClass = FontFace, Uint8ArrayClass = Uint8Array, decodeBase64 = atob;
  const loadFont = FontFace.prototype.load, addFont = FontFaceSet.prototype.add, hasFont = FontFaceSet.prototype.has;
  const getContext = HTMLCanvasElement.prototype.getContext, measureText = CanvasRenderingContext2D.prototype.measureText;
  const canvasFont = descriptor(CanvasRenderingContext2D.prototype, 'font')!.set!;
  const canvasDirection = descriptor(CanvasRenderingContext2D.prototype, 'direction')!.set!;
  const setText = descriptor(Node.prototype, 'textContent')!.set!;
  const getStyle = descriptor(HTMLElement.prototype, 'style')!.get!, setCss = descriptor(CSSStyleDeclaration.prototype, 'cssText')!.set!;
  const rect = Element.prototype.getBoundingClientRect, scrollWidth = descriptor(Element.prototype, 'scrollWidth')!.get!;
  const scrollHeight = descriptor(Element.prototype, 'scrollHeight')!.get!, removeChild = Node.prototype.removeChild;
  const pixelRatio = devicePixelRatio, frame = requestAnimationFrame;
  const loadedFonts = new MapClass<string, { family: string; face: FontFace }>();
  const initialCapabilities = { require: typeof (globalThis as unknown as Record<string, unknown>).require, process: typeof (globalThis as unknown as Record<string, unknown>).process };
  const binding = (globalThis as unknown as Record<string, (text: string) => void>)[bindingName]!;
  delete (globalThis as unknown as Record<string, unknown>)[bindingName];
  const send = (value: unknown) => apply(binding, undefined, [json(value)]);
  let failure: string | undefined;
  const fatal = (reason: string): never => { failure ||= reason; send({ nonce, op: 'fatal', reason }); throw new ErrorClass(reason); };
  let sequence = 0, selected: Function | undefined, owner: unknown;
  let path: string[] = [], chain: unknown[] = [];
  const pending = new MapClass<number, { resolve: (value: string) => void; reject: (error: Error) => void }>();
  const gate = (op: string, args: unknown[]) => new PromiseClass<string>((resolve, reject) => {
    const id = ++sequence;
    apply(mapSet, pending, [id, { resolve, reject }]);
    try { send({ nonce, id, op, args }); } catch { fatal('Capability payload is not serializable'); }
  });
  function immutable(target: object, name: PropertyKey, value: unknown) {
    const existing = descriptor(target, name);
    if (existing && !existing.configurable) fatal('Cannot restrict browser capability: ' + String(name));
    define(target, name, { get: () => value, set: () => fatal('Browser capability replacement: ' + String(name)), configurable: false });
  }
  const blocked = (name: string) => function () { return fatal('Forbidden browser capability: ' + name); };
  for (const name of ['fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'Worker', 'SharedWorker',
    'RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'WebTransport', 'AudioContext',
    'webkitAudioContext', 'alert', 'confirm', 'prompt', 'open', 'showOpenFilePicker', 'showSaveFilePicker',
    'showDirectoryPicker', 'requestFileSystem', 'webkitRequestFileSystem']) immutable(globalThis, name, blocked(name));
  for (const [target, name] of [[Navigator.prototype, 'sendBeacon'], [Element.prototype, 'requestFullscreen'],
    [HTMLInputElement.prototype, 'showPicker'], [HTMLInputElement.prototype, 'click'],
    [HTMLAnchorElement.prototype, 'click'], [HTMLFormElement.prototype, 'submit'], [HTMLFormElement.prototype, 'requestSubmit']] as const) {
    immutable(target, name, blocked(name));
  }
  for (const name of ['serviceWorker', 'mediaDevices', 'geolocation', 'clipboard', 'usb', 'serial', 'bluetooth', 'hid', 'credentials', 'storage']) {
    immutable(Navigator.prototype, name, undefined);
  }
  document.addEventListener('securitypolicyviolation', () => fatal('Content security policy violation'));
  apply(addEvent, globalThis, ['error', () => fatal('Uncaught renderer script error')]);
  apply(addEvent, globalThis, ['unhandledrejection', () => fatal('Unhandled renderer promise rejection')]);
  if (kind === 'experiment') for (const name of ['callProduction', 'retainFixture', 'readScientificInput', 'measureLayout']) {
    immutable(globalThis, name, (...args: unknown[]) => gate(name, args));
  }
  function json(value: unknown): string {
    let nodes = 0;
    const seen = new MapClass<object, boolean>();
    function visit(item: unknown, depth: number): unknown {
      if (++nodes > 100000 || depth > 32) fatal('JSON structure boundary exceeded');
      if (typeof item === 'number' && !finite(item)) fatal('Non-finite result');
      if (typeof item === 'string' && !apply(wellFormed, item, [])) fatal('Unsupported result string');
      if (item === null || typeof item === 'boolean' || typeof item === 'string' || typeof item === 'number') return item;
      if (typeof item !== 'object') return fatal('Result is not finite JSON');
      if (apply(mapGet, seen, [item])) fatal('Cyclic result');
      apply(mapSet, seen, [item, true]);
      if (!array(item) && prototype(item) !== objectPrototype && prototype(item) !== null) fatal('Result must contain plain JSON data');
      const copied = array(item) ? setPrototype(new ArrayClass((item as unknown[]).length), null) : create(null);
      const keys = ownKeys(item);
      for (let index = 0; index < keys.length; index++) {
        const key = keys[index]!;
        const property = descriptor(item, key)!;
        if (key === 'toJSON') fatal('Custom JSON projection is unsupported');
        if (typeof key !== 'string' || !hasOwn(property, 'value')) fatal('Result contains an accessor or symbol');
        if (!property.enumerable) continue;
        define(copied, key, { value: visit(property.value, depth + 1), enumerable: true, configurable: true, writable: true });
      }
      if (array(item)) for (let index = 0; index < (item as unknown[]).length; index++) {
        const property = descriptor(item, string(index));
        if (!property || !hasOwn(property, 'value')) fatal('Sparse or accessor array is not finite JSON');
      }
      apply(mapDelete, seen, [item]);
      return copied;
    }
    const copied = visit(value, 0);
    const text = apply(stringify, undefined, [copied]);
    if (typeof text !== 'string') fatal('Result has no JSON projection');
    return text;
  }
  function lookup() {
    let value: unknown = globalThis;
    const current: unknown[] = setPrototype(new ArrayClass(), null);
    for (let index = 0; index < path.length; index++) {
      const name = path[index]!;
      if ((typeof value !== 'object' && typeof value !== 'function') || value === null) fatal('Production selector owner is invalid');
      current[current.length] = value;
      const property = descriptor(value, name);
      if (!property || !hasOwn(property, 'value')) return fatal('Production selector requires own data descriptors');
      value = property.value;
    }
    if (selected) {
      if (value !== selected || current.length !== chain.length) fatal('Production export was replaced');
      for (let index = 0; index < current.length; index++) if (current[index] !== chain[index]) fatal('Production export owner was replaced');
    }
    return { value, current };
  }
  return {
    capabilities() { return json(initialCapabilities); },
    async installFonts(records: Array<{ path: string; family: string; content: string }>) {
      if (kind === 'experiment') fatal('Experiment cannot install fonts');
      for (const item of records) {
        const binary = apply(decodeBase64, undefined, [item.content]);
        const bytes = new Uint8ArrayClass(binary.length);
        for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index);
        const face = new FontFaceClass(item.family, bytes);
        await apply(loadFont, face, []);
        apply(addFont, fontSet, [face]);
        apply(mapSet, loadedFonts, [item.path, { family: item.family, face }]);
      }
      return json({ loaded: records.length });
    },
    async measureLayout(request: { text: string; font: string; font_size: number; width: number; direction: string }) {
      if (kind !== 'measurement') fatal('Layout measurement requires the pristine renderer');
      const loaded = request.font.startsWith('source:') ? apply(mapGet, loadedFonts, [request.font.slice(7)]) : undefined;
      if (loaded && !apply(hasFont, fontSet, [loaded.face])) fatal('Frozen font is absent');
      const family = loaded ? loaded.family : request.font.slice(7);
      const node = apply(createElement, document, ['div']) as HTMLDivElement;
      const style = apply(getStyle, node, []);
      apply(setCss, style, [`margin:0;padding:0;border:0;width:${request.width}px;font:${request.font_size}px ${family};direction:${request.direction};white-space:pre-wrap;overflow-wrap:normal;line-height:normal;`]);
      apply(setText, node, [request.text]);
      apply(appendChild, body, [node]);
      await new PromiseClass<void>(resolve => apply(frame, globalThis, [() => resolve()]));
      try {
        const box = apply(rect, node, []);
        const canvas = apply(createElement, document, ['canvas']) as HTMLCanvasElement;
        const context = apply(getContext, canvas, ['2d']) as CanvasRenderingContext2D;
        if (!context) fatal('Canvas measurement is unavailable');
        apply(canvasFont, context, [`${request.font_size}px ${family}`]);
        apply(canvasDirection, context, [request.direction]);
        const measured = apply(measureText, context, [request.text]);
        return json({ family, css_bounds: { width: box.width, height: box.height },
          scroll: { width: apply(scrollWidth, node, []), height: apply(scrollHeight, node, []) },
          canvas: { advance_width: measured.width, actual_left: measured.actualBoundingBoxLeft,
            actual_right: measured.actualBoundingBoxRight, actual_ascent: measured.actualBoundingBoxAscent,
            actual_descent: measured.actualBoundingBoxDescent }, device_pixel_ratio: pixelRatio });
      } finally { apply(removeChild, body, [node]); }
    },
    select(names: string[]) {
      path = names;
      const found = lookup();
      if (typeof found.value !== 'function') return fatal('Production selector is not callable');
      selected = found.value; chain = found.current; owner = chain[chain.length - 1];
      return selected;
    },
    loadClassic(url: string) {
      return new PromiseClass<void>((resolve, reject) => {
        const script = apply(createElement, document, ['script']) as HTMLScriptElement;
        apply(scriptSource, script, [url]);
        apply(addEvent, script, ['load', () => resolve(), { once: true }]);
        apply(addEvent, script, ['error', () => reject(new ErrorClass('Frozen classic script failed')), { once: true }]);
        apply(appendChild, head, [script]);
      });
    },
    invoke(fn: Function, text: string) {
      if (failure) fatal(failure);
      lookup();
      if (fn !== selected) fatal('Held production function differs');
      const args = apply(parse, undefined, [text]);
      let value: unknown, rejection: string | undefined;
      try { value = apply(fn, owner, args); } catch (error) {
        const message = error && (typeof error === 'object' || typeof error === 'function') ? descriptor(error, 'message') : undefined;
        rejection = typeof error === 'string' ? error : message && hasOwn(message, 'value') && typeof message.value === 'string' ? message.value : 'Original production exception';
      } finally { lookup(); }
      if (failure) fatal(failure);
      if (rejection !== undefined) return json({ ok: false, error: rejection });
      if (value && (typeof value === 'object' || typeof value === 'function') && descriptor(prototype(value) ?? value, 'then')) fatal('Asynchronous production result is unsupported');
      return json({ ok: true, text: json(value) });
    },
    deliver(id: number, ok: boolean, text: string) {
      const entry = apply(mapGet, pending, [id]);
      if (!entry) fatal('Unknown capability reply');
      apply(mapDelete, pending, [id]);
      if (ok) entry.resolve(text); else entry.reject(new ErrorClass(text));
    },
    async run(url: string) {
      const namespace = await import(url);
      const property = descriptor(namespace, 'default');
      if (!property || !hasOwn(property, 'value') || typeof property.value !== 'function') return fatal('Generated ESM must export run');
      const value = await apply(property.value, undefined, []);
      if (failure) fatal(failure);
      if (apply(mapSize, pending, [])) fatal('Experiment finished with unawaited capabilities');
      return json(value);
    },
  };
}
