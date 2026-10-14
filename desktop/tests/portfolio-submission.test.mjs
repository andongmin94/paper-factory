import assert from 'node:assert/strict';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const { outputFiles } = await build({
  entryPoints: [fileURLToPath(new URL('../src/main/portfolio-submission.ts', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'esm', target: 'node22', plugins: [{
    name: 'genuine-engine-error', setup(builder) {
      builder.onResolve({ filter: /^\.\/engine\.js$/ }, () => ({ path: new URL('../dist/engine.js', import.meta.url).href, external: true }));
    },
  }],
});
const { portfolioSubmissionSite, portfolioScience, verifyPortfolioSubmissionChange, submissionRecordsPreserved } =
  await import('data:text/javascript;base64,' + Buffer.from(outputFiles[0].text).toString('base64'));
const { artifactFormat, isReadableArtifactId } = await import('../dist/artifacts.js');

// Synthetic administration fixtures, never an actual author's approval or submission.
function workflow() {
  const submission = { status: 'prepared', selected_venue_id: 'ieee-security-privacy',
    preparation: { artifact_id: 'repository-portfolio-submission-preparation-1', sha256: 'a'.repeat(64),
      current: true, author_biography: 'Synthetic immutable biography for guard verification.',
      confirmation: { artifact_id: 'repository-portfolio-submission-confirmation-1', sha256: 'c'.repeat(64) } },
    portal_record: null,
    history: [{ artifact_id: 'repository-portfolio-submission-event-1', sha256: 'b'.repeat(64), note: 'Prior immutable synthetic event.' }],
    candidates: [{ venue_id: 'ieee-security-privacy', portal_url: 'https://ieee.atyponrex.com/journal/sp-cs',
      guidelines_url: 'https://www.computer.org/csdl/magazine/sp/write-for-us/14680?title=Author%20Information&periodical=IEEE%20Security%20%26%20Privacy',
      prepare_available: true, missing: [] }],
  };
  return { repository_paper: { analysis_attempts: 2, analysis: { method: 'Preserved synthetic static analysis.' },
    portfolio: { analysis_sha256: 'd'.repeat(64), venues: [{ venue_id: 'ieee-security-privacy', draft_attempts: 2, review_attempts: 2,
      draft: { title: 'Preserved synthetic manuscript' }, review: { accepted: true } }], submission } },
    author_metadata: { value: { display_name: 'Synthetic Author', affiliation: 'Synthetic Institute', email: 'fixture@example.test' }, sha256: 'e'.repeat(64) },
    artifacts: Object.fromEntries(['repository-draft-1', 'repository-portfolio-submission-preparation-1', 'repository-portfolio-submission-event-1']
      .map(id => [id, { id, sha256: 'f'.repeat(64), size: 42 }])) };
}
const stateError = error => error.code === 'RESEARCH_STATE_INVALID';

test('submission site lookup returns only fixed official routes for a retained venue', () => {
  const paper = workflow().repository_paper;
  assert.equal(portfolioSubmissionSite(paper, 'ieee-security-privacy', 'portal'), 'https://ieee.atyponrex.com/journal/sp-cs');
  assert.match(portfolioSubmissionSite(paper, 'ieee-security-privacy', 'guidelines'), /^https:\/\/www\.computer\.org\//);
  for (const mutate of [
    value => { value.portfolio.submission.candidates[0].portal_url = 'https://attacker.example/submit'; },
    value => { value.portfolio.submission.candidates[0].portal_url += '?redirect=https://attacker.example'; },
    value => { value.portfolio.submission.candidates = []; },
  ]) {
    const changed = structuredClone(paper); mutate(changed);
    assert.throws(() => portfolioSubmissionSite(changed, 'ieee-security-privacy', 'portal'), error => error.code === 'SUBMISSION_SITE_INVALID');
  }
  assert.throws(() => portfolioSubmissionSite(paper, 'unretained-venue', 'portal'));
  assert.throws(() => portfolioSubmissionSite(paper, 'ieee-security-privacy', 'arbitrary'));
});

test('submission administration admits new receipts while preserving actual science and old file descriptors', () => {
  const before = workflow(), after = structuredClone(before);
  after.artifacts['repository-portfolio-submission-package-1'] = { id: 'repository-portfolio-submission-package-1', sha256: '1'.repeat(64), size: 100 };
  for (const role of ['photo', 'generated-submission-typ', 'generated-submission-table-layout-lua', 'generated-submission-pandoc-metadata-json']) {
    const id = `repository-portfolio-submission-${role}-1`;
    after.artifacts[id] = { id, sha256: '3'.repeat(64), size: 100 };
  }
  after.repository_paper.portfolio.submission.history.push({ artifact_id: 'repository-portfolio-submission-event-2', sha256: '2'.repeat(64), note: 'New synthetic event.' });
  assert.doesNotThrow(() => verifyPortfolioSubmissionChange(before, after));
  assert.deepEqual(portfolioScience(before.repository_paper), portfolioScience(after.repository_paper));
  assert.deepEqual(before.repository_paper.portfolio.submission.history, after.repository_paper.portfolio.submission.history.slice(0, 1));
});

test('submission changes cannot rewrite science, counts, author facts, old artifacts or prior receipt history', () => {
  const mutations = [
    value => { value.repository_paper.analysis.method = 'Changed interpretation'; },
    value => { value.repository_paper.analysis_attempts = 0; },
    value => { value.repository_paper.portfolio.venues[0].draft_attempts = 0; },
    value => { value.repository_paper.portfolio.venues[0].review_attempts += 1; },
    value => { value.repository_paper.portfolio.venues[0].review.accepted = false; },
    value => { value.author_metadata.value.display_name = 'Different author'; },
    value => { value.artifacts['repository-draft-1'].sha256 = '0'.repeat(64); },
    value => { delete value.artifacts['repository-draft-1']; },
    value => { value.artifacts['repository-draft-2'] = { id: 'repository-draft-2', sha256: '0'.repeat(64), size: 1 }; },
    value => { value.repository_paper.portfolio.submission.history[0].note = 'Rewritten event'; },
    value => { value.repository_paper.portfolio.submission.history = []; },
    value => { value.repository_paper.portfolio.submission.preparation.author_biography = 'Rewritten same receipt'; },
  ];
  for (const mutate of mutations) {
    const before = workflow(), after = structuredClone(before); mutate(after);
    assert.throws(() => verifyPortfolioSubmissionChange(before, after), stateError, mutate.toString());
  }
});

test('author updates can derive stale status and candidate holds without rewriting saved preparation or events', () => {
  const before = workflow().repository_paper, after = structuredClone(before);
  after.portfolio.submission.status = 'stale';
  after.portfolio.submission.preparation.current = false;
  after.portfolio.submission.candidates[0].prepare_available = false;
  after.portfolio.submission.candidates[0].missing = ['Current author output needs regeneration.'];
  assert.equal(submissionRecordsPreserved(before, after), true);
  for (const mutate of [
    value => { value.portfolio.submission.preparation.author_biography = 'Changed immutable biography'; },
    value => { value.portfolio.submission.history[0].note = 'Changed immutable receipt'; },
    value => { value.portfolio.submission.portal_record = { status: 'submitted' }; },
  ]) {
    const changed = structuredClone(after); mutate(changed);
    assert.equal(submissionRecordsPreserved(before, changed), false);
  }
});

test('only final manuscript and preparation package formats can be opened or downloaded', () => {
  for (const [role, extension] of Object.entries({ md: 'md', pdf: 'pdf', docx: 'docx', package: 'zip', manifest: 'json', metadata: 'json', 'cover-letter': 'txt' })) {
    const id = `repository-portfolio-submission-${role}-12`;
    assert.equal(artifactFormat(id).extension, extension);
    assert.equal(isReadableArtifactId(id), true);
  }
  for (const role of ['source', 'preparation', 'confirmation', 'event', 'docx-conversion', 'pdf-conversion', 'arbitrary']) {
    const id = `repository-portfolio-submission-${role}-1`;
    assert.equal(artifactFormat(id), undefined);
    assert.equal(isReadableArtifactId(id), false);
  }
  for (const suffix of ['0', '-1', '../paper', '1/raw', '01']) {
    assert.equal(isReadableArtifactId(`repository-portfolio-submission-pdf-${suffix}`), false);
  }
});
