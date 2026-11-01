# Research, revision, and assessment

## Make the additional value inspectable

Select a question the actual material can answer and a decision that matters to the intended reader. Read the sources far enough to establish the central behavior, normal reachability, relevant guards, counterexamples, and boundaries. Record why cases were chosen. A bounded source construction can be valuable without being an execution, an exhaustive survey, or evidence of prevalence.

If several angles compete, [contribution-selection.md](contribution-selection.md) provides a short worked selection example. Reuse retained reading and source witnesses to rule out unsupported or low-value questions before investing in a full article.

Challenge the contribution with the closest existing method, including its strongest relevant guarantees and assumptions. Apply it fairly to the same supported cases. Explain what the existing method already establishes, what the article adds, and whether the additional work changes a decision. Agreement with established guidance remains a result; do not weaken a baseline to manufacture novelty.

State the supported result and the reader's resulting decision plainly before spending a full article on it. A narrow case may justify a useful integration lesson; make that lesson specific enough to distinguish it from a polished restatement of familiar advice. When the value remains unclear, narrow or reconsider the article rather than treating accurate citations and a completed template as a submission recommendation.

Separate source-declared behavior, static observations, executed observations, interpretation, and hypothetical applications. A recorded expectation does not by itself establish runtime harm. A worked policy is not an implemented, safe, or effective fix. Missing external evidence or an inaccessible paper is a research limitation, not proof that the project has reached an intrinsic ceiling.

For a revision, prefer changes that resolve a real inference or adoption problem: a missing premise, an unfair comparison, an unexplained state transition, an ambiguous result, a needed failure condition, or evidence readers cannot locate. Distinguish those from a new study requiring execution, another independent case, measurements, or a maintainer response. More prose, more checks, and a higher rating are not new evidence.

## Write for a reader, then freeze

Build the abstract around the problem, what was actually done, the supported result, and why that result changes a decision. Describe a static study as static without turning the abstract's conclusion into a catalogue of unclaimed discoveries. Introduce concrete actors, state changes, and consequences before using abstractions such as membership or restoration authority. Use technical terms when they improve precision; word lists and subjective AI-detection scores do not establish authorship or publication quality.

Perform one author editorial pass before freezing the article for independent review. Read the argument as the venue's intended reader: can that reader restate the problem, principal result, additional value over existing work, and practical consequence? Remove duplicate conclusions and sentences that preempt the same objection repeatedly. Each substantial section should advance the evidence or decision rather than reassert the contribution in new terms. If the central result cannot be explained clearly, resolve that problem before export instead of adding more defensive prose.

Place the study's general scope in the method and its consequential limits in the limitations discussion. Keep a local qualification where omitting it would confuse an observed result, a source-derived construction, or a proposed design. Consolidation must not turn a hypothetical repair into an implemented result or imply execution that did not occur. Retain useful case controls and refusal conditions; their purpose is to test the argument, not repeat a generic disclaimer.

Keep the venue-required AI-use acknowledgment truthful and proportionate: identify the actual tool, affected material or sections, and extent of assistance. Methodological facts such as unexecuted code belong in the study description and need not be repeated in the acknowledgment unless that repetition is necessary to describe the assistance. Do not conceal AI-generated material, relabel extensive generation as grammar correction, or invent human work to make the article sound more natural.

## Evidence-grounded review criteria

Use these criteria to judge the strongest useful manuscript supported by the inspected project and primary evidence, and its actual suitability for the selected venue. They are review dimensions, not numerical targets, publisher peer review or an acceptance predictor. A manuscript needs a worthwhile supported contribution, adequate evidence and a coherent argument for the intended reader; the absence of a detected error alone is insufficient. Material difficulty understanding the central result, or repetition that obscures its value, warrants `revise_before_submission` even when individual claims are correct. Distinguish missing research from the project's demonstrated limits rather than declaring a ceiling from an evidence gap.

The quality target is an internal recommendation to publish the article as written. A near-ready article requiring minor revision still falls short of that strict target. Decide whether the article's actual claims and the venue require further central evidence, a consequential comparison, a redesigned study or substantial rewriting, and distinguish those needs from localized corrections. Execution restrictions or a narrow scope do not make an essential gap nonblocking; neither does a static method automatically require experiments for every bounded claim.

| Criterion | What the reviewer judges |
| --- | --- |
| `contribution` | A consequential, specific advance in readers' decisions beyond existing guidance; a polished restatement is insufficient. |
| `evidence` | Accurate, adequate, inspectable evidence for central claims, with scope and confidence matching what was actually observed. |
| `method` | A traceable analytical procedure, selection rationale, counterexamples, and meaningful checks that another reader can follow. |
| `comparison` | Fair comparison with the closest existing work and alternatives, grounded in actual primary bodies and identifying additional value. |
| `practical_value` | Usable decisions, worked cases, costs, failure conditions, and residual risks for the intended practitioner. |
| `logic` | Evidence supports the argument and conclusions without an unsupported generalization or hidden premise. |
| `presentation` | The intended reader can restate the central problem, result and practical consequence; prose and visuals explain them precisely and economically, without repetitive caveats or conclusions obscuring the argument. |
| `venue_fit` | A compelling feature article for the selected magazine's audience, scope, and applicable article requirements. |
| `limitations` | Specific, consequential limits and alternatives integrated into claims and advice. |

## One independent review

Give a separate reviewer the complete frozen article, relevant raw sources and primary bodies, exact exported files when available, and this rubric. Do not provide prior ratings, a desired score, or a preferred winner unless the user specifically requested a comparison requiring that information. An independent technical review should check the claims, not merely the author's evidence summary.

The author and independent critic provide complementary scrutiny in a bounded pass. Do not turn their feedback into an automatic model-to-model revision loop, or infer that two agreeing models establish research validity. Review the argument and reader comprehension directly rather than asking the critic to make the article appear human-written. Name a particular second model only when its actual use is established.

Cover all nine criteria in the single assessment with uncertainty, short literal article anchors, evidence-based reasons and consequential remaining improvements. Lead with an internal `publication_recommendation` and `as_written_publication_target_met`, and retain `no_major_revision_target_met` as a separate diagnostic, using the distinctions below. Preserve the separate `recommendation` of `consider_submission`, `revise_before_submission`, or `not_recommended` for existing preparation tools, explaining submission suitability for the selected audience and article category. Retain essential factual, citation or source defects separately; an essential defect prevents an unqualified recommendation to consider submission. Explain which remaining issues are blocking and which are useful future research, without manufacturing new observations or novelty to remove the distinction.

| Internal publication recommendation | Meaning for the exact reviewed article |
| --- | --- |
| `accept` | Its contribution, evidence, comparisons and presentation warrant publication as written; no required article revision is identified. |
| `minor_revision` | Only identified, localized corrections remain; no new central evidence, consequential comparison, redesigned study or substantial rewriting is needed. List those corrections explicitly. |
| `major_revision` | At least one such substantive change is needed before recommending publication. State the unmet need and why it matters to the current claim. |
| `reject` | The current contribution, evidence or venue fit does not justify recommending publication; distinguish a different study from revision of this article. |

Set `as_written_publication_target_met` true only for `accept`. A `minor_revision` outcome is near-ready but does not meet the strict target; list the required localized corrections explicitly. Set the separate `no_major_revision_target_met` diagnostic true only for `accept` or `minor_revision`. None of these labels is a publisher decision, a prediction of first-round acceptance, or a probability estimate. Older reviews without these explicit judgments remain unassessed against the stronger target. A legacy `consider_submission` or a passing format/final-preparation report does not establish that target and must not be relabeled as doing so.

Numerical ratings are optional when useful or requested. If supplied, use integer scores from zero to ten across all nine criteria, retain uncertainty, and explain the evidence behind them. Scores and averages never determine readiness by a fixed threshold or override an essential defect. If a simple arithmetic mean is displayed, calculate it from all nine scores without rounding individual judgments or choosing a favorable subset. Keep the original assessment and reviewed article/output hashes, whether the assessment is qualitative or scored. Different one-pass reviewers are not a controlled paired comparison, and a score change does not prove improvement or deterioration. Do not call a replacement reviewer to obtain a preferred result.

Separate an independent agent review from human author approval and publisher peer review. If independent review is unavailable or interrupted, deliver its actual status rather than inventing an assessment or silently treating self-review as independent. Report content recommendation, native format checks, page inspection and human preparation separately; administrative completion and actual submission do not establish acceptance. After the one review, deliver the result and stop automatic rewriting or rating loops.

## Evidence and delivery record

Use ordinary files in a fresh research directory. A useful compact record identifies the source revision and byte hashes, retained primary-body identities and reading scope, exact article/export/review hashes, actual helper outcomes, known model identity, and unresolved limits. Existing counts and failures remain historical records. Current agent model use is not zero merely because no separate API instrumentation exists.

Keep long command recipes, source witnesses, and auxiliary policy calculations in an identified companion. The article must still explain its argument without requiring the companion to substitute for a missing result. Preserve original licenses when redistributing repository sources and respect third-party paper redistribution rights.

Preparation gaps belong beside the manuscript. Do not invent affiliation, contact, biography, photograph, funding, conflicts, rights, originality, author responsibility, or approval to pass a check. Content recommendation, native format compliance, page inspection, administrative readiness, actual submission, and acceptance are separate facts.
