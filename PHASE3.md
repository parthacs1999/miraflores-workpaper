# Phase 3 — Tax reconciliation and unified findings

## Scope and source brief

The original three-page case-study PDF in `docs/Case_Study_Redesign_the_Tax_Workpaper l MiraFlores AI.pdf`,
PHASE1.md, PHASE2.md, Instructions.json and the existing architecture were inspected before coding.
The brief requires calculations with evidence, independent checks, books-to-tax work, state splits
and practical review of large detail. This phase implements those capabilities to the extent
supported by the packet. It does not implement the complete case-study lifecycle or Phase 4.

Instructions.json is immutable. Reconciliations compare engine originals to source evidence;
they never overwrite return lines, approve ledger adjustments, or rerun the tax engine.

## Architecture

- `reconciliation_core.py`: reusable Rule/Context execution, Decimal parsing, printed-field
  attribution, preserved input values, source locations, computation steps, display-normalized
  comparison, and explicit unsupported/conflicting-source dispositions.
- `reconciliation_service.py`: targeted rules across all ten requested areas, transaction-level
  investment detail, asset opening balances and firm-standard prior-year comparisons.
- `finding_service.py`: unified catalog combining the unchanged legacy validator, engine
  diagnostics and new reconciliation issues. Stable rule IDs and semantic issue keys distinguish
  a computation from an underlying finding.
- `reconciliation_workflow.py`: current review state, immutable decision snapshots, explicit
  adjustment links and atomic creation of linked Phase 1 drafts.
- `ReconciliationDashboard.tsx`: grouped issue queue, calculation/source comparison, all-check
  inventory, decisions, audit history and links to evidence and corrections.

The calculation Context reads printed_content rather than treating extracted values as truth.
Printed numeric fields require a unique contextual match. Missing fields, ambiguous matches,
non-numeric inputs, missing rates and unsubstantiated facts produce explicit dispositions.
Structured prior-year, agency and parameter inputs go through the Phase 2 resolver. Each input
retains its source type; engine-supplied values are labelled `engine_reported` or documented
as an engine-consistency dependency. Later-received documents are flagged for historical
baseline comparisons. This is current-packet reconciliation, not a timeline replay.

Each result contains a stable check ID, rule version, version/tax year, tax area, jurisdiction,
method, check type, unit, expected and reported values, raw/normalized difference, tolerance
basis, rounding quantum, conclusion, inputs, source references and calculation steps.
The raw values and unrounded expected result remain visible; monetary calculations use Decimal.

## Findings, identity and deduplication

The legacy `/api/validation` contract and finding IDs remain unchanged. The unified review
catalog retains every legacy finding, current status, note and historical event. Engine diagnostic
IDs retain the Phase 2 form `engine:<version>:<code>:<original-index>`; semantic issue keys link
counterparts across versions without copying review status between versions.

Each unified finding includes `origin`, `origins`, `tax_year`, `jurisdiction`, `area`, severity,
evidence references, reconciliation IDs and aliases. Deduplication uses explicit issue mappings,
not merely shared documents or similar text. Examples:

- Mileage count and mileage deduction share one duplicated-sheet issue, with two calculations.
- The Meridian summary mismatch and omitted M18 transaction share the existing engine issue.
- Crypto basis and California AMT checks join their existing engine diagnostics.
- Three unmatched RSU-basis lots share one stock-compensation issue while retaining each lot's
  calculation and evidence.
- Prior-year checks reuse legacy variance IDs when those findings already exist.

Alias review requests write/read the canonical finding history. Existing review IDs are never
reassigned. Generic source-verification candidates and prior-year swings remain separate when
they concern different questions; shared evidence alone is not proof of a duplicate issue.
The document-destinations API now includes unified findings without changing its existing fields.

## Implemented coverage and boundaries

| Area / rule IDs | Reproducible method | Boundary |
|---|---|---|
| `business.receipts` | D14 book receipts 151,300; D15 p3 establishes card receipts already included; D21 corroborates 12,400 | Expected 151,300 versus engine 163,700; not an automatic tax correction |
| `business.software` | 6,850 less client-identified personal Spotify 216 = 6,634 | Conditional on documented classification; CPA judgment |
| `business.utilities` | Telephone 2,160 × client 70% + internet 1,320 × client 50% = 2,172 | Client estimates, not independently proven usage |
| `business.meals` | Printed 3,960 × supplied R-MEALS-50 = 1,980 | Uses supplied simplified rule |
| `business.conditional_bridge` | Books net profit plus documented add-backs/replacements, unique mileage and supplied tax depreciation/home office = 73,568 | Conditional CPA comparison; engine depreciation/elections and client estimates remain explicit assumptions |
| `business.books_bridge` | Full-finalization limitation retained under the same bridge issue | Full independently verified profit unsupported until classifications/elections/limits resolved |
| `vehicle.miles`, `vehicle.deduction` | Sum each printed trip once, excluding explicit duplicate page; 8,100 × supplied .70 = 5,670 | Does not add books fuel to standard mileage |
| `investment.bank_sweep` | Same payer/account 1,840 counted once versus combined return inclusion 3,680 | Distinct payer/account corroboration required |
| `investment.meridian_summary` | Printed summary and all printed lots 71,965 versus extracted detail 71,715 | Every extracted component retained; M18 source gain -60 has no engine line |
| `investment.lot.<doc>.<lot>` | Printed proceeds − printed/corroborated supplemental basis + wash adjustment | Includes all 260 Brightpath lots; unknown basis is not zero |
| D28 N1/N3/N4 | Supplemental basis yields gains 140, -620 and 5,880 versus reported 19,240, 18,480 and 15,300 | Supplements matched by acquisition date; all locations retained |
| `investment.crypto_basis` | Separates msg-07's approximate claim from substantiation | Referenced bank statement absent; basis/holding period unsupported |
| `depreciation.opening.<asset>.<jurisdiction>` | Sum prior annual depreciation for six prior assets, federal and California | Opening-balance proof, not independent current-year MACRS |
| `depreciation.rates` | Makes missing rate/convention support explicit | Independent current MACRS/AMT unsupported |
| `disposition.gain` | Closing proceeds less selling costs and rolled basis, using supplied current depreciation | Engine-consistency check; 105,039.99 normalizes to 105,040 |
| `disposition.unrecaptured` | Supplied lesser-of rule: straight-line depreciation bridge versus reported gain | Conditional on supplied current depreciation/gain; not independent recapture eligibility |
| `disposition.recapture` | Separates ordinary recapture classification from arithmetic | Independent legal/tax classification unsupported |
| `california.wages` | Corvane CA wages 107,100 + D73 resident-period wages 22,469 = 129,569 versus engine 218,400 | Payroll/document conflict and sourcing require judgment |
| `california.depreciation` | Supplied federal studio depreciation less supplied CA amounts = 30,400 | Engine-consistency only, not rate verification |
| `california.amt`, `california.capital_sourcing` | Explicit unsupported inventory | No CA AMT result; corrected aggregate sourcing depends on unresolved basis/allocation |
| `deductions.mortgage` | Distinct Forms 1098 13,900 + 997 + purchase points 4,800 = 19,697 | Excludes payoff interest already reported on Form 1098 |
| `deductions.property_tax` | Levy 13,420 less seller credit 6,912 = 6,508 | CPA confirmation of allocation required |
| `deductions.salt_limit` | Supplied cap/phaseout/floor applied to reported AGI/SALT inputs | Engine-consistency only; reported AGI is the engine proxy, not independently recomputed MAGI |
| `deductions.vehicle_gift` | Claimed 6,000 compared with acknowledgment gross proceeds 2,900 | Document comparison; does not assert a legally allowable deduction or exceptions |
| `deductions.cash_gift` | Explicit ambiguity/substantiation limitation | Receipt digit and missing acknowledgment language; later client claim not treated as a bank statement |
| `payments.federal_estimates` | Attributable estimates in latest pre-computation IRS snapshot: 12,000 versus 13,000 | Excludes extension/scripted later amounts; v1 has no available transcript and is unsupported |
| `payments.ca_estimates` | Only FTB payments designated 2025: 10,500 versus 14,000 | Excludes the 2024 credit; no transfer assumed |
| `payments.*_withholding` | Distinct printed W-2 boxes 2/17 = 25,400 federal / 13,130 California | Duplicate phone image excluded |
| `carryover.capital_loss_short/long` | Prior loss balances enter SchD as -3,200 / -11,000 | Initial utilization only; corrected outgoing carryovers not asserted |
| `carryover.outgoing` | Explicit incomplete corrected-roll-forward disposition | Depends on unresolved corrected gains/losses/limits |
| `k1.scorp_income`, `k1.partnership_income` | Printed K-1 income 18,400 / 8,400 versus Schedule E | Income consistency, not full basis/at-risk/passive eligibility |
| `k1.stock_basis` | Known 2022 basis plus 2023/24 income less distributions = 2,300 | Conditional on absence of other undocumented basis adjustments |
| `k1.outside_basis` | Missing basis explicitly disclosed | Capital account cannot substitute for outside basis |
| `rental.rent_a/b` | Owner statement 37,200; Austin monthly 2,250 × 9 = 20,250 | Does not prove every rental expense |
| `rental.passive_loss` | Reported current rental losses less prior suspended losses = -38,630 | Consistency only; independent allowance eligibility not asserted |
| `rental.hvac` | Separates full-system replacement invoice from capitalization judgment | Engine what-if is not independent proof |
| `variance.<line>` | Both firm prior-year amount and percent thresholds must be exceeded | Zero prior amount produces undefined percentage/judgment, not a fabricated percentage |

No supported check claims to recompute corrected total tax, QBI, SE tax, NIIT, full passive
allowance, credit eligibility, MACRS, California AMT or all carryovers. Those remain limitations.

## Materiality, rounding and conclusions

The packet specifies prior-year review when **both** absolute change exceeds $1,000 and
percentage change exceeds 10%. These standards are read from `firm.starter_standards`.
They are not silently repurposed as a universal monetary reconciliation tolerance.
No general reconciliation materiality threshold is supplied. New direct mismatches receive
review priority, not an invented assertion that they exceed a firm tax-materiality threshold.

The packet specifies whole-dollar return lines and cent-level Form 8949 detail. Comparisons
retain raw values, use the Phase 1 ROUND_HALF_UP display-normalization convention, and distinguish
an exact match, display-rounding difference and exact mismatch. This normalization is not a
claim that an independently specified engine tie-breaking rule was supplied. The numeric comparison
tolerance is zero after stated display normalization; it is not an invented firm allowance.

Other conclusions are `conflicting_sources`, `unsupported`, `judgment_required`,
`material_discrepancy` (only the specified prior-year standard), and
`not_flagged_by_firm_variance_standard`. Unsupported results retain reasons and relevant
references instead of silently disappearing or filling absent inputs with zero.

## CPA decisions and corrections

The existing persistent review workflow now accepts the unified catalog. Existing endpoints,
status vocabulary, mandatory notes and role permissions remain available. The new decision
endpoint uses stable packet staff IDs and also records authority, disposition, evidence,
packet hash and a complete finding/calculation snapshot. Status and decision event are committed
in one transaction. A resolved decision must have an explicit resolution disposition.

Dispositions are investigating, accepted-as-reported, professional judgment,
unsupported acknowledged, or correction linked. An unsupported acknowledgment documents a
scope limitation; it does not turn missing calculations into verified tax results.

Corrections are explicit Phase 1 ledger drafts. Creating a draft and its finding link is atomic;
concurrent duplicate requests cannot produce multiple active linked drafts. A
`correction_linked` resolution requires a same-version, current, approved, explicitly linked
adjustment. Phase 1 self-approval restrictions and partner thresholds still apply. Resolving
or linking an issue never approves an adjustment. Reversed/superseded/stale adjustments do
not become valid approved corrections merely because a past decision referred to them.

Historical review decisions remain historical if a linked adjustment is later reversed.
Automatic reopening/filing gates are Phase 4 and are not implemented. The dashboard displays
the adjustment's current state separately from the recorded decision. No new authentication,
firm sign-off, staffing, filing or notification workflow is introduced.

## Additive schema migration 3

Before applying changes, the existing reviews, review events, adjustment ledger and field
verification schema were inspected. Migration `003_reconciliation_reviews.sql` adds:

- `reconciliation_schema_migrations`, with migration version 3.
- `reconciliation_decisions`, storing authority, disposition, stable actor ID, evidence,
  linked adjustment, packet hash, full calculation snapshot and legacy review-event ID.
- `finding_adjustment_events`, an append-only link/unlink stream with actor, rationale and hash.
- Lookup indexes and update/delete rejection triggers for the new audit streams and existing
  `review_events`. Current `reviews` remains a mutable projection; its history is immutable.

Fresh databases bootstrap the identical legacy review table definitions with IF NOT EXISTS;
existing table definitions and rows are not rewritten. Migrations 1 and 2 remain unchanged.
The runner is idempotent. Tests verify preservation and SQLite integrity using isolated databases.

## API changes

New endpoints:

- `GET /api/reconciliations?version=v3`: all supported, matched, conditional and unsupported checks.
- `GET /api/unified-findings?version=v3`: grouped catalog data, current reviews and linked corrections.
- `GET /api/unified-findings/{id}/history?version=v3`: legacy events, documented decisions and link history.
- `POST /api/reconciliation-decision?finding_id=...&version=v3`: documented review decision.
- `POST /api/reconciliation-links?finding_id=...&version=v3`: explicit link or unlink.
- `POST /api/reconciliations/{check_id}/adjustment?version=v3`: atomically create/link a Phase 1 draft.

Decision body: `actor_id`, `status`, `note`, `authority`, `disposition`, `refs`, optional
`adjustment_id`. Correction body: `actor_id`, `note`, `authority`. Link body:
`actor_id`, `adjustment_id`, `note`, `action` (`link` or `unlink`). Unknown IDs/versions return
404; role violations 403; unsupported corrections, stale/invalid linked corrections or
conflicting link state 409; missing rationale/authority or unresolved evidence 400;
malformed bodies 422. Legacy error handling and required response fields remain intact.

Additive extensions: `/api/reviews` includes unified issues, old review-decision/history APIs
accept canonical IDs and aliases, and document destinations include unified findings. Existing
validation, evidence resolution/verification, engine packet and adjustment contracts remain.
The Phase 1 one-to-one payment method now also supports California 540NR lines 71/72,
so payment reconciliation drafts change payments/balance, not total tax; approval controls are unchanged.

## Complete demonstration workflow

From `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m app.migrate
PYTHONDONTWRITEBYTECODE=1 .venv/bin/uvicorn app.main:app --reload --port 8000
```

From a second terminal in `frontend`:

```sh
npm run dev
```

1. Open http://localhost:3000, choose v3, then **Reconciliation Dashboard**.
2. Search `business.receipts` and inspect **Duplicated card receipts**. The comparison shows
   expected 151,300, original reported 163,700, difference 12,400, method, tolerance basis,
   source values and calculation steps. Open D15 page 3, then its supporting D15 document,
   expand extracted fields, and open ev-0109 for Phase 2 source/field verification.
3. In the reconciliation review panel select Priya (st-01). Enter notes and authority naming
   D14, D15 page 3 and D21. Click **Create linked adjustment draft**. It creates a separate
   immutable-baseline proposal and audit link, not an engine update.
4. Click **Open adjustment <id>**. Submit it with a note, switch to Helen (st-03), enter a
   partner rationale and approve. Priya cannot approve her own work; Daniel cannot approve
   this greater-than-$1,000 federal effect. The ledger shows estimated effects -4,402 federal
   and -384.40 California, as in Phase 1.
5. Return to Reconciliation Dashboard and inspect receipts again. Choose the approved
   correction, status `resolved`, disposition `correction_linked`, and document notes and
   authority. Save. The decision and calculation snapshot are retained in append-only history.
6. Refresh and reopen the issue. Status, notes, authority and correction persist. Original
   reported receipts still show 163,700; the approved ledger overlay remains separate.
7. Search `vehicle`, select its single mileage issue, then expand **All checks** and select
   `vehicle.deduction`. Both 8,100 miles and the 5,670 deduction are retained under one issue.
8. Select `california.amt` in All checks. It displays an unsupported expected value, the
   original placeholder zero and the explicit missing calculation. Draft creation is disabled.
   Filter jurisdiction California to confirm the issue remains visible.
9. Inspect the stock-compensation issue and use All checks to select each N1/N3/N4 lot. Inspect
   supplemental basis and its acquisition-date attribution; compare against the engine gain.
   Brightpath's 260 matched lot checks remain in the all-check inventory rather than generating
   260 duplicate alerts.
10. Inspect estimated payments, itemized deductions and prior-year issues. The firm threshold
    applies only to prior-year variances. Review decisions remain separate from numerical
    reconciliation results. Legacy Review Findings and document reverse tracing show the same IDs.
11. Optionally reverse the approved correction through Phase 1. Its approved-summary contribution
    disappears, link history remains, and its current reversed state is visible. The prior CPA
    decision remains historical; automatic reopening is not claimed.

## Verification commands

From `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

From `frontend`:

```sh
./node_modules/.bin/tsc --noEmit --incremental false
npm run lint
npm run test:e2e
```

The Playwright command runs `npm run build` into `.next-e2e`, serves that production artifact
on 3100 and uses the disposable SQLite API on 8100. Existing servers/database are not reused.
Build/browser execution requires network access for existing Google Fonts and local worker,
server and Chromium permissions. No assertions, test skips or source lint rules were weakened.

## Known limitations

- The supported rules are packet-specific deterministic parsers, not a general OCR/tax engine.
- Conditional source comparisons and internal consistency are labelled distinctly from independent proof.
- Complete corrected books-to-tax profit, full gain/source aggregation, missing crypto basis,
  independent MACRS/recapture eligibility, full outgoing carryovers, outside basis and CA AMT
  are explicitly not complete. No missing tax thresholds or inputs are invented.
- Review snapshots have a fixed rule-version marker; automatic reopening after rule/source or
  correction changes is deferred to Phase 4. Current ledger state remains visible.
- The legacy review API keeps its original demo role/name contract. New detailed decisions use
  stable packet IDs, but there is still no authenticated identity provider.
- Audit triggers protect application writes, not an administrator who can alter SQLite schema.
- The source PDF's full lifecycle brief is broader than Phase 3. No Phase 4 feature is claimed.

## File manifest relative to Phase 2

Created:

- `PHASE3.md`
- `backend/app/reconciliation_api.py`
- `backend/app/migrations/003_reconciliation_reviews.sql`
- `backend/app/services/reconciliation_core.py`
- `backend/app/services/reconciliation_service.py`
- `backend/app/services/finding_service.py`
- `backend/app/services/reconciliation_workflow.py`
- `backend/tests/test_reconciliation_rules.py`
- `backend/tests/test_unified_findings.py`
- `backend/tests/test_reconciliation_workflow.py`
- `frontend/src/components/ReconciliationDashboard.tsx`
- `frontend/tests/reconciliation.spec.ts`

Modified:

- `backend/app/main.py` — register reconciliation routes.
- `backend/app/migrate.py` — report additive migration 3.
- `backend/app/adjustment_api.py` — translate existing ReviewError in shared invocation.
- `backend/app/services/review_service.py` — unified catalog, aliases and transactional decision snapshots.
- `backend/app/services/adjustment_service.py` — supported one-to-one California payment corrections.
- `backend/app/services/document_accountability_service.py` — unified reverse-trace findings.
- `backend/data/reviews.db` — additive migration 3 only, preserving previous records.
- `frontend/src/app/page.tsx` — dashboard and correction navigation.
- `frontend/src/components/AdjustmentWorkspace.tsx` — open linked adjustment and its audit history.

The uploaded source PDF, Instructions.json, PHASE1.md, PHASE2.md, migrations 1/2 and all pre-existing
tests remain unchanged. Temporary PDF-reader tooling was installed under /tmp only, not as a project dependency.

## Final verified acceptance result

- **260 pytest cases passed**, including all 163 pre-existing backend tests.
- **14 Playwright scenarios passed**, including all 11 pre-existing browser scenarios.
- All **174 previous tests remain passing**; **274 tests** now pass in total.
- Standalone TypeScript and ESLint passed. No existing test assertions were weakened.
- The optimized production build passed in `.next-e2e` and was the artifact exercised by Playwright.
- Current v3 inventory: **419 documented checks** and **211 unified issues**. Check conclusions:
  303 exact matches, 2 display-rounding differences, 11 exact mismatches, 10 judgment-required,
  11 unsupported, 48 firm-standard prior-year discrepancies, and 34 prior-year checks not flagged
  by that standard. These categories do not imply a completed independent tax computation.
- SQLite `PRAGMA integrity_check`: **ok**. Migration 3 preserves the previous table definitions
  and every review, review-event, adjustment, adjustment-revision, adjustment-event and field
  verification row. The application database contains zero test decisions or link events.
- Packet SHA-256 is unchanged:
  `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`.
- Initial sandbox-only browser startup could not bind port 8100. The escalated production-build
  suite passed. Its first run also exposed a California AMT jurisdiction classification bug;
  the implementation was corrected, a regression test was added, and the full suite then passed.
- The pre-existing Starlette/httpx deprecation warning remains. No test failures remain.

Every registered check is exercised for reproducibility, method, traceable inputs and explicit
disposition. Unsupported tax calculations remain unsupported; their presence is not a claim
of completed tax-law or engine functionality. Phase 4 has not been implemented.
