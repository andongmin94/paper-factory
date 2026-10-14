import { PUBLICATION_VENUES, getPublicationVenue, type PublicationCatalog, type PublicationTarget } from '../shared/venues.js';

export const repositoryAuthoringPurpose = 'Repository publication authoring policy v2. ';
export const repositoryReferencePurpose = 'Frozen repository publication target; primary reference-selection policy v2. ';

const commonGuidance =
  'Write the article title, abstract and complete manuscript in English; planning explanations and reviewer reasons may use the goal language. ' +
  'Develop one consequential engineering question and a supported practical contribution beyond a README summary. ' +
  'Use the actual retained source-analysis result, literal repository witnesses and inspected primary comparisons; distinguish findings, interpretation and implications. ' +
  'Static and qualitative analysis can support implemented-path, documented-design and observed corpus findings. It does not establish unobserved performance, adoption, exploitation, user effects or causal superiority. Do not require execution of every input repository. ' +
  'When comparing repository code with software documentation, distinguish the inspected documentation snapshot from the repository dependency declaration and any verified resolved runtime. If version compatibility was not verified, state that limitation explicitly; do not infer runtime behavior or version matching from a latest-document URL or access date. ' +
  'Explain enough of the actual source-reading procedure, scope and counterexamples for readers to check the lesson. Use a codebook only when it clarifies a real design decision. Do not invent manual analysis, independent coders, inter-rater reliability, author approval or validation. ' +
  'Disclose Paper Factory, the actual supplied model names, materially generated analysis and manuscript sections, and extent of AI use in Acknowledgments. ' +
  'Keep hashes, receipt IDs, model-call counts, collection diagnostics and submission-administration checklists outside scientific prose. ' +
  'Write literal repository paths and code identifiers as inline code so Markdown formatting cannot change their spelling. ' +
  'Uninspected precise venue rules, university credit and final author/editor approval remain unverified. ';

export function repositoryPublicationGuidance(target?: PublicationTarget | null, catalog?: PublicationCatalog) {
  if (!target) return commonGuidance + 'Choose and freeze one publication target from the supplied IEEE Software and IEEE Security & Privacy catalog. ';
  const venue = getPublicationVenue(target.venue_id, catalog?.venues);
  if (!venue) throw new Error('Unknown repository publication target');
  return commonGuidance + `The frozen publication target is ${venue.name}, article category ${target.article_category}. Do not switch it during writing or remediation. ` +
    `Audience/scope: ${venue.scope}. Required contribution: ${venue.contribution_expectation}. Analysis: ${venue.analysis_expectation}. ` +
    'The catalog records inspected scope and any verified numerical rules separately from editorial working budgets; do not claim working budgets are official limits. ' +
    (venue.verified_limits.word_count_scope === 'whole_article'
      ? 'The verified word range counts the complete article, including abstract, keywords, references, author biographies and table text, plus the fixed allowance for each table or figure. Allocate a margin inside both the minimum and maximum; substantive evidence-based explanation must meet the minimum without filler. '
      : 'When a fixed visual allowance applies to this body-word profile, replace table/figure text with that allowance and exclude references and author biographies. ') +
    'Apply this exact publication profile: ' + JSON.stringify(venue) + '. ';
}

export function repositoryVenueSelectionGuidance() {
  return 'Assess BOTH catalog venues exactly once in publication_target.candidates: IEEE Software and IEEE Security & Privacy. ' +
    'Choose one venue_id and an allowed Feature Article category based on the actual engineering question, achievable practical contribution and evidence method, then explain the selection. ' +
    'For each candidate reason propose a concrete reader problem, supported central lesson, existing evidence and necessary additional evidence. IEEE Software needs actionable design alternatives, costs and application conditions; IEEE Security & Privacy needs a concrete protection problem, threat and trust boundaries, mitigations and residual risk. If this repository has no consequential security/privacy issue, mark that candidate out_of_scope rather than inventing one. ' +
    'Use suitable for an appropriate planned study, needs_evidence for a missing substantial study basis, and out_of_scope for a topic/article mismatch. Suitable is not a claim of submission readiness or acceptance. ' +
    'Record ordinary planned literature readings or analysis tasks in missing_evidence even for a suitable planned target; their completion is assessed after collecting evidence and writing the actual manuscript. Substantial unavailable study foundations still mean needs_evidence. ' +
    'Do not choose a venue without practical contribution and evidence to justify its scope. A precise source-grounded design lesson can be suitable without a new theorem, representative multi-project corpus or execution experiment. ' +
    'CS/CS-education hiring recognition is conditional on the actual hiring field and publication type; do not assume all computing papers fit education-pedagogy positions. ' +
    'Exact inspected catalog: ' + JSON.stringify(PUBLICATION_VENUES) + '. ';
}

export const repositoryAnalysisGuidance =
  'Perform the planned source analysis now, using the complete retained source and relevant inspected comparisons. Return ANALYSIS RESULTS, not another plan or a manuscript. ' +
  'Define a small codebook whose dimensions match the preserved comparison_dimensions. Identify concrete analytical units and apply the defined dimensions to actual literal source witnesses. ' +
  'For every observation and finding, provide source evidence IDs and a bounded interpretation; every source evidence ID must resolve to an unchanged literal quote/path/SHA256 from the supplied complete source. ' +
  'Evidence IDs form an explicit hierarchy: each observation evidence_ids must be a subset of its enclosing unit evidence_ids; each finding evidence_ids must be a subset of the union of evidence_ids of the units named in its unit_ids. Every evidence_ids array and unit_ids array must contain unique existing identifiers. Declare each required source witness in source_evidence, then include it in the enclosing unit before an observation uses it. ' +
  'Link findings to the units that demonstrate them. Evaluate meaningful counterexamples or boundary cases with the retained evidence; distinguish an analytical hypothetical condition from an observed implementation. ' +
  'Compare with the actually inspected primary literature or comparison-purpose documentation using exact text hashes and quotes. Venue guidance is never scientific evidence. ' +
  'Develop the contribution from the comparison and findings, including when it applies and why it changes a design decision. A table of unrelated feature names is insufficient. ' +
  'Keep this analysis response compact: normally 4-6 representative units, the planned dimensions, 6-12 short literal source witnesses and 2-4 synthesis findings; use more only when essential to the research question. Reuse witness IDs rather than repeating quotes. These are working response budgets, not journal requirements. ' +
  'Use a bounded set of units and concise evidence quotes rather than duplicating entire files. Do not fabricate corpus-wide absence claims, counts, statistical confidence, human coding, executions, measured effects or scholarly priority. ' +
  'Every limitation must state the actual scope or interpretation constraint. Retain unresolved evidence gaps honestly; do not claim that collecting bytes validates scientific interpretation. ';
