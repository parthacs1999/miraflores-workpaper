# Phase 7 — Requirements Gap Closure and Product Hardening

## Scope

Phase 7 adds authorized live change tracking, personal checkpoints, atomic bulk operations with compensating undo, immutable evidence uploads, persistent threaded questions, and a single-engagement firm operations workspace. These are working backend/frontend features, not mock controls. The original PDF, computation/reference contract, PHASE1.md–PHASE6.md and existing application/security/database/test architecture were reviewed. The session-initialization fix from the intervening task is retained.

There is no tax-engine rerun, agency transport, legal signature, authenticated client portal, external notification delivery, paid service or invented additional engagement. The real packet remains **FILING BLOCKED**. This file is the requested engineering record; deployment, final hand-in documentation and video production have not begun.

Instructions.json SHA-256 is unchanged:
`ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`.

## Exact Phase 7 file manifest

Created:

| File | Responsibility |
|---|---|
| `backend/app/migrations/006_product_hardening.sql` | Immutable original files, commands/change index, personal checkpoints and audit-index triggers |
| `backend/app/services/product_service.py` | Scoped change recovery, policy-aware caches, uploads, discussions, bulk compensation, actual time and budgets |
| `backend/app/product_api.py` | Typed strict-session routes and bounded asynchronous long polling |
| `backend/tests/test_product_hardening.py` | 59 isolated backend acceptance cases, including parametrized file/security tests |
| `frontend/src/components/LiveUpdates.tsx` | Live metadata feed, reconnect, summaries and personal checkpoints |
| `frontend/src/components/ProductWorkspace.tsx` | Evidence, threaded discussion, bulk action and firm operations interfaces |
| `frontend/workflow-tests/phase7.spec.ts` | Seven strict-mode browser acceptance workflows |
| `PHASE7.md` | This engineering record |

Modified:

| File | Change |
|---|---|
| `backend/app/main.py` | Registers product routes under the existing boundary |
| `backend/app/migrate.py` | Schema-aware, transactional legacy-review change-index backfill; accurate CLI message |
| `backend/app/security.py` | Bounded request intake; operational administrator allowlist; area-restricted legacy aggregate protection; final assignment revalidation; encoded-original redaction |
| `backend/app/security_context.py` | Request-local active transaction context for dynamic evidence resolution |
| `backend/app/workflow_connection.py` | Propagates the originating transaction during dependency hooks |
| `backend/app/services/workflow_service.py` | Immutable entity scope guard; scoped overview; supplemental contributors/dependencies; blocking questions/uploads; transactional question invalidation and sign-off gates |
| `backend/app/services/change_analysis_service.py` | Supplemental review fingerprints; bypasses global caches for mutable, authorized live evidence |
| `backend/app/change_analysis_api.py` | Preserves historical resolver's typed HTTP 200 contract while withholding data outside an area-restricted assignment |
| `backend/app/services/evidence_service.py` | Typed attachment/question/discussion references in current authorized context; excludes them from packet-only historical replay |
| `backend/app/services/lifecycle_service.py` | Freezes supplemental evidence metadata, discussions and protected original bytes into new snapshots |
| `frontend/src/components/FirmWorkflow.tsx` | Collaboration/operations navigation, persistent live panel, metadata refresh, scoped readiness explanation and access-loss clearing |

No existing test was removed, weakened or edited. The session launcher, README and session regression files added in the preceding fix remain unchanged in this Phase 7 implementation. Existing earlier-phase working-tree changes and generated test/build artifacts are not additional Phase 7 source changes. No runtime dependency was added.

## Architecture

### Server-driven changes and “since I last looked”

The transport is **bounded long polling**, selected deliberately instead of SSE: the existing security middleware buffers JSON so it can mask nested values and revalidate the session before delivery. Bypassing that boundary for an indefinite stream would introduce a separate security path. A poll waits up to 20 seconds; the frontend uses an immediate handshake followed by 10-second polls and two-second error retries. No database transaction remains open while waiting.

An append-only SQL change index references the existing append-only workflow/review/adjustment/verification histories. It contains metadata, not copied source values or free-text audit payloads. Source-trigger writes occur in the same transaction as the original event. Existing events are backfilled once, without rewriting them. Future commits remain recoverable across process restarts; there is no in-memory event queue whose contents can be lost.

The index is paged by monotonic cursor. Responses scan at most 1,000 rows and emit at most 200 authorized events (frontend page size 100), with `has_more` and the last scanned cursor. Missed pages are recovered in order. There are no user-generated updates during a read, except normal session/access audit and first-use initialization. Cursors are scan positions, not counts of authorized issues; gaps can result from filtering and must not be interpreted as other engagements' contents.

Responses include summaries by workpaper area, event category, authorized document ID, finding, adjustment and review status. Associations use declared packet provenance/current workpaper metadata, not inferred tax correctness. Repeated source events describe separate audit actions, not duplicate underlying tax issues. The feed never transmits source amounts, message bodies, filenames, raw audit snapshots or free-text staff identities.

Every poll checks active engagement membership and current areas, including after a wait. The outer boundary checks cookie validity and assignment revision again before sending bytes. Cross-engagement events are excluded by SQL; area filtering occurs before metadata emission. Document associations outside the current assignment are omitted. Restricted users cannot fetch whole-engagement legacy graphs as an indirect bypass.

Personal checkpoints are keyed by real packet staff ID and engagement, protected by optimistic revisions, and append an audit event. They advance only through a valid database cursor and cannot move backwards within an unchanged scope. An assignment-scope change resets the effective checkpoint to zero. Checkpoints never change reviews or approvals. The frontend retains the latest 300 received changes, makes checkpoint advancement explicit, and preserves its last cursor through reconnects. Refreshing/opening a page does not automatically mark work reviewed.

Live events refresh visible firm metadata and product records while preserving input state. The explicit **Refresh current workspace** control remounts inspectors, with a warning to save edits first. Identity/masking switches clear views through the existing epoch; live-session/assignment loss clears the workspace rather than retaining old data on screen.

### Bulk operations and undo

Supported operations are deliberately explicit:

| Operation | Semantics |
|---|---|
| `acknowledge_findings` | Open current-v3 findings become `in_review`, with a mandatory note; never resolved |
| `acknowledge_documents` | Personal “seen” marker; document disposition, extraction and verification stay unchanged |
| `submit_records` | Submit complete draft/open workflow records for later independent approval |
| `assign_tasks` | Partner/admin assignment of open deadline tasks to active authorized practice staff |

The UI pages/searches eligible items and accepts up to 50 selections. Each item receives its own existence, scope, revision, state and semantic validation. All mutations, notifications, audit entries and dependency invalidations use a single serialized SQLite transaction. One invalid item rolls back the entire batch.

Idempotency keys are scoped to actor and engagement, bound to a canonical normalized request hash, and persist the original result. An exact retry returns the original effect identity; different content under the same key is rejected. The UI can retry the exact request after losing its response, including when the server already committed. Replaying an old key after compensation does not reapply its effect; current batch state remains in the workflow projection/history.

Undo is an **audited compensation**, not deletion or database rewind. It requires the original operator or an assigned partner, unchanged per-item revisions and current authorization. It appends new review/entity events and a compensated batch event. Finding acknowledgment returns to open; record submission returns to its prior preparation state; task ownership returns to the previous still-valid assignee. The original review projection is also captured in the batch audit before overwriting it. A later edit/approval prevents compensation. A resource bound into a submitted/accepted simulated filing cannot be undone through this route. The API has no bulk filing, approval, signature, payment or agency-reversal operation.

Compensation never restores an invalidated sign-off. SQLite's existing permanent invalidation guards remain in force, and restored workpaper values require fresh approval. Bulk acknowledgment does not bypass independent review, waive readiness or invent document verification.

### Evidence attachments

Original bytes are stored as **immutable SQLite BLOBs**, eliminating uploader-controlled server storage paths, symlinks and filesystem orphan races. The server generates the attachment ID. SHA-256, byte size, declared/validated media type, creator, timestamp, safe display filename and versioned metadata are recorded. Each upload must link to one or more valid findings, documents, adjustments, notes, workflow records or collaboration questions.

Intake limits and validation:

- Maximum 5 MiB per file, 100 MiB original-file storage per engagement, 8 MiB mutation request body. The body bound counts received bytes rather than trusting Content-Length.
- Allowlisted PDF, PNG, JPEG and UTF-8 plain text with matching extensions/media types. Path separators, traversal/dot segments, control characters, trailing dots/spaces and unsafe names are rejected.
- Strict base64 decoding; PDF signature/trailer and active/encrypted/embedded-content rejection; PNG signature/chunk bounds/checksums/header dimensions/data/trailer; JPEG signature/segment dimensions/scan/trailer; UTF-8/control/active-markup checks for text.
- Images have bounded dimensions. Formats are validated conservatively; this is not malware scanning, full format decoding or sanitization. Originals remain untrusted and never render inline in the app.

All original downloads require a current practice assignment, **all linked areas**, sensitive-data clearance, explicit reveal header and meaningful access purpose. An additional attachment-specific download audit is written transactionally. The browser verifies SHA-256 and downloads an octet-stream Blob; no public URL or inline preview is introduced. Unprocessed bytes cannot be safely field-masked, so uncleared staff receive metadata only and cannot download originals.

Original content is never replaced/deleted; metadata changes create audited revisions and reset support review. An independent reviewer must actually obtain the cleared, audited original before recording manual support review. This records `manual_support_review_not_extraction`; `processing` remains `not_extracted`. Uploading or finding the same number in a file does not verify a tax field. Unreviewed uploads block relevant sign-offs and real readiness.

Attachments contribute hashes, metadata, authors and links to relevant area manifests, reconciliation-review fingerprints and frozen snapshot dependencies. Unrelated areas remain valid unless they share a real/global dependency. A new immutable snapshot can include original bytes for self-contained examination support; the special encoded-original field is removed by default redaction, including inside downloads/packages. Only an authorized cleared reveal can include those bytes. Stored/delivered package hashes retain the Phase 6 distinction.

### Questions and colleague/client responses

Questions have immutable identities, area, owner, staff participants, optional explicit due date, references, blocking designation and audited metadata revisions. Metadata changes reopen preparation and notify participants; a blocking designation cannot simply be removed to bypass filing readiness. A changed owner must be active and assigned to the area.

Messages are immutable threaded records, with parent validation, source refs, actual staff operator and timestamp. Staff-mediated packet-client responses record the declared client separately and explicitly assert **not authenticated**. Participants or an assigned partner may respond/act; current area authorization always applies. New threads, messages and status/assignment changes create in-app notifications.

Workflow: `open → answered → awaiting_review → resolved`. An answered question must be submitted for resolution. Its preparer/responders cannot independently resolve it. Reopening or revising metadata requires a fresh response/review. Resolutions bind supporting attachments/messages, relevant adjustments/verifications/workpaper records, policy and assignments. A relevant change transactionally returns a resolved question to `awaiting_review`, preserves the old decision, notifies the owner and requires a fresh independent resolution. Reverting data never automatically resurrects that decision. Unresolved blocking questions block filing and scoped sign-offs.

Current evidence references `attachment:...`, `question:...` and `discussion:...` resolve to typed authorized results. Missing/inaccessible records return explicit unresolved reasons without content. Dynamic results bypass global immutable-packet caches. They are not injected into Phase 5 historical packet replay.

### Firm operations

Search/status covers only the **single supplied invented engagement CL-20417**. No synthetic real clients, engagement counts, actual hours or capacity assumptions are seeded. The workspace combines current assignments, visible staff workload, packet tasks, discussion/notice deadlines, blocking notes/questions and full readiness blockers. Administrators get operational metadata/counts rather than tax discussion bodies or time-entry notes; restricted staff see authorized areas only.

Budgets start from `firm.budget_hours`, preserving each original amount. Partner/admin overrides are immutable audit revisions. Buckets map explicitly to existing tax areas; a shared bucket is counted once. Actual time is recorded by the acting staff member as integer minutes, with work date, area, bucket and note. Only that staff member can revise/void it. Future actuals, mismatched area/bucket, forged IDs and totals above 24 hours per staff/day are rejected transactionally. Voids preserve history.

Totals use Decimal arithmetic: actual hours = active minutes / 60; remaining = current budget − exact actual hours. Display rounds to two decimal places; integer minutes remain authoritative. For example, 95 minutes against 3.5 hours displays 1.58 actual and 1.92 remaining; changing budget to 1.25 displays −0.33 remaining and over-budget. Actuals in restricted views include only authorized areas; they are not represented as complete firm totals.

Time/budget administration does not change tax computations or invalidate unrelated tax approvals. Actual evidence/questions do. No invoices, payroll, billing rates, external calendars or external notifications are implied.

## Additive database migration

Migration 006 leaves migrations 001–005 and existing tables/records intact. It adds:

| Table | Columns / invariants |
|---|---|
| `product_files` | `id`, `engagement_id`, `sha256`, `media_type`, `size`, `content`, `created_by`, `created_at`; bounded original size; UPDATE/DELETE blocked |
| `product_commands` | Actor/engagement/key composite primary key, request hash, original result JSON, timestamp; UPDATE/DELETE blocked |
| `product_changes` | Monotonic ID, engagement/area/category/resource/action/actor/time and source table/event ID; unique source identity; indexed engagement/cursor/area; UPDATE/DELETE blocked |
| `product_checkpoints` | Engagement/staff composite key, scope fingerprint, cursor, revision, update timestamp; mutable projection with append-only checkpoint audit |
| `product_schema_migrations` | Marker version 6 and installation timestamp |

Four triggers index new workflow, review, adjustment and field-verification events in the originating transaction. The first migration backfills existing events exactly once. The migration runner checks legacy review-table columns before adding review backfill, preserving even minimal legacy-schema regression fixtures. Backfill and marker are committed together. Existing audits are referenced, never deleted or rewritten.

Mutable product records reuse `workflow_entities` with kinds `p_attachment`, `p_question`, `p_message`, `p_document_ack`, `p_bulk`, `p_time` and `p_budget`. All revisions use append-only `workflow_events`. Generic entity identity/kind/area/engagement cannot be changed or reserved by a different resource type. New time IDs must be server-generated; a caller-supplied ID may only revise an existing owned time entry.

Read-only live-database backup verification applied all migrations twice, compared every original row, checked no change-index duplication, and ran integrity/foreign-key checks. At verification, the original database had one review/four review events, 27 workflow entities/events, one policy, ten sessions, 23 access events and empty adjustment/verification/reconciliation/sign-off/snapshot/package tables. All were preserved. After verification, the local backend was stopped, an additional private backup was retained, migration 006 was applied to the live local database twice, and every original row was compared again unchanged. The change index contains the 31 original workflow/review history events. Integrity and foreign keys passed. The backend was restarted in the same explicit local-only demo mode.

## API changes

All new paths are relative to `/api/product`. Bodies forbid unknown fields. Mutations use server-session actors, CSRF/Origin controls, documented rationale and optimistic revisions where applicable.

| Method | Path | Contract |
|---|---|---|
| GET | `/overview` | Authorized attachments, questions/messages, batches, seen markers and staff/client options |
| GET | `/changes?after=&wait_seconds=&limit=` | Filtered paged metadata, scoped associations/summaries, recovery cursor and checkpoint |
| POST | `/checkpoint` | Advance this staff member's cursor with `expected_revision` |
| GET | `/bulk/catalog?operation=` | Current eligible/authorized items with individual revision tokens |
| GET | `/bulk/history` | Authorized batch projections; administrators only see task-assignment batches |
| POST | `/bulk` | Atomic `operation`, `command_key`, selected IDs/revisions, rationale and optional task assignee |
| POST | `/bulk/{id}/undo` | Append compensating action if every item is still eligible/current |
| POST | `/attachments` | Filename/media/base64/title/area/links/rationale; server derives hash and size |
| POST | `/attachments/{id}/actions` | Version metadata or record independent, inspected support review |
| GET | `/attachments/{id}/download` | Cleared purpose-audited original; canonical base64 JSON, never public/inline |
| POST | `/questions` | New persistent discussion, ownership/participants/deadline/blocking/refs |
| POST | `/questions/{id}/metadata` | Version assignment/content/refs; reopens work and retains blocking constraints |
| POST | `/questions/{id}/messages` | Staff or explicitly mediated client response, optional reply parent and evidence |
| POST | `/questions/{id}/actions` | Request independent resolution, resolve, reopen |
| GET | `/history/{id}` | Authorized append-only before/after history; out-of-scope historical metadata snapshots withheld |
| GET | `/operations?q=` | Supplied engagement search, visible assignments/workload/deadlines/blockers/budget/actual |
| POST | `/time` | Actual minutes, work date, area/bucket; own revision/void with expected revision |
| POST | `/budgets` | Partner/admin budget revision retaining packet original |

Prior APIs retain their paths/IDs and normal whole-engagement contracts. Security hardening deliberately restricts legacy aggregate reads to entire-engagement assignments. `/api/overview` retains its envelope but withholds household details for restricted staff. `/api/workflow/overview` filters records/notes/tasks/sign-offs/notifications/areas. `/api/timeline-replay/evidence` preserves HTTP 200 plus its typed graph envelope for restricted staff, with an explicit unresolved `outside_assignment_scope` result and no source data. Other aggregate reads return 403. The isolated legacy test profile is unchanged.

## Security boundaries and operational limits

- Production remains fail-closed. Explicit local demo selection is not authentication or signature assurance. Phase 4 session revocation, credential epoch, cookie, Origin, CSRF, administrator separation and default masking remain mandatory.
- New route-specific authorization runs inside the transaction. The global boundary still covers all responses/errors, uses no-store/private and nosniff headers, masks nested histories, and rechecks the session/assignment before response delivery. Administrator exceptions enumerate operational paths, not the whole product prefix.
- Area permissions are enforced for reads, writes, retries, undo, linked evidence, downloads and historical metadata. Access to a current narrowed attachment scope does not expose its older broader-scope audit payloads.
- The change feed contains only filtered metadata. Its index does not copy source bodies or file bytes. Secret values, credentials and attachment content are not printed to logs. Cleared original downloads add explicit view audit records.
- SQLite append-only triggers protect application history; they do not make SQLite encrypted, externally notarized or resistant to an administrator replacing the database file. Original-file BLOBs contain sensitive bytes at rest. Existing production limitations around SSO/MFA, encryption, rate limiting and managed credential operations remain.
- File checks do not certify malware-free files. Active PDF mechanisms/unsafe formats are conservatively rejected, and downloads are untrusted originals. There is no automatic OCR, extraction, antivirus service or field-level verification of uploaded bytes. A deployment would need an isolated scanner/intake pipeline before offering inline previews or wider types.
- Long polling provides authorized prototype-scale collaboration, not distributed real-time infrastructure or multi-tenant firm hosting. The packet has one engagement; foreign-scope test fixtures are isolated tests only.
- Partial support is made visible rather than clearing readiness: unknown evidence, missing deadlines, restricted views, unsupported tax calculations, unverified uploads, stale decisions and original authoritative-return/client-authorization prerequisites remain explicit.

## Verification

The pre-Phase-7 working baseline was 450 tests: the requested 437 Phase 6 tests plus 13 session-initialization regression tests added in the intervening task. All remain passing. Phase 7 adds 59 backend and seven browser cases, for **516 passing tests, zero final failures** across all suites. Phase 7 implementation and required verification are complete within the documented prototype/security boundaries; the real packet remains filing-blocked.

| Check | Result |
|---|---|
| Full pytest | 474 passed, zero failures; final full run 102.61 seconds |
| Final targeted Phase 7 backend rerun | 59 passed, zero failures after final audit/association/scope checks |
| Strict Playwright | 28 passed, zero failures (1.5 minutes) |
| Legacy Playwright | 14 passed, zero failures (21.2 seconds) |
| TypeScript | Passed (`tsc --noEmit`) |
| ESLint | Passed (`npm run lint`) |
| Standalone webpack production build | Passed (`next build --webpack`; optimized routes generated) |
| SQLite preservation/idempotence/integrity/foreign keys | Passed on backup and live additive migration; all original rows unchanged |
| Instructions.json | Original SHA-256 unchanged |
| Actual local application smoke test | Passed: demo login, live handshake, upload/discussion empty states, bulk controls and packet-budget workspace; no business records created |

Backend tests cover old/new event indexing, personal scope-bound checkpoints, reconnect pagination, long-poll/write concurrency, session/assignment revocation, other-engagement/area exclusion, per-item rollback, idempotent retries, compensation/intervening approvals/submitted filing protection, immutable files/hashes/quotas, path and file-signature attacks, size/base64 limits, all six target types, cleared downloads/access audit, metadata history scopes, typed resolver/package masking, discussion threading/ownership/client assurance/independence, stale resolution invalidation, readiness/sign-off blockers, Decimal budgets/time/voids/daily concurrency, API guards, append-only storage, transaction rollback and migration preservation.

The browser suite exercises actual controls for upload/download/manual review, two separate staff contexts and reconnect/checkpoints, committed-but-lost bulk response retry/undo, threaded mediated-client/colleague responses and independent clearance, budgets/time/search/admin assignment compensation, malicious file/uncleared/area/admin denial and scoped sign-off invalidation. All 21 preexisting strict and 14 legacy browser tests remain unchanged.

During development, checks caught a legacy minimal-schema backfill assumption, an overbroad historical-route denial, a missing initial heartbeat when a checkpoint had no unseen events, and new-test setup/synchronization/JSX issues. They were fixed in code or by making new tests wait for actual writes/use legitimate sign-off prerequisites. Existing assertions were not weakened. Existing Starlette/httpx and Node color-environment warnings remain.

Commands:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
```

From `frontend`:

```sh
./node_modules/.bin/tsc --noEmit
npm run lint
npm run build -- --webpack
npm run test:e2e
npm run test:e2e -- --config=playwright.workflow.config.ts
```

All tests use isolated databases/private servers. No test fixture marks the real packet filing-ready. SQLite verification backs up the real database read-only, runs migrations twice, compares original table rows, and checks `PRAGMA integrity_check`/`PRAGMA foreign_key_check`.

## Complete demonstration workflow

Use the existing explicit local launcher, preferably with a separate demonstration database. From the repository root in terminal one:

```sh
cd backend
REVIEW_DB_PATH=/private/tmp/miraflores-phase7-demo.db .venv/bin/python run_secure.py --demo
```

Terminal two, from the repository root:

```sh
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Use `http://localhost:3000`; keep both hosts as localhost. Stop any older server occupying the port. The explicit demo flag remains local-only and rejects conflicting production settings. No session/CSRF/security bypass is needed.

1. Select **st-01 Priya**, confirm demonstration identity assurance and FILING BLOCKED. The **Since I last looked** panel connects immediately, then waits for committed changes. Expand summaries to inspect area/document/finding/adjustment/review associations. Choose **Mark displayed changes seen**, wait for checkpoint advancement and reload; prior acknowledged events stay acknowledged only for Priya.
2. Open a separate browser context/profile as **st-02 Daniel**. In Priya's page choose **Pause live updates**. In Daniel's or Priya's other authorized working context create an area-specific question/record. Reconnect the paused page: missed events arrive without manually refreshing or losing the cursor. Independent users' checkpoints remain separate. Session/assignment loss clears the affected workspace.
3. As Priya open **Collaboration → Evidence Attachments**. Choose business, enter a title/rationale, select target document D14 and upload a safe `.txt` source file. Inspect immutable ID, SHA-256, size, links, `not_extracted` and `unverified`. Invalid PDF signatures, path-like names, active markup and oversized inputs are rejected.
4. Switch to Daniel, open the same attachment, enter a meaningful original access purpose, download and inspect it. The browser verifies SHA-256; the access log records the original view. Enter a review rationale and record independent support review. Processing still says not_extracted. Review history shows upload and review, not fabricated OCR/field confirmation.
5. As Priya edit attachment metadata/title/links and save a revision. Original bytes/hash remain fixed; support review resets. Affected signatures/review decisions/snapshots require fresh review. An unrelated payments signature remains current unless there is a real shared dependency. The unreviewed evidence remains a readiness blocker.
6. In **Questions & Responses**, create a blocking business question owned by st-01 with staff participants `st-01, st-02, st-03`, explicit due date and references such as D14 or the attachment ID. Use the question ID as an attachment target if desired. A metadata edit can reassign ownership/change deadline/refs, but cannot remove a blocking designation.
7. Record a response with declared client cu-01: it is visibly staff-mediated, not authenticated. Copy the generated discussion ID into the reply-parent field for a colleague follow-up. Responses keep authors, evidence and parent identities. Cross-thread parents are rejected. Request resolution; any preparer/responding staff member attempting to resolve their own work is rejected. Switch to independent **st-03 Helen**, document review and resolve. History and in-app notifications persist.
8. Revise supporting attachment metadata or relevant workpaper evidence after resolution. The discussion returns to awaiting_review in the same transaction, retains its prior resolution and blocks filing again. Reverting data does not revive the old resolution. A fresh independent review is required.
9. In the existing **Diligence** screen create two complete preparation records with applicability/answer/authority/evidence. In **Collaboration → Bulk Actions**, select `submit_records`, search those titles, select both and enter rationale. Apply the atomic action. Incomplete/stale/inaccessible items prevent the whole operation. Independent approval still happens through the established review workflow.
10. Choose **Undo with compensation** before later changes/filing. Both records return to preparation with new audit events; invalidated signatures stay invalid. A subsequent independent approval or submitted/accepted frozen filing blocks unsafe compensation. Finding acknowledgment similarly means in_review, while document acknowledgment means seen and never changes the 74-document accountability classification.
11. To simulate losing an HTTP response after commit, the automated browser test drops that response and uses **Retry identical bulk request**. It receives the original batch identity, with no duplicate effect. Changing the request under the same key is rejected.
12. Open **Firm Operations**. Search CL-20417 or household name/status; unmatched searches return no engagements. Only the supplied invented engagement is available. Inspect visible assignments/workload, packet/discussion/notice deadlines, blocking notes/questions and filing readiness reasons.
13. As Priya choose business bucket/area and record 95 actual minutes for today's date with rationale. Inspect 1.58 actual hours versus original 3.5 budget and 1.92 remaining. Edit or void your own entry and inspect history; other staff cannot rewrite it. No future actuals or more-than-24-hour staff/day entries are accepted.
14. Switch to **st-05 administrator**, open Firm Operations, enter rationale and revise business budget to 1.25. Original packet 3.5 remains visible; 95 minutes displays −0.33 remaining/over budget. Admin sees operational amounts/status, not tax discussion bodies or time-entry notes. In its Bulk Actions tab assign open packet tasks to an active scoped staff member; inspect notifications/history and compensate the assignment if still unchanged.
15. As administrator/partner use existing Assignments to give st-04 only business access. Marcus sees scoped collaboration/operations metadata, masked values and no unauthorized areas. Raw originals are unavailable without clearance, even if a download ID is known. Legacy whole-return endpoints are denied; the historical resolver returns a typed unresolved scope reason rather than source data. Admin cannot fetch tax collaboration/change-feed/original endpoints.
16. Finish in **Readiness**. Original professional/tax/document/signature prerequisites and new unresolved-question/unreviewed-upload blockers remain. No seen marker, bulk operation, uploaded file, staff-mediated response or simulated filing clears authoritative readiness.

## Original PDF gap classification after Phase 7

These classifications describe the packet-backed prototype, not a claim of authoritative tax practice or production deployment. “Implemented” includes the expressly requested simulation boundary where noted.

| Original requirement | Classification | Coverage / remaining boundary |
|---|---|---|
| Trace numbers to exact printed source fields; simulated source documents | Implemented for supported packet provenance | Typed resolver, lineage, simulated documents and ambiguity-aware field verification; invalid/missing provenance is explicit |
| Reverse document tracing and why a document was not used | Implemented | All 74 packet documents retain distinct evidence-based dispositions and supported indirect destinations |
| Record how values were verified | Implemented | Persistent method/source/verifier/time/audit; automatic matching remains distinct from CPA attestation; uploaded bytes remain unextracted |
| Attach any file/message/note as evidence | Partially implemented | Secure allowlisted original uploads, persistent discussions/notes and typed links; arbitrary unsafe/archive/office formats and automatic extraction are intentionally excluded |
| Link related items across return, years and related returns | Partially implemented | Packet lineage, prior-year pointers, related-return facts and carryover provenance work; no general multi-return editing or computed next-year workspace |
| Show tax computations, reconcile without trusting the engine, handle large detail | Implemented within supplied methods | Original calculations/asset/sales detail and independent supported comparisons exist; unsupported inputs/results remain explicit, not fabricated |
| Complete books-to-tax, state split, basis/limits and every CPA schedule | Partially implemented / unsupported where inputs are missing | PHASE3 rule coverage remains; authoritative outside basis, full passive limits/AMT, complete depreciation/recapture and all corrected rollforwards cannot be invented |
| Adjust without losing original, who/why/effect | Implemented | Phase 1 immutable originals, estimated overlay, independent approval, conflicts and append-only ledger |
| See live changes and since last looked | Implemented | Authorized long polling, missed-event recovery, personal persistent checkpoints and scoped summaries |
| Compare versions and try what-ifs | Implemented within supplied alternatives | v1/v2/v3 comparisons, compatible stored scenarios; no combined/incompatible tax savings or rerun |
| Act on many items with undo | Implemented for supported safe operations | Atomic acknowledgments/submission/task assignment and audited compensation; bulk professional resolutions/approvals or filing reversal intentionally excluded |
| Prior-year swings; judgment/elections/due diligence/penalty decisions | Implemented as documented workpaper workflows | Existing deterministic flags and persistent authority/evidence/review; unsupported tax judgment still needs a CPA |
| Prove completeness: documents, areas, outside filings | Partially implemented | Accountability/diligence/outside-filing records and readiness block unresolved work; the actual incomplete case is not falsely certified complete |
| Client/colleague questions as evidence | Implemented with declared assurance | Threaded ownership/participants/deadlines/refs/attachments/audit/notifications; client statements are staff-mediated, not authenticated client communications |
| Blocking notes, changing sign-offs, roles, several people, assignments/deadlines/notifications | Implemented at prototype scale | Persistent scoped workflows, independent review, permanent invalidation, concurrency/live updates and in-app notifications; no external message delivery |
| Client approval and e-file signature | Partially implemented / intentionally excluded legal assurance | Snapshot-bound joint-client demonstration workflow exists; legal signatures/authenticated clients require real supporting infrastructure |
| Extensions, filing/rejections, client copy, freeze, amendment, notices/examination | Implemented as simulations | Immutable snapshots and packages, separate amendments, scripted/explicit demonstration events; actual submission/payment/delivery/agency confirmations intentionally excluded |
| Carry forward with history and plan next year | Partially implemented | Reviewed original/proposed carryovers and immutable handoff/planning facts; no invented corrected outgoing carryovers or future-year tax |
| Firm standards and sensitive-data protection/view logs | Implemented at prototype scale | Immutable policies, backend roles, nested masking, audited cleared views/downloads; enterprise SSO/MFA/encryption/operational controls remain outside this local prototype |
| Time against budget, status and search | Implemented for supplied engagement | Packet budgets, audited actual minutes/revisions, workload/deadlines/status/search; no fabricated multi-client firm or capacity figures |
| Prior preparer's work versus current changes | Implemented for supplied records | Prior-year memo/basis/carryovers and current version/review/adjustment histories remain navigable; historical gaps remain explicit |
| CPA speed/trust and day-one usability bar | Partially implemented, not independently validated | Search, pagination, evidence navigation, labels and accessible native controls are tested; real practitioner usability evaluation is still required |
| Hosted working-app link | Intentionally excluded now | Local working app exists; deployment has not started, as instructed |
| One-page core-idea/data-model hand-in; final error/design narrative and AI-use disclosure | Intentionally excluded final hand-in work | Phase engineering records exist; they do not replace final submission artifacts |
| Narrated prototype/technical-tradeoff video link | Intentionally excluded now | No video production has started, as instructed |

No feasible approved Phase 7 control is represented by a nonfunctional placeholder. The explicit remaining limitations concern unsupported authoritative computations, excluded real-world integrations/security assurance, unrestricted file ingestion, general multi-engagement/year editing and final delivery/usability validation.
