# Project audit and submission increment

Reviewed 2026-09-30. Scope: the existing research, execution, manuscript, policy,
package, publication, preprint and revision workflows, followed by a narrow OJS
3.5 submission integration. Defects below were reproduced before correction.
Existing Pydantic models, HTTPX, native locks and conversion libraries were reused;
no runtime dependency or scientific record migration was added.

| Reproduced problem | Implemented correction |
| --- | --- |
| Unsupported quantitative assertions in section headings or metric descriptions passed manuscript integrity | Apply the existing prose assertion checks to these rendered text fields; preserve valid metric identifiers and unit notation |
| Searches and CLI DOI imports using stale Study snapshots silently dropped history or overwrote current research flags | Lock the Study, load its current registered record and merge successful search/citation history |
| Obvious patient surveys and clinical participant interviews escaped the human-subject execution gate | Add specific participant/clinical descriptors, including demonstrated Korean terms; keep ordinary software literature surveys and parser benchmarks allowed |
| Declared experiment output cleanup could delete a declared input before execution | Reject overlapping declared input/output paths at registration |
| Stored policy values could be rebound while the reviewed specification remained unchanged | Bind venue, values, evidence, origins and freshness settings to the preserved reviewed specification |
| A database commit acknowledgement failure could delete already committed compiled/package/preprint artifacts | Delete a published artifact only when a read confirms its exact commit binding is absent; retain evidence on unknown outcomes |
| Rehashed native PDF/TeX/DOCX files could disagree with preserved conversion receipts | Verify each recorded source and native output digest and the exact required format set |
| An attestation could become outdated after a new actual preprint posting | Revalidate the complete current preprint fact set at the outbound final-submit boundary; preserve genuinely observed journal receipts |

The rejected-feedback increment also closes a missing workflow: an actual
`REJECTED` referee report can produce a distinct child manuscript in the same
Study. Existing edits, experiment evidence, author approval and new-venue package
commands are reused. Original scientific freezes and the rejected journal history
remain intact. Another active journal submission blocks further feedback edits
and approval. Same-journal revision delivery still requires an actual `REVISION`
decision.

## OJS contract and delivery review

The implemented client uses the maintained official OJS/PKP 3.5 source, with
pinned protocol references in [submission reuse](submission-reuse.md). Contract
review found and corrected assumptions that would fail on an actual installation:
the submission's section is a publication field; embedded publications are
summaries; file/contributor collections use wrapped `items`; author file resource
IDs differ from storage IDs; and submitted dates do not carry the site's timezone.

Delivery binds the immutable ready package, actual journal API context, canonical
metadata derivatives and explicit reviewer file genres. Blinded metadata uses the
existing identity redaction alongside blinded native files. Administrative files
and the entire package ZIP are excluded from automatic reviewer uploads. Actual
contributors, custom declarations and forms remain author-reviewed in the journal
interface.

Full remote inspection is serialized, includes the current publication, exact
contributor roster and file bindings, and is rechecked after live policy/author
approval. Two local plans cannot modify the same bound journal draft. Every
mutating request has a durable intent. Ambiguous validation or final submission
keeps the Study slot occupied, blocks duplicate submission/cancellation and uses
read-only provider reconciliation. A successful status code alone does not create
a local submitted fact: a separate provider read must confirm identity, submitted
date and completed submission progress.
Author-confirmed local recovery validates and imports preserved consecutive event
evidence after database rollback/acknowledgement failure, without repeating a
remote operation. Exact buffered upload bytes are checked before the HTTP request.

OJS does not provide a documented conditional final-submit lock. A person or
plugin could change a remote draft between the final inspection and provider
operation. The adapter checks the latest observable facts and provider validation;
it does not claim a cross-system atomic transaction or universal journal support.

## Repeatable verification

GitHub Actions runs all test files in four complete shards on Windows and Ubuntu,
using pinned official actions, Python 3.12 and actual installed document converters.
The external Pandoc fixture now works across supported test platforms instead of
silently skipping exports outside one Windows checkout layout. Module-mode CLI
invocation exposes the same portal commands as the installed console entrypoint.

Provider tests use clearly synthetic HTTP transports and credentials. The portal
smoke runs genuine corpus experiments, scientific checks and native exports with
a synthetic journal API; it does not contact a real journal or claim a live
authenticated acceptance test. Final measured test and smoke results are recorded
in [implementation status](status.md).

Remaining target-specific work: authenticated acceptance against the user's
actual OJS journal, its custom required fields and contributor workflow, and
review-round-aware revision uploads. ScholarOne, Editorial Manager and arXiv
upload remain unsupported. Human factual approval and actual final Submit remain
explicit author actions.
