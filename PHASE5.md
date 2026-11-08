# Phase 5 — Version Comparison, What-if Scenarios, and Timeline Replay

## Scope and implemented features

Phase 5 adds an authorized Change Analysis workspace to the Phase 4 application. It compares immutable engine snapshots, presents the five supplied alternative computations, replays time-bounded packet evidence, and explains changes affecting current reviews and approvals. It does not rerun the engine, apply hypothetical tax savings, sign a return, file anything, or implement Phase 6.

The original case-study PDF, Instructions.json computation/reference contract, PHASE1.md–PHASE4.md, backend/frontend, migrations and existing tests were inspected. The PDF was read using the PDF skill and pypdf; Next.js's installed client-component documentation was consulted. No external paid service or new dependency was introduced.

Instructions.json SHA-256 remains `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`.

### Return version comparison

- A three-column v1/v2/v3 matrix preserves presence versus absence and original values. Select any ordered pair, including reverse or identical versions, to classify added, removed, changed and unchanged lines.
- Diffs are calculated from actual stored lines, not trusted `changes_from_previous` declarations. Metadata-only changes remain distinguishable from value changes. Original declared changes, version triggers and line notes appear as explanations, with an explicit warning that these are not proof of causality.
- Numeric differences and percentage changes use Decimal arithmetic. Percentage is `(new - old) / abs(old) × 100`; a zero/missing/nonnumeric baseline yields an explicit undefined reason. Missing lines are not treated as zero.
- Dollar differences are labeled only for inferred monetary lines; ratio/rate/quantity/text fields retain numeric or nonmonetary presentation. The packet lacks a universal units field, so this conservative presentation does not turn ratios into tax dollars.
- Changed lines link to the selected version's lineage, exact source references and supporting documents through the existing resolver, simulated-document inspector and field-specific SourceVerification highlighting. Full graphs are fetched on demand; compact support summaries avoid repeating entire dependency graphs in every comparison row.
- Diagnostics, unified findings, current persistent review state/validity and current adjustment ledgers are shown by engine baseline. Diagnostic duplicates are retained using occurrence-aware identities. Existing finding IDs are not reassigned. These current review/ledger sections are explicitly separate from historical workflow snapshots.

For v1 → v3 the actual line diff has 3 additions, 1 removal, 117 changes and 507 unchanged lines. Federal total tax F1040.24 is 77,200 / 77,470 / 81,962 across v1/v2/v3: a v1 → v3 increase of 4,762, or v2 → v3 increase of 4,492. Comparison does not establish that any stored figure is correct.

### What-if analysis

Only the packet's five stored alternatives are offered, all based on v3:

| Alternative | Supplied choice | Federal total-tax change | California total-tax change |
|---|---|---:|---:|
| `equipment_section179` | equipment = s179 | 0 | -1,050 |
| `equipment_no_bonus` | equipment = macrs | +10,245 | -260 |
| `hvac_improvement` | hvac = improvement | +3,633 | +896 |
| `standard_deduction` | deduction = standard | +12,306 | 0 |
| `penalty_annualized` | penalty_method = annualized | 0 | 0 |

These are supplied simplified-engine alternative results, not authoritative recalculations, approved corrections or automatically available savings. The API preserves each jurisdiction's base/alternative summaries, changed lines, choices and supplied tax/penalty deltas. Missing California `penalty_change` fields remain “not supplied”; they are not manufactured.

Compatibility checks compare the requested version, supplied baseline summaries and every changed line's old value to the actual stored baseline. Effect checks separately compare supplied deltas with the provided base/alternative summaries. All five packet alternatives match their v3 baseline; v1/v2 selections are incompatible.

Different values for the same choice key conflict: section 179 and no-bonus MACRS cannot be selected together. Other selections may be compared alongside one another, but **no combined engine result is supplied**. `combined_result` is always null; the system never adds savings. Submitted/approved adjustment interactions are called out, and all alternatives always refer to the original unadjusted baseline. California AMT and other unsupported interactions remain explicit limitations.

The April extension estimate is displayed separately as the stored v2-based estimate. Viewing it does not record an extension or payment.

Authorized practice staff can save and revise hypothetical analyses with notes and optimistic revisions. They remain `hypothetical`, preserve every before/after revision, and never enter the Phase 1 financial ledger or contribute to workpaper summaries/sign-offs. Existing workflow IDs cannot be overwritten or reserved through the analysis endpoint.

### Controlled timeline replay

The replay workspace is separate from the current tax workspace. Opening it unmounts current tax inspectors, preventing a previously opened future document from remaining beside a historical snapshot.

The user selects a UTC instant. The replay shows:

- Every document arrival from `received_at`, plus eligible scripted engagement events.
- Only versions whose `computed_at` is at or before the cutoff, and their stored engine summaries labeled as unverified snapshots.
- Time-eligible stored-version corrections, including old/new values, differences and packet triggers.
- Questionnaires, messages and call notes only after their supplied timestamps.
- Only eligible stored diagnostics. Independent reconciliation findings are not backdated from the current catalog.
- Actual database review, field-verification and workflow audit activity according to server recording timestamps, distinct from scripted packet history.
- Actual adjustment event state reconstructed from append-only snapshots at the cutoff; current mutable ledger projections are not substituted into the past.
- Historical source navigation through a dedicated time-aware resolver, not the current evidence endpoint.

Nested evidence is filtered before resolution. Document/page/extracted references require document arrival; communications require their own timestamps; agency snapshots, transactions, notices and e-file entries require eligible dates and supporting-document availability. Original agency JSON Pointer indices are preserved; inaccessible slots do not acquire future values. Explicit future pointer requests return unresolved results with no label/value/source graph from the future.

Return lines and assets must have an eligible version and eligible declared dependencies. Lines whose dependencies are unavailable, invalid or cyclic are withheld with a reason rather than exposed using current knowledge. Before the first engine run, already received documents and other eligible source records can still be inspected using a source-only resolver context; no fictitious computed version or tax output is introduced. Historical `v1`/`v2`/`v3` references have the additive typed result `return_version` and contain only eligible version metadata.

Date-only availability is conservatively interpreted as the end of that UTC day. Document extraction has no independent timestamp, so extracted fields become eligible with their source document; this assumption is disclosed below. Scripted events can describe future plans already known at their timestamp, but later records themselves are not exposed early.

All packet timeline events are labeled scripted/received-at history and `completes_live_workflow=false`. Client signature, rejection/acceptance, payment, refund, quality review and examination events never perform those actions in the live application. Replay never changes financial/review decisions or clears readiness. Normal security access logging and first-use database initialization still occur.

### Current change impact and approval validity

- Dependency previews accept line, document, document-page, extracted/client/prior-year/agency references, or `policy:current`. They identify reachable return lines, workpaper areas, findings and affected approvals. Unknown references remain explicit.
- A preview or hypothetical selection does not invalidate approvals. Actual supported mutations use the existing transaction hook to reassess review dependencies and invalidate signatures before the source transaction commits.
- Review dependency fingerprints bind source graphs, relevant adjustments, verification events, finding links, scoped preparation/notes and active policy. A new documented resolved-review event binds current dependencies. A relevant change marks the separate assessment `needs_reassessment`; the original resolved status, note and review history remain intact.
- Existing unbound legacy resolutions are not silently treated as newly confirmed. Only actual review event IDs inserted by the current transaction may establish a fresh binding.
- A fresh documented independent resolution is required to clear reassessment; merely viewing or recording an impact preview cannot clear it. Reconciliation cards display a warning when their prior resolution requires reassessment. Filing readiness has an additional `REVIEW_REASSESSMENT_REQUIRED` blocker.
- Relevant review assessments become part of Phase 4's signature manifest. Empty assessment collections do not change pre-Phase-5 manifests, avoiding deployment-only invalidation of unrelated signatures.
- Signature invalidation remains scoped, transactional and permanent. Reverting a dependency does not resurrect an old sign-off. Current related approvals may be inspected alongside append-only invalidation history. Unrelated payments approvals and unrelated review bindings are preserved in automated tests.

A review-assessment state describes the binding of the last documented resolution, not an override of the current review status. Reopening a review still leaves an unresolved finding that blocks readiness.

## Architecture and exact Phase 5 file manifest

New files:

| File | Responsibility |
|---|---|
| `backend/app/change_analysis_api.py` | Typed comparison, scenario, replay and impact API routes |
| `backend/app/services/change_analysis_service.py` | Actual version diffs, support indices, scenario compatibility/conflicts, saved analyses, impact/fingerprints/reassessment |
| `backend/app/services/timeline_service.py` | UTC availability context, nested historical resolver, safe replay and audit reconstruction |
| `backend/tests/test_change_analysis.py` | Phase 5 calculations, temporal boundaries, security, persistence, concurrency and integration tests |
| `frontend/src/components/ChangeAnalysisWorkspace.tsx` | Version Comparison, What-if Analysis, Timeline Replay and Change Impact UI |
| `frontend/workflow-tests/phase5.spec.ts` | Five strict-mode browser workflows |
| `PHASE5.md` | This implementation and verification record |

Modified files:

| File | Phase 5 change |
|---|---|
| `backend/app/main.py` | Include new router under the existing shared security boundary |
| `backend/app/security.py` | Efficient per-response redaction memoization/compiled identifier matching; avoid treating nonnumeric account-label prose as a secret; reject malformed non-object JSON without reflecting input |
| `backend/app/workflow_connection.py` | Track newly inserted review-event IDs through commit/rollback |
| `backend/app/services/workflow_service.py` | Invoke reassessment inside the original transaction; bind relevant assessment records in signatures; add readiness blocker |
| `backend/app/services/reconciliation_workflow.py` | Add review-validity metadata to findings that have a persisted assessment |
| `backend/app/services/evidence_service.py` | Add `return_version` to typed results for historical version metadata; existing resolver behavior is preserved |
| `frontend/src/components/FirmWorkflow.tsx` | Authorized top-level Change Analysis navigation, separate from current workpaper/replay state |
| `frontend/src/components/ReconciliationDashboard.tsx` | Display stale-resolution warnings without overwriting existing review statuses |

The worktree already contained uncommitted Phases 1–4 files and generated artifacts. They were preserved; this manifest does not attribute the entire repository diff to Phase 5. Original regression test assertions were not modified.

## API and persistence changes

All new endpoints inherit strict sessions, assignment checks, redaction, no-store responses and sensitive-access audit controls. Mutations also require CSRF and allowed Origin. Selected staff IDs are never authenticated identity assurance in demo mode; Phase 4's warning remains visible. Administrators have no tax-analysis privilege, and assigning a preparer does not grant sensitive-data clearance.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/version-comparison?before=v1&after=v3` | Three-version matrix, selected-pair actual line diff, reasons/support, diagnostic/finding/review/ledger differences |
| GET | `/api/what-if?version=v3` | Supported alternative catalog, compatibility/effect checks and extension estimate |
| POST | `/api/what-if/compare` | Evaluate selection compatibility/conflicts; no combined tax result |
| POST | `/api/what-if/analyses` | Save/revise hypothetical analysis with expected revision and server principal |
| GET | `/api/what-if/analyses` | Current saved analyses and append-only revision events |
| GET | `/api/timeline-replay?at=...` | Read-only historical packet/audit snapshot |
| GET | `/api/timeline-replay/evidence?at=...&ref=...&version=...` | Time-aware typed evidence graph; unavailable references never fall through to current data |
| GET | `/api/change-impact?ref=SchC.1&version=v3` | Dependency preview, related approval validity, review assessments and audit history |
| POST | `/api/change-impact/reassess` | Independent reviewer/partner records a current impact assessment and checks existing bindings |

Selection body: `{ "version": "v3", "scenario_ids": ["equipment_section179"] }`.

Save adds optional existing analysis `id`, required `note`, and `expected_revision` (0 for a new analysis). Conflicting/wrong-baseline/unknown selections cannot be saved. Revisions cannot overwrite any other kind of workflow entity. Impact assessment body contains `version`, `refs`, and `note`.

No new SQLite DDL is required. Existing additive migrations 001–004 remain unchanged. Phase 5 uses the existing `workflow_entities` projection and append-only `workflow_events`:

- `kind=scenario_analysis`, state `hypothetical`: baseline, supplied choice IDs, rationale, packet fingerprint and stored comparison snapshot. Events preserve every revision.
- `kind=review_assessment`, state `current` or `needs_reassessment`: version/finding ID, latest resolved review-event ID, dependency fingerprint and reason. Events preserve every reassessment.
- `kind=impact` events: assessor, reference set, affected line/area list and rationale.

Existing ledger tables/states, review IDs, historical rows, policies, signatures and immutable packet values are not rewritten. Financial overlays still require Phase 1's independent approval controls and partner threshold.

## Verification

Original baseline: **326 passing tests = 306 pytest + 14 legacy browser regressions + 6 strict browser workflows**.

Phase 5 final verification:

| Check | Result |
|---|---|
| Pytest | **367 passed**: all original 306 plus 61 Phase 5 cases |
| Playwright regression | **14 passed**, original assertions retained |
| Playwright strict | **11 passed**: original 6 plus 5 Phase 5 workflows |
| TypeScript | `tsc --noEmit` passed |
| ESLint | Passed |
| Production build | `npm run build -- --webpack` passed; both Playwright servers also build production artifacts |
| SQLite | Original/copy integrity `ok`; copy foreign-key check empty; repeated migration preserved all original table-row digests |
| Instructions.json | Original SHA-256 unchanged |

The production build uses the webpack option already established in Phase 4 for this environment. Build/font fetching and local browser servers require approved execution outside the sandbox. The existing Starlette/httpx deprecation warning remains. No final test failures are accepted or hidden by retries.

Tests cover all ordered version-pair behaviors, missing/zero/text/negative values, contradictory declared diffs, duplicate diagnostics, every stored alternative's exact federal/California changes, invalid baselines/choices, mutually exclusive and unsupported combinations, immutable summaries, optimistic/concurrent revisions, ID-namespace isolation, audit history, exact document/version boundaries, source inspection before the first computation, future documents/extractions/messages/notices/e-file entries, nested source withholding, actual versus scripted reviews/verifications, current readiness separation, dependency previews, real invalidation versus hypothetical isolation, unrelated review/approval preservation, fresh resolution requirements, authorization/clearance/CSRF/no-store/redaction, and database integrity.

The schema-preservation check inspected the working SQLite database read-only, backed it up to a temporary database, applied migrations twice, and compared original table-row hashes. Original rows remained: reviews 1, review_events 4, migration markers 1 each for adjustments/evidence/reconciliation, and empty original ledger/verification/reconciliation event tables. The working database was not modified by Phase 5 verification. No migration 005 was necessary.

Reproduce from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd frontend
npx tsc --noEmit
npm run lint
npm run build -- --webpack
npm run test:e2e
npm run test:e2e -- --config=playwright.workflow.config.ts
```

Both browser suites use private local servers and disposable databases. Legacy unauthenticated behavior remains isolated to its explicit test configuration. Strict tests use separate application settings and do not inherit legacy authorization.

## Known limitations and remaining PDF requirements

### Phase 5 limitations

1. The engine cannot be rerun. Only the five stored alternatives are supported. Their combined effects, interactions with corrections, large threshold crossings and California AMT are not authoritative or computed here. Selecting an election does not implement it on a tax return.
2. Replay is a conservative knowledge projection, not a recovered original application database. The packet has no per-field extraction/ingestion history or historical CPA reviews. Field availability is tied to document receipt; date-only records are available at day end. Undated prior-year/household provenance is conservatively gated using the supplied organizer/prior-record delivery facts.
3. Independent reconciliation findings are not retrospectively asserted: the current catalog includes later evidence. Replay shows only eligible stored engine diagnostics, actual audit metadata and explicit explanations for unsupported/withheld material. Some known engine lines are withheld because their declared provenance is unresolved/cyclic; this does not invent missing historical inputs. Engine summaries remain visible as stored reports, not independently verified totals.
4. Historical review/workflow activity is intentionally limited to eligible audit metadata. Current mutable note/policy/assignment projections and unrestricted source snapshots are not inserted into the past. Exact source documents and eligible communications remain navigable. Actual later audit records appear only after their server timestamps.
5. Document availability follows packet `received_at`, not mentions in earlier narratives. An earlier message can truthfully mention an expected late K-1 without exposing that K-1 before arrival.
6. Change impact follows declared evidence/line dependencies and scoped workflow records. It cannot infer arbitrary semantic relationships omitted from the packet. Policy is a shared dependency: a global policy revision affects all signatures that bound that policy. External direct SQL/packet edits are outside supported mutation paths; packet replacement requires process restart and review.
7. Original resolved review statuses are preserved for compatibility/history. Current validity is separate; stale resolutions block readiness and have explicit warnings. Existing unbound legacy decisions require new review. A manual impact assessment cannot waive that requirement.
8. No WebSocket push or “since I last viewed” checkpoint has been added. Views refresh through explicit navigation/actions; immutable support indices are cached, mutable ledger/review state is read from SQLite.
9. Phase 4 security limits remain: demo selection is not authentication; configured credentials are not enterprise SSO/MFA or legal e-signatures; SQLite is not encrypted or externally notarized. Approved users can copy revealed data. Redaction supports the packet and labeled identifier patterns, not arbitrary future document ingestion.

### Original PDF requirements still incomplete

The original PDF describes a broader finished product than these implemented phases. Remaining requirements include:

- Bulk multi-item actions with undo; automatic/live collaboration updates and per-reviewer “since last looked” views.
- Uploading arbitrary new files and a full live client/colleague communication portal; the current system links packet evidence and persistent review records.
- Fully authoritative corrections/recomputation and every professional tax schedule/limitation where the packet lacks sufficient inputs or engine results. Unsupported tax areas remain review blockers.
- Actual client approval/e-file signatures, extensions/filing submissions/rejections, client-copy delivery, freeze-at-filing, amendments, examination-response bundles, rollforward and next-year planning workflows. Phase 5 only replays supplied events; these Phase 6 actions are not implemented.
- Complete firm-wide time-versus-budget, global search/status operations and enterprise identity/security administration beyond the demonstrated engagement workflow.
- The final hand-in artifacts: hosted working-app link, a dedicated one-page core-idea/data-model handover, and the required narrated prototype/technical-tradeoff video link. This repository documentation is not a substitute for the requested video or hosted delivery.

The real packet remains filing-blocked until actual prerequisites are met. No hypothetical analysis or scripted filing event clears that block. Phase 6 has not begun.

## Demonstration workflow

Start the existing secure local demonstration launcher from `backend`:

```sh
WORKPAPER_ENV=development WORKPAPER_MODE=demo WORKPAPER_ORIGINS=http://localhost:3000 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_secure.py
```

Set `REVIEW_DB_PATH` to a separate absolute demonstration database path if desired. In `frontend`, run `npm run dev` with API URL `http://localhost:8000`. Use strict demo mode, not the isolated legacy regression profile.

1. Open the app and select st-01 Priya. Confirm the persistent demonstration/no-legal-signature warning. Open the top-level **Change Analysis** tab.
2. In **Version Comparison**, leave v1 → v3 selected and search `F1040.24`. Inspect 77,200 / 77,470 / 81,962 and the 4,762 increase. Change the left baseline to v2 to see 4,492. Open the chosen version's inspect link, follow its source/line links, and open **Change details** for packet triggers and supporting documents. Inspect diagnostics, current review/finding changes and separate adjustment ledgers.
3. In **What-if Analysis**, select `equipment_section179` on v3: federal total-tax change 0 and California -1,050. Read the original/alternative jurisdiction summaries, baseline checks and supplied changed lines.
4. Add `equipment_no_bonus`. The shared equipment choice conflicts, and saving is blocked. Remove it. Add `standard_deduction` to compare two separate results: there is still no combined result and no summed savings. Switch to v1/v2 to observe baseline incompatibility; restore v3.
5. Enter a rationale and **Save hypothetical analysis**. Reload, reopen What-if Analysis and load saved analyses/history. Confirm the state remains hypothetical and the Phase 1 ledger/approved summary has not changed. Inspect the separate April v2 extension estimate without performing an extension/payment action.
6. In **Timeline Replay**, select `2026-03-04T09:12:00` UTC and replay. v1 is available; D31 (corrected brokerage), D37/D38 (late K-1) and D72 (2028 notice) are absent. Request `agency:/notices/1` or D72 in the historical inspector: no future payload is returned.
7. Move to `2026-03-18T21:09:00`: D31 is now available, but v2 is not computed yet. Move to `2026-03-19T07:40:00`: v2 and eligible stored-version corrections appear. Move to `2026-06-23T06:05:00`: v3 appears, while D71/D72 remain unavailable.
8. Move to `2026-07-15T02:11:00`: scripted federal/California acceptance events are visible and labeled historical, never live workflow completion. Move to `2028-01-26T15:00:00` to inspect the now-available examination notice. Return to **Readiness** and confirm FILING BLOCKED remains. For early-season source-only behavior, replay `2026-01-12T17:04:00`: D01 can be inspected before any engine version exists.
9. Return to the current tax workspace and prepare the business-receipts source review as st-01. Resolve required scoped notes/records through the existing independent workflow. As st-02, record a business reviewer sign-off; use st-03 for required partner approvals. These are demonstration workpaper approvals.
10. In **Change Analysis → Change Impact**, preview `SchC.1` or D14. Inspect affected lines, areas, findings and current signatures. Previewing does not change their state. Save a hypothetical analysis and verify signatures remain unchanged.
11. As st-01, use the existing business-receipts adjustment example (`SchC.1`, 163,700 → 151,300) to create a real adjustment draft. Affected business approvals invalidate through the transactional hook; unrelated approvals remain valid unless their actual dependencies overlap. The draft still contributes zero to approved summaries.
12. Inspect Change Impact again. As an independent reviewer/partner, enter a rationale and record an impact reassessment. If an existing resolved finding's dependencies changed, its historical status remains resolved but validity says `needs_reassessment`, the reconciliation card warns, and readiness blocks. Perform a fresh documented independent resolution through the existing reconciliation workflow; an old invalidated signature still requires a new sign-off.
13. Verify role and clearance boundaries: st-05 cannot open/fetch tax Change Analysis; an unassigned identity is denied; an assigned uncleared identity receives masked sources. Session switches clear the workspace and its reveal mode. All actual financial corrections continue to use the original ledger approval controls.

Implementation was AI-assisted using local repository tools, the PDF skill, Python, FastAPI, React/Next.js, pytest and Playwright. No paid external tax or document service was added.
