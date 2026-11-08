# Phase 6 — Filing and Post-Filing Lifecycle

## Scope and assurance

This phase implements a persistent **simulator**, from frozen workpaper through client review, extensions, payment evidence, filing outcomes, amendments, notices, examination packages and next-year handoff. All seven areas have frontend controls and backend enforcement. No agency transport, cash transfer, email delivery, authenticated client portal or legally valid electronic signature is configured.

The real household remains **FILING BLOCKED**. Demonstration acceptance is never authoritative readiness. An authoritative finalization request is rejected; there is no override endpoint. The original engine packet is never rewritten, and an approved adjustment remains a separate estimated workpaper overlay.

The complete three-page original PDF, Instructions.json, PHASE1.md–PHASE5.md, existing schema, API/security/transaction architecture, frontend and tests were inspected. The PDF skill and installed Next.js client-component documentation were consulted. No paid integration, additional runtime dependency, deployment, final case hand-in document or video was introduced. This file is the requested Phase 6 engineering record.

`backend/data/Instructions.json` SHA-256 remains:
`ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`.

## Architecture and exact Phase 6 file manifest

Created:

| File | Responsibility |
|---|---|
| `backend/app/migrations/005_filing_lifecycle.sql` | Additive immutable snapshot/package storage and migration marker |
| `backend/app/services/lifecycle_service.py` | Lifecycle state machines, fingerprints, controls, package generation, invalidation and audit integration |
| `backend/app/lifecycle_api.py` | Typed lifecycle requests and routes; server-session actor selection |
| `backend/tests/test_lifecycle.py` | 38 parametrized backend acceptance cases in isolated temporary databases |
| `frontend/src/components/FilingLifecycleWorkspace.tsx` | Seven-tab filing/post-filing workspace, histories, client review and JSON downloads |
| `frontend/workflow-tests/phase6.spec.ts` | Seven strict-mode browser workflows |
| `PHASE6.md` | This engineering record |

Modified:

| File | Change |
|---|---|
| `backend/app/main.py` | Registers the lifecycle router under the existing security boundary |
| `backend/app/services/adjustment_service.py` | Extracts pure `summary_from_items`; existing summary contract and calculations are preserved |
| `backend/app/services/workflow_service.py` | Calls lifecycle invalidation inside the originating transaction; conditionally binds payment/carryover evidence to relevant area manifests |
| `backend/app/services/change_analysis_service.py` | Includes relevant lifecycle payment/carryover records in reconciliation-review dependency fingerprints |
| `backend/app/security.py` | Routes lifecycle independence checks to transactional domain controls while retaining global protection; audits rejected domain requests; distinguishes account identifiers from tax capital-account balances during redaction |
| `frontend/src/components/FirmWorkflow.tsx` | Adds authorized navigation and mounts the workspace with the existing identity/masking epoch |

Existing Phase 1–5 source, tests, documentation and database changes already present in the working tree are not Phase 6 modifications. Build/test outputs are generated artifacts, not application source changes. No existing test was weakened or removed.

### Persistence and transaction design

Migration 005 adds only:

- `lifecycle_schema_migrations(version, applied_at)` with marker 5.
- `lifecycle_snapshots(id, content_hash, version, purpose, mode, parent_id, content_json, dependency_json, created_by, created_at)`. `parent_id` references the original snapshot. Purpose and mode have CHECK constraints. Content hashes are indexed, not globally unique: a retired snapshot's identical content may be frozen under a fresh identity without resurrecting the retired approval chain.
- `lifecycle_packages(id, kind, snapshot_id, resource_id, content_hash, content_json, created_by, created_at)`. Kinds are client copy, examination response and handoff. Snapshot foreign key and resource/kind index support tracing.
- Four triggers reject UPDATE/DELETE of snapshot and package rows.

Mutable projections reuse `workflow_entities`; every revision preserves complete before/after data in append-only `workflow_events`. Lifecycle kinds are `lc_snapshot_validity`, `lc_authorization`, `lc_filing`, `lc_extension`, `lc_payment`, `lc_amendment`, `lc_notice`, `lc_carryover`, `lc_handoff` and `lc_delivery`. New IDs are server generated, namespaced and kind-checked; arbitrary existing workflow IDs cannot be overwritten.

All writes use the existing serialized SQLite transaction and optimistic `expected_revision` checks. Concurrent identical freezes reuse the current matching snapshot; competing transitions allow one mutation and reject the stale revision. `WorkflowConnection.commit` invokes the Phase 4/5 and lifecycle invalidation hooks before commit. A hook failure rolls back the original mutation and every resulting invalidation together.

Migrations 001–004 and existing table definitions are unchanged. Verification inspected the real database read-only, backed it up to a temporary database, ran all migrations twice and compared every original row. The real database had not yet installed migration 004, so the backup correctly acquired both the existing workflow tables and the three new lifecycle tables. The real database was not migrated or seeded during this verification; normal configured application initialization applies additive migrations when it opens the chosen database.

### Frozen content and fingerprints

Each snapshot contains:

- Exact selected v1/v2/v3 engine baseline, original source values and unverified-engine classification.
- Only currently approved, non-stale, non-reversed adjustments and the separately labeled approved estimate.
- Evidence references and a complete immutable copy of the supplied packet, including FX, parameters, communications, timeline, other stored versions and their computation contract. Later packet events remain labeled scripted.
- Reconciliation decisions, review history, field-verification history, linked adjustments, current policy and immutable policy revision history.
- Scoped workflow manifests, approvals/sign-offs, financial evidence, contributors, rationale and the actual readiness blockers at freezing.

Canonical JSON uses sorted keys, compact separators and ASCII escaping. Snapshot fingerprint is SHA-256 of `{content, dependencies}`; creation time and snapshot ID do not alter this fingerprint. Identical inputs/rationale under current dependencies reproduce the same current snapshot. Retired identities remain retired permanently.

Dependency manifests bind packet SHA, baseline, policy, assignments, evidence verification, relevant workpaper records/notes/sign-offs/review assessments, version adjustments/reviews/decisions/links, and payment/carryover evidence. Filing administration, client response recording and notice preparation are excluded from the frozen workpaper dependency set so that recording approval does not invalidate itself. Those controls have their own fingerprints.

The snapshot is an engagement-wide freeze: any bound engagement dependency can stale it. Phase 4 tax-area sign-offs remain scoped: new payments affect payments/engagement; carryovers affect carryovers/engagement. Unrelated business approvals do not invalidate merely because a payment is recorded. An empty new evidence collection does not change preexisting manifest shape at deployment.

## APIs

All paths below are relative to `/api/lifecycle`. Existing API paths, payloads and IDs remain available. Mutations require the existing session, Origin and CSRF controls. Actor IDs come exclusively from the server session. Notes must be nonblank; unsupported fields are rejected. Mutable actions require `expected_revision`.

| Method | Path | Behavior |
|---|---|---|
| GET | `/overview` | Authorized lifecycle projections, snapshots, packages, payment sources/checks, notices and planning facts |
| POST | `/snapshots` | Freeze demonstration content; optional explicit unfiled supersession; authoritative attempts blocked |
| GET | `/snapshots/{id}` | Frozen content, dependency manifest and current validity |
| GET | `/snapshots/{original}/compare/{amended}` | Actual baseline/approved-leaf differences and separately estimated summaries |
| POST | `/authorizations` | Create snapshot/hash-bound joint-client demonstration request with expiry |
| GET | `/authorizations/{id}/client-review` | Staff-mediated client-facing view of original lines, approved estimates, request and warnings |
| POST | `/authorizations/{id}/responses` | Record immutable declared-client approve/decline with evidence and actor attribution |
| POST | `/filings` | Create original or amendment simulation for one snapshot/jurisdiction |
| POST | `/filings/{id}/actions` | `ready`, `submit`, `simulate_reject`, `simulate_accept`, `correct` |
| POST | `/filings/{id}/client-copy` | Generate immutable accepted-simulation JSON workpaper copy |
| POST | `/deliveries` | Record simulated package delivery to a packet client; no actual message |
| GET | `/packages/{id}` | Masked/audited-reveal content and canonical JSON download with stored/delivered hashes |
| POST | `/extensions` | Prepare supplied jurisdiction-specific v2 extension estimate |
| POST | `/extensions/{id}/actions` | `approve`, `simulate_submit`, `record_packet_event`; real `confirm_external` rejected |
| POST | `/payments` | Record exact supplied numeric agency evidence, with cross-snapshot deduplication |
| POST | `/payments/{id}/review` | Independent documented payment-evidence review |
| POST | `/amendments` | Freeze a separate amended snapshot linked to an accepted original |
| POST | `/amendments/{id}/actions` | Independent `review`, followed by distinct partner `approve` |
| POST | `/notices` | Supplied scripted notice or explicitly staff-entered demonstration intake |
| POST | `/notices/{id}/actions` | `prepare`, `submit_review`, `approve`, `simulate_dispatch`, `close_demo` |
| POST | `/notices/{id}/package` | Generate current independently approved examination-response package |
| POST | `/carryovers/import` | Idempotently import all frozen baseline outgoing values as unverified drafts |
| POST | `/carryovers/{id}/actions` | Document manual `revise` or independent `review` |
| POST | `/handoffs` | Assign next-year planning/handoff with packet facts and unsupported calculations |
| POST | `/handoffs/{id}/actions` | Independent `review`, then simulated `handoff` with immutable package |
| GET | `/history?entity_id=...` | Lifecycle append-only event history, optionally scoped |

Unresolved evidence, wrong dates/baselines, invalid transitions, missing consent, self-approval, stale revisions and inaccessible resources produce explicit validation/403/404/409 responses. They do not silently complete a workflow. Generated JSON is returned through the same protected boundary, not an unauthenticated download URL.

## State machines and permission matrix

Every lifecycle resource carries demonstration/simulation and no-legal-signature metadata.

| Resource | Supported progression and terminal history |
|---|---|
| Frozen snapshot validity | `current → invalidated` or `superseded`; content never changes and old validity never revives |
| Client request | `requested → partially_approved → approved`; any decline → `declined`; expiry/dependency change/new request → `invalidated` |
| Filing | `draft → ready_for_submission → submitted → rejected/accepted`; rejected + distinct corrected snapshot → `draft`, fresh authorization and partner approval, new attempt |
| Extension | `prepared → approved → simulated_submitted → external_evidence_recorded`; approved dependency drift → `needs_review` |
| Payment | `evidence_recorded → reviewed` |
| Amendment | `prepared → reviewed → approved`; dependency drift → `needs_review` or stale snapshot requiring a fresh freeze |
| Notice | `intake → preparing → in_review → approved → simulated_sent → simulated_closed`; reviewed response changes require preparation/review again |
| Carryover | `prepared → reviewed`; any manual revision → `prepared`, preserving original/proposal/review history |
| Handoff | `prepared → reviewed → handed_off`; before publication, drift → `needs_review`; after publication, keep historical state but mark approval invalid and require successor handoff |
| Delivery | Append-only `simulated_delivered` record; no real delivery confirmation |

| Action | Preparer | Reviewer | Partner | Administrator |
|---|---|---|---|---|
| Read lifecycle and masked packages | Assigned | Assigned | Assigned | Denied tax data |
| Prepare snapshots, consent demonstrations, filing drafts, extensions, payment evidence, amendments, carryovers/handoffs | Assigned | Assigned | Assigned | Denied |
| Approve simulated filing readiness or extension | Denied | Denied | Independent only | Denied |
| Operate an already approved simulated submission | Assigned practice staff | Assigned practice staff | Assigned practice staff | Denied |
| Record simulated provider outcome | Denied | Independent | Independent | Denied |
| Review payment, amendment, response, carryover or handoff | Denied | Independent | Independent | Denied |
| Final amendment approval | Denied | Denied | Independent of author and reviewer | Denied |
| Prepare notice response | Assigned owner | Assigned owner | Assigned owner or partner | Denied |
| Generate/download permitted packages and record simulated delivery | Assigned | Assigned | Assigned | Denied |
| Configure assignments/policy | Existing Phase 4 restriction | Existing Phase 4 restriction | Existing Phase 4 restriction | Existing admin controls |
| Reveal sensitive data | Separate clearance + purpose + audit | Same | Same | No tax-data privilege |

Independence excludes substantive authors. Filing approval also excludes frozen workpaper contributors and staff who recorded declared-client responses. Amendment review and partner approval are distinct. Handoff review excludes authors of underlying carryover proposals as well as the handoff author. Strict authorization is evaluated within each write transaction; frontend button visibility is only a convenience.

Original demonstration snapshots start separate simulation runs. A jurisdiction gets one filing record per snapshot, including previously attempted snapshots, preventing a rejected attempt from being bypassed with another record. Amendments inherit their accepted parent's simulation run. Original and amended snapshots/acceptances are preserved independently.

## Calculation and evidence assumptions

### Extensions and payments

The only supported extension computation is `what_if.extension`, based on **v2**:

| Jurisdiction | Supplied estimated tax | Supplied payments | Balance | Packet rounding | Proposed payment |
|---|---:|---:|---:|---|---:|
| Federal | 77,470 | 41,742 | 35,728 | Positive balance rounded up to next 500 | 36,000 |
| California | 17,999 | 27,130 | -9,131 | Negative balance floored at zero | 0 |

Decimal arithmetic independently reproduces the supplied result and rejects conflicting stored results. This is the packet's method, not a newly asserted tax-law rule. No extension estimates are generated for v1/v3 or recomputed from unrelated what-if savings. Approved estimates bind v2 adjustments, jurisdiction/year payment records, policy and assignments; a change requires reapproval and does not secretly recalculate the supplied estimate.

Payment recording accepts only attributable numeric IRS code 670 transactions or supplied FTB payment entries. Values, jurisdiction, date and designated tax year are derived server-side, never accepted as fabricated input. The same IRS payment repeated in two transcripts has one payment identity. The California September payment explicitly designated 2024 never becomes a 2025 credit. Existing independent Phase 3 federal/California payment comparisons remain visible; the ledger records evidence and never overwrites return lines.

The scripted extension evidence must identify the supplied extension timeline event or the specific matching federal April 14, 2026 payment. An unrelated $3,000 estimate does not prove a $36,000 extension payment. `external_evidence_recorded` explicitly means supplied packet evidence, not a real confirmed external action. `confirm_external` is blocked because no real confirmation adapter exists.

### Filing, consent and amendments

Both joint packet clients (`cu-01`, `cu-02`) must approve the exact snapshot/hash before simulated readiness. Each response records declared client, actual staff operator, evidence, note, timestamp and demonstration assurance. Response changes require a new request; new requests permanently supersede prior active consent. A later decline cannot be bypassed through older approved consent.

Submission attempts have generated `SIM-...` IDs, exact content hash, authorization certificate, partner-approval certificate, timestamps and, for amendments, the separately approved amendment certificate. Rejection codes use packet vocabulary (`R0000-504-02` federal, `STATE-HOLD` California); original agency submission IDs are never presented as newly issued confirmations. Accepted/rejected outcomes are explicit local provider simulations.

A correction binds a distinct immutable replacement snapshot and evidence; its old attempt survives. Resubmission requires fresh joint approval and independent partner readiness. An amended correction additionally requires a newly reviewed/approved replacement amendment tied to the same original. A late acknowledgment may record an outcome against an already submitted payload after current work changes; it never certifies the new workpaper or clears current readiness.

Amendment comparison uses actual stored engine differences and approved workpaper leaf overlays, with zero/format-only decimal changes normalized. No downstream tax rerun or official amended forms are invented. Original engine identity fields are not silently edited as a simulated rejection is corrected; a new evidence-bound rationale is retained, and there is no generated official e-file payload.

### Notices, examination and retention

The supplied IRS Letter 566 (`N-2025-L566`, D72) is dated **2028-01-20**, has a supplied **2028-02-19** response deadline and is classified scripted examination intake. Its `real_received_at` is null. The prior 2023 CP2000 remains prior-year history; a 2025 snapshot cannot be used as its missing 2023 filing snapshot. Manual federal/California notices require attributable references and explicitly entered demonstration dates. No statutory response interval is invented; unknown deadlines remain manual review.

An examination response must bind an accepted simulation in the same year/jurisdiction, a documented response, sources, an active assigned owner and independent approval. A generated package contains the complete frozen source packet/baseline/overlay, dependency manifest, review provenance, notice/response/evidence, notice audit, frozen validity history and accepted filing certificates. It is self-contained JSON, not a real notice submission or official return PDF. A historical accepted snapshot remains usable for answering a notice even after current work changes.

Retention uses D01 page 2's seven-year client retention statement as a **demonstration minimum**, not a statutory or administrator-certified firm retention rule. Anchor is the later of current UTC date and notice source date; packages retain `retain_until_at_least`, provenance and legal hold. There is no deletion job.

### Carryovers and planning

v3 supplies **17** outgoing leaf values. Import preserves exact original values and their frozen snapshot/path, from/to years and calculation limitations. Adjusted proposals require a finite Decimal amount (or explicit return to original), authority/method, evidence and rationale; independent review stores a separate reviewed value. A capital-account balance remains a tax balance, not a masked bank identifier. Neither review nor handoff asserts that a corrected outgoing carryover or 2026 tax has been authoritatively computed.

Handoff binds all imported/reviewed carryovers, owner, notes, active policy/assignments and the packet's 2026 planning reference. It requires every supplied leaf to have independent review and an accepted source simulation before completion. Planning facts/dates/safe-harbor descriptions are shown, but no future-year tax or actual installment dollars are fabricated. Completion notifies the assigned owner in-app and creates an immutable handoff package. Changed published carryovers mark that approval stale and notify the owner; a successor handoff is required.

## Invalidation and readiness

The existing real readiness blockers remain mandatory: missing assignments/diligence/elections/judgments, unresolved professional questions or blocking notes, document accountability gaps, unresolved/unsupported findings, stale review decisions, incomplete/stale adjustments, verification gaps, missing signatures, and unverified authoritative final return/actual client authorization. Demonstration workflow cannot waive them.

Examples verified automatically:

1. Changing a business preparation record invalidates its scoped signatures, the engagement freeze and pending snapshot-bound consent/readiness in the same transaction. Original content and earlier accepted attempts survive.
2. Recording/reviewing a payment affects payments/engagement manifests and related reconciliation reviews, preserving an unrelated business signature.
3. Changing relevant policy invalidates extension/amendment/response/handoff approvals that bound it. A stale approved state cannot be used by racing a later action; actions recompute their controls.
4. Superseding an unfiled freeze invalidates its consent. Reverting work to identical bytes creates a fresh identity if needed; the old snapshot never revives. Accepted originals cannot be superseded; use an amendment.
5. A replacement client request invalidates earlier consent and resets pending submission readiness. A decline or expiration blocks submission.
6. A carryover revision resets review and invalidates dependent handoff approval. Already published handoff content is preserved with a stale flag and successor requirement.
7. A deliberately raised invalidation-hook error rolls back the initiating workpaper mutation and every lifecycle state change.

Snapshot/approval validity is checked again at sensitive transitions, even if no dashboard has been opened since expiry. Automatic invalidation preserves append-only before/after history. Provider outcomes for already transmitted simulated attempts remain historical facts about that frozen simulated attempt, not mutable current-workpaper approvals.

## Security and limitations

- Phase 4 locked defaults, production startup validation, session identity, active membership, CSRF, allowed origins, stable staff IDs, role checks, independent review and sensitive-access purpose controls remain in force. Legacy unauthenticated behavior is confined to explicit isolated regression configuration.
- Global middleware still protects every lifecycle route, including snapshots, client-review views, package content/download JSON, errors and audit histories. Lifecycle-specific checks execute transactionally in the domain service instead of the generic legacy-write guard.
- Default recursive masking and known packet-identifier/text masking apply before package serialization. Reveals require clearance and purpose and are audited. Stored and delivered hashes are distinct when masking changes bytes; the downloaded canonical ASCII JSON hashes to `delivered_content_hash`.
- Responses use `Cache-Control: no-store`; the existing identity/masking epoch remounts the workspace, clearing in-memory details/downloads on switches or reveal changes. No public package links are introduced. Request URL logging remains disabled in the supported launcher. Denied domain actions add metadata-only access audit entries, without logging request contents or sensitive error bodies.
- Demonstration staff/client selection does not establish authenticated identity. Provisioned credential mode is not enterprise SSO/MFA, legal e-signature compliance or client identity proofing. No real payment/filing/notice/delivery confirmation can be created by this simulator.
- SQLite is not encrypted or externally notarized; trigger-protected append-only history is application-level tamper resistance, not protection against a privileged database/file administrator. Approved users can save revealed downloads. Arbitrary future files/identifiers would need additional extraction, redaction and threat testing.
- Frozen whole-packet evidence intentionally includes future scripted records for reproducible current/post-filing work. It is not a time-restricted replay endpoint. The separate Phase 5 replay retains its existing future-visibility protections.
- This single-engagement application has no official IRS/FTB forms/XML, legal signatures, external payment provider, actual mail/portal delivery, automatic statutory deadline engine or fully recomputable corrected tax engine. Manual conclusions remain professional workpaper judgments, not fabricated authoritative calculations.

## Verification

Tests use isolated temporary databases; browser suites start separate disposable legacy and strict servers. Synthetic transitions never mark the real packet filing-ready.

| Check | Result |
|---|---|
| Pytest | 405 passed, 0 failed (85.20 seconds) |
| Strict Playwright | 18 passed, 0 failed (11 existing + 7 new; 1.0 minute) |
| Legacy Playwright | 14 passed, 0 failed (20.0 seconds) |
| TypeScript | Passed (`tsc --noEmit`) |
| ESLint | Passed (`npm run lint`) |
| Webpack production build | Passed (`next build --webpack`; optimized routes generated) |
| SQLite migration preservation | All original rows preserved after two migration passes on backup |
| SQLite integrity / foreign keys | `ok` / no violations |
| Instructions.json | Original SHA-256 unchanged |

The 392-test prior baseline consists of 367 backend + 14 legacy-browser + 11 strict-browser tests. All remain passing. Phase 6 adds 38 backend and seven strict-browser cases, for **437 passing tests, zero final failures** across the full suites. The Phase 6 simulated implementation and required verification are complete; the real case remains filing-blocked and the broader PDF limitations below remain open.

An initial strict-browser run found two new-workspace UI/test integration issues: a locator also matched Next's route announcer, and closed notice cards no longer displayed their stable ID. The new locator was scoped to the lifecycle workspace, and notice IDs now remain visible in every state. Neither existing tests nor assertions were weakened. Final strict verification passes. The preexisting Starlette/httpx deprecation warning and Node color-environment warnings remain; they do not indicate failing checks.

Backend coverage includes reproducible and concurrent freezes; immutable content/packages; all v1/v2/v3 authoritative blocks; joint consent/decline/expiry/replacement; namespace forgery; federal/California outcomes; rejection/correction/resubmission; amended resubmission; stale/late approvals; scoped signature invalidation and rollback; exact extension computations/unsupported baselines/wrong evidence; payment year/deduplication; original/amended independence; scripted and manual CA notices; response deadlines/packages/retention; carryover original/manual/reviewed provenance; stale published handoff; permissions, sensitive audit, canonical download hashes, caching and concurrent approvals.

Browser coverage exercises all seven tabs through real controls: blocked authoritative freeze and demo acceptance/client copy/download/delivery; rejected attempt and fresh-snapshot resubmission; extension/payment review; 2028 examination response package; separately approved amendment/authorization/filing; all 17 carryover reviews/handoff; admin denial and masked package response. All existing Phase 1–5 browser workflows remain part of the suites.

Commands, from repository root unless noted:

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

SQLite checks use a read-only connection to the working database, SQLite backup into a temporary directory, two `app.migrate.migrate` passes, full original-row comparisons, `PRAGMA integrity_check` and `PRAGMA foreign_key_check`. The original counts remain reviews 1, review_events 4, one marker each for adjustments/evidence/reconciliation and zero original adjustment/verification/reconciliation rows. Automated tests also exercise migration idempotence and immutable-table triggers.

## Complete demonstration workflow

Use an isolated demonstration database so the current repository's review records remain untouched. From `backend` (choose a new absolute database filename):

```sh
WORKPAPER_ENV=development WORKPAPER_MODE=demo WORKPAPER_ORIGINS=http://localhost:3000 REVIEW_DB_PATH=/private/tmp/miraflores-phase6-demo.db PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_secure.py
```

From `frontend`, run `npm run dev` with the existing API URL `http://localhost:8000`. Use strict demo sessions, never the isolated legacy regression launcher. Session switching clears tab selections and rationale fields; reopen Filing & Post-Filing and choose the intended working snapshot after each switch.

### Freeze and client authorization

1. Select **st-01 Priya** and start the demonstration session. Open **Readiness** and confirm FILING BLOCKED with actual blockers.
2. Open **Filing & Post-Filing → Finalization**. Enter rationale `Original demonstration return`, references `D01`, baseline v3. Select authoritative mode and attempt freezing: it must reject. Switch to demonstration mode and freeze. Inspect the SHA, immutable baseline, separate approved adjustments, dependency manifest and retained readiness blockers. Repeating exactly the same current inputs reuses the snapshot.
3. Open **Client Authorization**, select the new working snapshot, set a future UTC expiry and rationale. Create the demo request. Open the client-facing review: it exposes original lines and approved estimates, bound version/hash and no-legal-signature warning.
4. Select **cu-01**, references `msg-09`, and record demo approval. State is partially approved. Select **cu-02** and approve: state becomes approved. A decline instead blocks the request; issue a fresh request to restart, preserving history.

### Submission, rejection and correction

5. As st-01, **Filing Status**: select the snapshot, federal jurisdiction and Original filing; enter rationale and create a simulated draft. Attempting readiness without joint consent or as its author must fail.
6. Switch to **st-03 Helen**, reopen Filing Status, enter independent rationale. Approve simulated readiness, then simulate submission. Inspect generated SIM ID, frozen hash, authorization and partner certificates.
7. Simulate rejection. Inspect the packet-derived federal rejection code, explicit local-provider label and attempt timestamp. No actual agency confirmation exists.
8. Switch to st-01. In Finalization, enter a distinct correction rationale and evidence `D71`; freeze a new demonstration snapshot. Original engine values stay intact. Obtain new cu-01/cu-02 demo approvals on the new snapshot.
9. In Filing Status select the corrected working snapshot and reference D71. On the rejected record choose **Bind corrected snapshot**. It returns to draft while preserving the rejected attempt and correction history. Switch to st-03, reapprove readiness, simulate submission, then acceptance. Two attempts and one correction are retained. To demonstrate California, use its separate jurisdiction draft; its local rejection vocabulary is STATE-HOLD.
10. Generate the simulated client copy on the accepted record. Inspect stored/delivered fingerprints and download the simulated JSON. Choose a packet client and record simulated delivery. There is no actual email or delivery confirmation. Readiness still says FILING BLOCKED.

### Extensions and payment evidence

11. As st-01 open **Extensions & Payments**, select federal, enter rationale and prepare the supplied v2 estimate. Inspect tax 77,470, payments 41,742, balance 35,728 and proposed 36,000. Repeat with California to inspect proposed zero. This does not calculate v3 extension liability.
12. As st-03 independently approve, simulate extension submission, then link scripted extension evidence. State external_evidence_recorded explicitly remains non-real. Inspect history.
13. As st-01 select a numeric IRS payment source and record evidence. As **st-02 Daniel**, independently review it. Duplicate transcript evidence must reject, and the FTB 2024-designated payment must remain 2024. Expand independent payment reconciliation.

Payment/carryover evidence changes intentionally stale pending freezes; perform this branch before making a new current snapshot or use the previously accepted immutable filing for post-filing notice/handoff examples.

### Amendment

14. As st-01 open **Amendments**, select an accepted original snapshot, choose a supported baseline, enter an amendment reason and source evidence, and prepare a separate amendment. Compare original/amended engine changes and approved leaf estimates; an unchanged baseline can validly show no numeric difference. To demonstrate a tax-workpaper correction, first complete an independently approved Phase 1 adjustment, then freeze the amendment; the original accepted snapshot is unchanged.
15. As st-02 independently review the amendment. As st-03 provide separate partner approval. As st-01 use **Authorize amended snapshot**, create a fresh joint demo client request and record both responses.
16. In Filing Status select that amended snapshot and amendment record. Create its own draft, then use st-03 for ready/submission/acceptance. Inspect the amendment certificate and preserved original filing. A rejected amendment requires a newly frozen/reviewed/approved replacement amendment, not reuse of old approval.

### Notice and examination

17. As st-01 open **Notices & Examination**. Select an accepted federal snapshot, N-2025-L566 and owner st-01; enter rationale and record intake. Confirm scripted classification, source date 2028-01-20, due date 2028-02-19 and null real receipt time.
18. Set supporting references `D72, D14, D53`, write the proposed examination response in the rationale field, prepare response and submit for review.
19. As st-02 enter an independent review rationale and approve response. Generate the examination package. Download/inspect frozen packet, baseline/overlay, evidence, policy/review provenance, accepted filing certificates, notice history and retention/legal hold. Simulate dispatch, then close the demonstration notice. No agency response is sent.
20. For California, use **Staff-entered demonstration notice**, select California, enter explicit dates/title and resolved reference such as D74. Prepare against an accepted California simulation. The app rejects impossible date order and inactive/unassigned owners. A prior-year CP2000 cannot be answered with a 2025 filing snapshot.

### Carryovers, handoff, invalidation and security

21. As st-01 open **Carryovers & Planning**, select an accepted v3 snapshot, enter rationale, import the 17 supplied carryovers and prepare next-year handoff to an active practice owner. Inspect each original path/value; there is no calculated 2026 tax.
22. Optionally propose a manual value with explicit authority/method, source references and note. Original remains visible and review resets. As st-02 provide source references (for example D06 plus item-specific evidence), authority/method and rationale; review every carryover individually. This is a documented workpaper proposal, not proof of a legally correct future calculation.
23. As st-02 independently review handoff, then record simulated handoff. Inspect in-app notification and immutable package. Review the supplied planning dates/facts and explicit unsupported calculations.
24. Revise a carryover afterward: prior published package remains unchanged, approval is marked stale and owner notified. Prepare a successor handoff after fresh independent carryover review.
25. To demonstrate pending-freeze invalidation, freeze/authorize a new current snapshot and get partner readiness without submission. Change relevant business preparation/evidence through the existing workpaper controls. Reload lifecycle: snapshot/consent stale and filing back to draft. Historical accepted attempts remain preserved. Inspect append-only lifecycle history.
26. Switch to st-05 administrator: lifecycle tax navigation and direct API access are denied. A separately assigned uncleared preparer can view masked data but cannot reveal identifiers. Cleared users must supply an access purpose for audited reveal. Identity/masking switches clear opened package/detail state. Finish in Readiness and confirm real FILING BLOCKED.

## Remaining original case-study PDF requirements

The PDF describes a finished product broader than this packet-backed simulator. The following requirements remain incomplete, wholly or in the stated extent; Phase 6 does not claim to finish them:

1. **Evidence attachments and cross-return working:** arbitrary new file/message attachment intake and a live client/colleague question portal are absent. Existing packet messages and persistent workpaper notes can be linked. Prior-year evidence and frozen carryover provenance exist, but a general multi-engagement/related-return editor and operational next-year return workspace do not.
2. **Complete calculation/records coverage:** stored schedules, assets/sales, independent supported checks and limitations are available. A corrected rerunnable return, complete independent basis-by-year/outside-basis, full federal/CA/AMT depreciation/recapture, passive-loss limitations, retirement/foreign/credit eligibility and every outgoing carryover cannot be authoritatively verified from missing inputs/results. Unsupported areas remain explicit; complete books-to-tax/state split and every outside filing cannot be certified merely by checking diligence boxes. See PHASE3.md's rule-level coverage and limitations.
3. **Live change and collaboration:** optimistic concurrency, audit history, version comparison and sign-off invalidation work. Live pushed multi-user updates, reviewer-specific “since I last looked” checkpoints, general bulk workpaper actions and undo are absent. Importing all carryovers is not a general bulk-undo facility.
4. **Real client approval and e-file signature:** client review/response is staff-mediated demonstration identity, not an authenticated client portal or legally compliant e-file signature. Real IRS/FTB submission, payment transfer, acceptance, client-copy delivery and notice dispatch are intentionally unconfigured. These real-world elements remain unsatisfied by simulation, consistent with the Phase 6 constraints.
5. **Official filing/rollforward outputs:** freeze/amendment/examination/handoff simulations and self-contained JSON packages now work. Official completed tax forms/PDFs/XML, authoritative corrected amended returns, actual next-year tax calculations, automated statutory notice/retention rules and live rollforward into a new year's computed return do not. No authoritative filing-ready path exists for this unresolved packet.
6. **Firm operations:** engagement roles/assignments/standards, statuses, notifications and sensitive view logs work. Full firm-wide time-versus-budget, cross-engagement status/search and enterprise identity/operational security administration are incomplete. Current local searching and assignment notifications do not fulfill a firm-wide operations suite.
7. **Hand-in artifacts:** hosted working-app link, dedicated one-page core-idea/data-model handover, final consolidated errors/design narrative and required narrated prototype/technical-tradeoff video link remain to be prepared. Earlier engineering docs describe errors and AI/tool usage; they do not replace the final case hand-in. Final documentation/video/deployment work has deliberately not begun, as instructed.

The PDF's simulated-source-document requirement is retained through existing field-specific evidence views; actual extraction/PDF source ingestion was not required by the brief and has not been fabricated. The qualitative CPA speed/trust and new-hire usability bar still needs real practitioner evaluation; passing automated tests is not evidence that this user-research criterion has been met.
