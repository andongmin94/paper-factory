# Phase 3 reuse and publication boundaries

Reviewed on 2026-09-30, before adding publication lifecycle or preprint code. The
existing dependency set, `Workspace` record store, immutable approved freezes,
venue policy captures and submission-package verification were inspected first.
Phase 3 requires no additional runtime dependency.

| Component | Official source and license/terms | Decision |
| --- | --- | --- |
| SQLite through Python `sqlite3` | [Python interface](https://docs.python.org/3/library/sqlite3.html), [transaction semantics](https://sqlite.org/lang_transaction.html), [SQLite public domain](https://sqlite.org/copyright.html) | Reuse the current local record store. Check competing submissions and commit the state change in one write transaction; `BEGIN IMMEDIATE` acquires the writer before the check. No ORM, distributed scheduler, workflow engine or new database server is necessary. |
| Existing Pydantic and policy/package modules | Repository dependencies and [Phase 2 decision](phase2-reuse.md) | Reuse strict records, official-source captures, approved-canonical hashes and verified package manifests. Separate a local author attestation from a recorded external submission. A withdrawal request retains the active submission slot until actual confirmation is recorded. |
| arXiv metadata API | [User manual](https://info.arxiv.org/help/api/user-manual.html), [API terms](https://info.arxiv.org/help/api/tou.html), [API access](https://info.arxiv.org/help/api/index.html) | The documented `export.arxiv.org/api/query` service returns Atom metadata, rather than submitting manuscripts. Descriptive metadata is CC0; article files retain their own licenses. Defer a metadata polling adapter: the current local workflow can record an identifier and an author-reviewed receipt without fetching unrelated articles. Any future adapter must observe one request per three seconds and one concurrent connection across machines under the user's control, and include the requested arXiv acknowledgment. |
| arXiv submission workflow | [Submission overview](https://info.arxiv.org/help/submit/index.html), [licenses](https://info.arxiv.org/help/license/index.html), [third-party submission](https://info.arxiv.org/help/third_party_submission.html) | Prepare locally for the author to review and upload using the official workflow. Registration, possible endorsement, moderation, license choice and final author action remain relevant. A journal package is not automatically an arXiv-ready source archive: arXiv's source and server-processing rules need their own verification. Record actual preprint confirmation separately from peer review. |
| arXiv SWORD/APP deposit API | [Official manual](https://info.arxiv.org/help/submit_sword.html) | A documented deposit API exists. Its manual names author registration, separate administrator authorization, a registered default license and authenticated deposits; its update section ends in 2013. Defer integration until the actual account's present authorization and service behavior can be verified. Do not assume that an ordinary metadata API or a successful local package grants deposit access. No credentials, authorization request or upload was performed in this review. |
| PKP Open Journal Systems / Open Preprint Systems | [API documentation source](https://github.com/pkp/pkp-docs/blob/main/dev/api/index.md), [maintained OJS API specification](https://github.com/pkp/ojs/blob/main/docs/dev/swagger-source.json), [OJS GPL v3 license](https://github.com/pkp/ojs/blob/main/docs/COPYING) | OJS and OPS expose maintained APIs; the OJS specification documents submissions, files and editorial decisions. Access requires authentication and installation configuration, and permissions vary by role/version. Defer a concrete adapter until an actual journal and authorized account are selected; pin that installation's API version. Do not implement a fictional universal publisher API or copy platform code into this MIT project. The hosted PKP documentation returned an access challenge during this review; official repository documentation was readable. |
| Crossref DOI metadata | [REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [relationship schema](https://www.crossref.org/documentation/schema-library/markup-guide-metadata-segments/relationships/) | Reuse the existing Crossref adapter for citation verification. The public API needs no sign-up and exposes metadata; abstracts can retain copyright. Preprints can be connected to published articles with `isPreprintOf` / `hasPreprint` relationships, but metadata availability or a relationship is not an editor's submission, rejection or withdrawal receipt. Do not use metadata search to clear the active-submission guard. |
| DataCite DOI metadata | [Public REST API](https://support.datacite.org/docs/rest-api), [metadata and CC0](https://support.datacite.org/docs/getting-started-guides) | The public, unauthenticated JSON API retrieves Findable DOI records. Metadata is CC0. Defer a second DOI provider because Phase 3's explicit external receipts do not require broad metadata harvesting. No DOI registration/deposit account or paid service is created. |

Publication-state records describe evidence supplied and reviewed by the author.
An imported receipt is preserved with its bytes, hash, review identity, source
reference and observed time; the application cannot authenticate an arbitrary
local file as a message sent by an editor. Unknown status remains unresolved.
Confirmed rejection or confirmed withdrawal can release the local guard;
preprint posting never releases it or establishes peer-reviewed acceptance.

The guard covers submission records in the selected workspace, including papers
belonging to the same study. A conservative comparison also detects exact reuse
of approved measurement evidence from the same source snapshot under a different
study ID. This does not establish semantic similarity, detect translated prose,
or decide whether related studies are scientifically distinct. It cannot discover
an unrecorded external submission or coordinate independently copied workspaces.
The final author attestation must
therefore explicitly cover submission elsewhere. Future browser/API adapters
must acquire the same guard before the external action, preserve uncertainty
after interrupted uploads, and distinguish a draft/upload from the publisher's
final confirmation. Local test fixtures exercise these boundaries without
creating an external publication or sending messages to editors.
