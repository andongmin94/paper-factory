import assert from 'node:assert/strict';
import test from 'node:test';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/main/repository-recovery.ts', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'esm', target: 'node22' });
const { retainedScientificSections, completeManuscriptTail } =
  await import('data:text/javascript;base64,' + Buffer.from(outputFiles[0].text).toString('base64'));

// Synthetic transport fixtures only; these are not actual manuscript or research evidence.
const title = 'Synthetic interrupted manuscript';
const headings = ['Abstract', 'Introduction', 'Related Work', 'Method', 'Repository Analysis', 'Discussion',
  'Limitations', 'Actionable Insights', 'Conclusion'];
const sections = headings.map(heading => ({ heading, text: `${heading}: synthetic source analysis without observed execution. `.repeat(3) }));
const acknowledgments = 'Synthetic fixture: drafting assistance is disclosed without inventing human approval. Unicode 가 and escaped "quotes" remain unchanged. '.repeat(2);
const sourceEvidence = [1, 2].map(index => ({ id: `S${index}`, path: 'src/synthetic.js', sha256: 'a'.repeat(64),
  quote: `export const fixture${index} = "synthetic";\n// retained literal line`, interpretation: 'Synthetic interpretation of a retained source quote.' }));
const literatureEvidence = [{ source_id: 'synthetic-scholar', text_sha256: 'b'.repeat(64), quote: 'Synthetic retained scholarly quotation.',
  interpretation: 'Synthetic comparison without an empirical result.' }];
const documentEvidence = [{ source_id: 'synthetic-document', text_sha256: 'c'.repeat(64), quote: 'Synthetic retained official-document quotation.',
  interpretation: 'Synthetic documented behavior only.' }];
const completion = () => ({ acknowledgments, source_evidence: structuredClone(sourceEvidence),
  literature_evidence: structuredClone(literatureEvidence), document_evidence: structuredClone(documentEvidence), revision: null });
const completeSections = JSON.stringify({ title, sections: [...sections, { heading: 'Acknowledgments', text: acknowledgments }] }).slice(0, -1);
const sourceTail = `,"source_evidence":[${JSON.stringify(sourceEvidence[0])},{"id":"S2","quote":"unfinished`;
const interruptedEvidence = completeSections + sourceTail;
const recoveryError = code => error => error?.code === code;

test('unfinished Acknowledgments keeps the original protected-text binding shape', () => {
  const prefix = acknowledgments.slice(0, 95);
  const interrupted = JSON.stringify({ title, sections }).slice(0, -2) +
    ',{"heading":"Acknowledgments","text":' + JSON.stringify(prefix).slice(0, -1);
  const retained = retainedScientificSections(interrupted);
  assert.deepEqual(Object.keys(retained), ['title', 'sections', 'acknowledgmentsPrefix']);
  assert.deepEqual(retained, { title, sections, acknowledgmentsPrefix: prefix });
  const result = completeManuscriptTail(retained, completion());
  assert.deepEqual(result.sections.slice(0, -1), sections);
  assert.equal(result.sections.at(-1).text, acknowledgments);
});

test('a feature without a venue insight requirement recovers its complete evidence tail', () => {
  const scientific = sections.filter(section => section.heading !== 'Actionable Insights');
  const prefix = JSON.stringify({ title, sections: [...scientific, { heading: 'Acknowledgments', text: acknowledgments }] }).slice(0, -1) + sourceTail;
  const retained = retainedScientificSections(prefix);
  assert.deepEqual(retained.sections, scientific);
  assert.deepEqual(completeManuscriptTail(retained, completion()).sections.slice(0, -1), scientific);
});

test('complete venue-specific scientific sections remain protected during tail completion', () => {
  const scientific = [...sections.slice(0, -1), { heading: 'Validity', text: 'Synthetic corpus sampling and interpretation limits. '.repeat(3) }, sections.at(-1)];
  const prefix = JSON.stringify({ title, sections: [...scientific, { heading: 'Acknowledgments', text: acknowledgments }] }).slice(0, -1) + sourceTail;
  const retained = retainedScientificSections(prefix);
  assert.deepEqual(completeManuscriptTail(retained, completion()).sections.slice(0, -1), scientific);
});

test('readable Feature Article headings preserve complete prose and citation entries during tail completion', () => {
  const feature = ['Abstract', 'The developer decision', 'What the code shows', 'Costs and application limits']
    .map(heading => ({ heading, text: `${heading}: synthetic bounded design lesson with no asserted execution. `.repeat(3) }));
  const prefix = JSON.stringify({ title, sections: [...feature, { heading: 'Acknowledgments', text: acknowledgments }] })
    .slice(0, -1) + sourceTail;
  const retained = retainedScientificSections(prefix);
  assert.deepEqual(retained.sections, feature);
  const completed = completeManuscriptTail(retained, completion());
  assert.deepEqual(completed.sections.slice(0, -1), feature);
  assert.deepEqual(completed.source_evidence, sourceEvidence);
});

test('completed Acknowledgments protects its exact bytes and retains only complete evidence entries', () => {
  const retained = retainedScientificSections(interruptedEvidence);
  assert.equal(retained.acknowledgmentsComplete, true);
  assert.equal(retained.acknowledgmentsPrefix, acknowledgments);
  assert.deepEqual(retained.retainedEvidence, { source_evidence: [sourceEvidence[0]] });
  assert.equal(Object.hasOwn(retained, 'retainedRevision'), false);
  const result = completeManuscriptTail(retained, completion());
  assert.equal(result.title, title);
  assert.deepEqual(result.sections.slice(0, -1), sections);
  assert.equal(result.sections.at(-1).text, acknowledgments);
  assert.deepEqual(result.source_evidence, sourceEvidence);
});

test('complete entries across all three evidence arrays survive a later interrupted entry', () => {
  const prefix = completeSections + ',"source_evidence":' + JSON.stringify(sourceEvidence) +
    ',"literature_evidence":' + JSON.stringify(literatureEvidence) +
    ',"document_evidence":[' + JSON.stringify(documentEvidence[0]) + ',{"source_id":"incomplete';
  const retained = retainedScientificSections(prefix);
  assert.deepEqual(retained.retainedEvidence, { source_evidence: sourceEvidence, literature_evidence: literatureEvidence,
    document_evidence: documentEvidence });
  const result = completeManuscriptTail(retained, completion());
  for (const key of ['source_evidence', 'literature_evidence', 'document_evidence']) assert.deepEqual(result[key], completion()[key]);
});

for (const mutation of ['acknowledgments', 'sourceQuote', 'sourceDrop', 'sourceReorder', 'science', 'title']) {
  test(`evidence-tail completion rejects ${mutation} changes to protected input`, () => {
    const retained = retainedScientificSections(completeSections + ',"source_evidence":' + JSON.stringify(sourceEvidence));
    const value = completion();
    if (mutation === 'acknowledgments') value.acknowledgments += ' Extra disclosure.';
    if (mutation === 'sourceQuote') value.source_evidence[0].quote = value.source_evidence[0].quote.replace('\n', '\\n');
    if (mutation === 'sourceDrop') value.source_evidence.shift();
    if (mutation === 'sourceReorder') value.source_evidence.reverse();
    if (mutation === 'science') value.sections = structuredClone(sections);
    if (mutation === 'title') value.title = 'Unapproved new title';
    assert.throws(() => completeManuscriptTail(retained, value), recoveryError('MANUSCRIPT_RECOVERY_INVALID'));
  });
}

for (const key of ['literature_evidence', 'document_evidence']) {
  test(`completed ${key} entries cannot be changed during completion`, () => {
    const value = completion();
    const retained = retainedScientificSections(completeSections + ',"source_evidence":' + JSON.stringify(sourceEvidence) +
      ',"literature_evidence":' + JSON.stringify(literatureEvidence) + ',"document_evidence":' + JSON.stringify(documentEvidence));
    value[key][0].interpretation = 'Changed retained interpretation.';
    assert.throws(() => completeManuscriptTail(retained, value), recoveryError('MANUSCRIPT_RECOVERY_INVALID'));
  });
}

for (const revision of [null, { prior_draft_sha256: 'd'.repeat(64), changes: ['Synthetic retained correction.'] }]) {
  test(`a completed revision ${revision === null ? 'null' : 'object'} remains protected before the closing root brace`, () => {
    const value = { ...completion(), revision };
    const prefix = completeSections + ',"source_evidence":' + JSON.stringify(sourceEvidence) +
      ',"literature_evidence":' + JSON.stringify(literatureEvidence) + ',"document_evidence":' + JSON.stringify(documentEvidence) +
      ',"revision":' + JSON.stringify(revision);
    const retained = retainedScientificSections(prefix);
    assert.equal(Object.hasOwn(retained, 'retainedRevision'), true);
    assert.deepEqual(retained.retainedRevision, revision);
    assert.deepEqual(completeManuscriptTail(retained, value).revision, revision);
    value.revision = revision === null ? { prior_draft_sha256: 'e'.repeat(64), changes: ['Invented.'] } : null;
    assert.throws(() => completeManuscriptTail(retained, value), recoveryError('MANUSCRIPT_RECOVERY_INVALID'));
  });
}

test('an unfinished revision object is completed without claiming it was retained in full', () => {
  const prefix = completeSections + ',"source_evidence":' + JSON.stringify(sourceEvidence) +
    ',"literature_evidence":[],"document_evidence":[],"revision":{"prior_draft_sha256":"unfinished';
  const retained = retainedScientificSections(prefix);
  assert.equal(Object.hasOwn(retained, 'retainedRevision'), false);
  assert.equal(completeManuscriptTail(retained, completion()).revision, null);
});

test('a valid full JSON response missing its stream completion still protects all returned fields', () => {
  const prefix = JSON.stringify({ title, sections: [...sections, { heading: 'Acknowledgments', text: acknowledgments }],
    ...Object.fromEntries(Object.entries(completion()).filter(([key]) => key !== 'acknowledgments')) });
  const retained = retainedScientificSections(prefix);
  assert.equal(retained.acknowledgmentsComplete, true);
  assert.equal(Object.hasOwn(retained, 'retainedRevision'), true);
  assert.deepEqual(completeManuscriptTail(retained, completion()).sections.slice(0, -1), sections);
});

for (const tail of [',"unknown":[]', ',"source_evidence":[1]', ',"source_evidence":[{"bad":}]',
  ',"source_evidence":[],"source_evidence":[', ',"source_evidence":"not-an-array"', '}']) {
  test(`malformed or unrelated completed-tail data is refused: ${tail}`, () => {
    assert.throws(() => retainedScientificSections(completeSections + tail), recoveryError('MANUSCRIPT_RECOVERY_UNAVAILABLE'));
  });
}

test('incomplete or duplicate scientific sections never gain tail recovery', () => {
  for (const invalid of [sections.slice(0, 2), sections.slice(1), [...sections.slice(0, -1), sections[0]]]) {
    const prefix = JSON.stringify({ title, sections: [...invalid, { heading: 'Acknowledgments', text: acknowledgments }] }).slice(0, -1) + sourceTail;
    assert.throws(() => retainedScientificSections(prefix), recoveryError('MANUSCRIPT_RECOVERY_UNAVAILABLE'));
  }
});
