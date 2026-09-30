# Official OJS submission integration

Research checked 2026-09-30. This increment reuses installed HTTPX and Pydantic,
the existing public-DNS/TLS pinning helpers, immutable submission packages, and
the existing publication journal. It adds no dependency, browser driver, account,
or vendor SDK. Provider development tests use HTTPX MockTransport and synthetic
credentials; no real journal was contacted or uploaded to.

## Adopt one actual provider

Implement OJS **3.5** against the maintained official `stable-3_5_0` source,
pinned at OJS `040e9163780bcf9ca5c614d8588688f6c324d4da` and its actual PKP library
submodule `8809a197de7c5f677428172bf5e6b4a5013460d6`. The journal administrator and
author must explicitly confirm the installed version and journal API base URL.
There is no invented `_version`, `_current_user`, or universal publisher endpoint.
Configuration admits only 3.5, and unexpected runtime response shapes block
progress; this is not remote certification of the server's version.
The official API source documents the actual submission routes below.
[Pinned OJS API specification](https://github.com/pkp/ojs/blob/040e9163780bcf9ca5c614d8588688f6c324d4da/docs/dev/swagger-source.json).

| Action | Journal API route | Request |
| --- | --- | --- |
| Read submission | `GET /submissions/{id}` | No body |
| Start draft | `POST /submissions` | Explicit `sectionId`, `locale`, optional `userGroupId` |
| Read full metadata | `GET /submissions/{id}/publications/{pubId}` | No body |
| Edit metadata | `PUT /submissions/{id}/publications/{pubId}` | Reviewed multilingual title, abstract, keywords, optional primary contact |
| Read uploaded files | `GET /submissions/{id}/files` | No body |
| Upload initial file | `POST /submissions/{id}/files` | Multipart `file`, explicit `genreId`, `fileStage=2` |
| Read contributors | `GET /submissions/{id}/publications/{pubId}/contributors` | No body |
| Create contributor | `POST .../contributors` | Explicit reviewed names, email, author group, affiliations |
| Edit contributor | `PUT .../contributors/{contributorId}` | Complete reviewed contributor fields |
| Validate stored draft | `PUT /submissions/{id}/submit` | JSON `{"_validateOnly": true}` |
| Final submission | `PUT /submissions/{id}/submit` | Explicit author approval; optional `confirmCopyright=true` |

The source permits authors on submission, metadata, contributor and final-submit
routes, with separate submission access and publication-edit policies. An API
token does not confer permission to someone else's submission. Validation uses
the installed journal's required metadata/file genres and plugin hooks; local
checks do not replace it. Copyright confirmation records acceptance and must
come from the actual author's approval of the journal notice. Contributor
creation can insert an author before affiliation validation returns HTTP 400;
that outcome requires inspection before any retry. The client does not request
ORCID verification emails or fabricate verified ORCIDs.
[Pinned submission controller](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/api/v1/submissions/PKPSubmissionController.php),
[pinned submission validation repository](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/classes/submission/Repository.php).

## Inspect source-defined responses

Submission `publications` are summaries. Read the full publication separately to
compare abstract and authors; read contributors for the exact roster. Contrary
to the Swagger array declarations, the pinned controllers return
`{"itemsMax": n, "items": [...]}` for both file and contributor lists. The adapter
checks counts, IDs, parent bindings and duplicate IDs. It retains nonsecret JSON
fields and redacts credential fields, including ORCID access/refresh tokens.
[Submission mapping source](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/classes/submission/maps/Schema.php),
[publication mapping source](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/classes/publication/maps/Schema.php),
[author schema](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/schemas/author.json).

The file response distinguishes the submission-file resource `id` from storage
`fileId`, plus submission ID, genre, stage and multilingual `name`. The server
fills an omitted name from the actual upload filename. Stage 2 is initial
submission; revision stage 15 additionally requires a valid review round and is
outside this narrow uploader. Final submission succeeds only with the matching
submission ID, empty `submissionProgress` and nonempty `dateSubmitted`; the
orchestrator then obtains a fresh independent read. Preserve the provider's
timezone-free `dateSubmitted` verbatim and use the UTC `received_at` for the
local observation, without guessing the journal's clock zone.
[File controller](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/api/v1/submissions/PKPSubmissionFileController.php),
[submission schema](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/schemas/submission.json).

## Local approval and transport boundaries

Persist only a `PF_OJS_API_TOKEN` environment variable reference, never the token.
Use bearer authentication with verified HTTPS, public DNS pinning and original
hostname TLS verification, no environment proxies, no redirects, bounded JSON
and file sizes, and no write retries. An unexpected success status, timeout,
redirect, malformed write response or server failure is an ambiguous outcome,
not permission to create a replacement draft or upload again. Preserve safe
operation metadata for reconciliation; provider error text and request bodies
must not appear in errors. The final local gate must bind author review to the
exact venue, package bytes, metadata, author roster and current provider draft.

OJS/PKP source is GPL v3; the client implements the public HTTP protocol
independently and copies no PHP implementation. This remains a local manuscript
workflow plus one concrete OJS adapter. Other publishers require their own
verified integrations. CAPTCHA, journal-specific payment/extra declarations,
unreviewed provider upgrades and unsupported required fields stop automated
progress and are completed in the genuine journal interface.
[Official source licensing notice](https://github.com/pkp/pkp-lib/blob/8809a197de7c5f677428172bf5e6b4a5013460d6/api/v1/submissions/PKPSubmissionController.php).
