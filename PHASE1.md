# Phase 1: audited tax adjustments

The original packet and existing API response shapes are unchanged. Engine lines
remain the baseline; adjustments are a separate overlay. Phase 2 is not implemented.

## Run and demonstrate

From `backend`:

```sh
.venv/bin/python -m app.migrate
.venv/bin/uvicorn app.main:app --reload --port 8000
```

From a separate terminal in `frontend`:

```sh
npm run dev
```

1. Open http://localhost:3000, choose return v3, and click **Tax Adjustments**.
2. Choose **Priya Raman (st-01)** as Adjustment staff.
3. Click **Load business receipts example**, then **Save adjustment draft**.
   This records `SchC.1`: engine 163,700; proposed 151,300; delta -12,400.
   Open D14, D15, D21 or ev-0109 using the evidence buttons.
4. Enter an action note and click **Submit adjustment**. Drafts and submissions
   contribute zero to approved totals.
5. Daniel Ortiz (st-02) cannot approve this adjustment: its federal effect exceeds
   $1,000. Priya cannot approve her own work. These rules also apply to direct API calls.
6. Select **Helen Strand (st-03)**, enter a partner review note, and click
   **Approve adjustment**. Expected tax effects: federal -4,402.00; California
   -384.40. Estimated total tax: federal 77,560.00; California 18,489.60.
   Estimated balances: federal -182.00; California -8,640.40 (negative means overpayment).
7. Refresh, reopen Tax Adjustments, and select the adjustment. Its state, content,
   approvals and complete audit snapshots persist.
8. As Helen, enter a note and **Reverse adjustment**. Its contribution becomes zero;
   the approved and reversal events remain visible. Engine return lines never change.
9. Alternatively, **Supersede with new draft** retires the approved adjustment and
   creates a linked draft. The old contribution is immediately removed. Revise the
   replacement as Priya, resubmit, and obtain fresh independent partner approval.
   Rejected adjustments may also be revised and resubmitted.

If an existing submitted or approved adjustment overlaps, resolve it first. Drafts
can coexist, but overlapping submissions/approvals are blocked. Terminal reversed
and superseded records remain available in the list and audit history.

## Schema and migration

Before implementation, `reviews.db` contained `reviews`, `review_events`, and SQLite's
sequence table. Migration `backend/app/migrations/001_adjustments.sql` is additive,
idempotent and transactional. It creates:

- `adjustment_schema_migrations`: migration version and application time.
- `adjustments`: current state/revision/sequence, engine version, packet SHA-256,
  stable preparer IDs, and optional superseded predecessor.
- `adjustment_revisions`: immutable payloads for every content revision.
- `adjustment_events`: immutable action records containing actor ID/role, note,
  previous/new states, revision/sequence, timestamp and complete snapshot.

Update/delete triggers protect both append-only tables. Existing review tables and
rows are not changed. `BEGIN IMMEDIATE` serializes writes; expected sequence numbers
prevent stale edits or duplicate approvals. Migration also runs lazily when the new
APIs first connect, using the same `REVIEW_DB_PATH` override as legacy review storage.

Transitions: draft → submitted → approved or rejected; rejected → draft by revision;
approved → reversed or superseded. Supersession atomically creates a linked draft.
Only current approved, fingerprint-matching adjustments contribute to summaries.
No destructive adjustment endpoint exists.

## New API contracts

- `GET /api/adjustment-metadata?version=v3`: packet staff, numeric targets, demo preset.
- `GET /api/adjustments?version=v3`: all states and current content, stale/conflict flags.
- `POST /api/adjustments?version=v3`: create draft.
- `GET /api/adjustments/{id}`: current adjustment.
- `POST /api/adjustments/{id}/revisions`: append a content revision to draft/rejected work.
- `POST /api/adjustments/{id}/actions`: submit, approve, reject, reverse, supersede.
- `GET /api/adjustments/{id}/history`: ordered append-only audit snapshots.
- `GET /api/workpaper-summary?version=v3`: engine summary plus approved estimated overlay.

Creation body: `actor_id`, `target`, `proposed_value` (decimal string), `rationale`,
`authority`, `refs` (existing extracted IDs, document-page references, client record IDs,
or baseline line keys). Revisions add `expected_sequence`. Action bodies contain
`actor_id`, `expected_sequence`, `action`, and `note`. Conflicts/stale sequences return
409, forbidden approval returns 403, missing records return 404, malformed input 422.
Client-supplied roles, effects, engine values and approval flags are rejected.

## Calculation assumptions and limits

Decimal arithmetic, two decimal places and ROUND_HALF_UP are used. Partner thresholds
use absolute **unrounded** tax effects; either jurisdiction over $1,000 requires the
packet partner. All content authors are retained and excluded from approving their work.
Recording a supersession alone does not make its actor an author of the unchanged
replacement content; actually revising that content does.

A conservative target allowlist maps wages, interest/dividends, Schedule C receipts,
profit and selected expenses, selected itemized/SALT lines, and California-source
wages to supplied version-specific marginal rates. Expense changes invert the profit
sign. Wages use the packet's California-source assumption; Schedule C uses its
residency-prorated rates. California-source wage changes affect California only.
Selected federal leaf payments/credits use the packet's 1:1 rule. A payment changes
payments/balance, not total tax. Unsupported targets (including depreciation-method choices, SEP/SEHI, basis and
other complex changes) are flagged manual review with unknown effects and cannot
be approved. Stored what-if alternatives are not selectable in this phase.

These are estimates, not tax-engine recomputations. AGI, taxable income, penalties,
carryovers and downstream engine lines are never recomputed. Caps, thresholds, QBI
interactions and combinations of changes require professional review. The summary
adds approved estimated effects to the selected baseline; it is not a filing-ready
return. Overlap detection conservatively blocks identical targets, ancestor/descendant
targets in the packet graph, and explicitly shared extracted evidence. It cannot
infer arbitrary semantic duplication from unrelated narrative references.

Staff identity is selected for this local demonstration. The server derives roles
from stable packet IDs, checks active dates, enforces independent review and partner
thresholds. There is no authenticated identity provider yet; this is not production
identity assurance. Audit triggers protect ordinary database writes, not a database
administrator with schema privileges. Changed packet fingerprints are excluded and
blocked from action; the packet is expected to remain immutable.

## Verification

From `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

From `frontend`:

```sh
./node_modules/.bin/tsc --noEmit --incremental false
npm run lint
npm run build
npm run test:e2e
```

Playwright builds a separate production artifact in `.next-e2e`, serves it on 3100,
and launches a disposable SQLite-backed API on 8100. Existing servers on 3000/8000
are not reused. The original four browser scenarios retain all assertions; only
URLs became configurable. Browser tests run serially against one disposable database.
Backend tests use individual temporary databases and verify migration preservation,
audit immutability, calculation signs/rounding, both approval thresholds, independence,
all states, concurrency, conflicts, fingerprints and unchanged engine/packet data.

Builds require Google Fonts network access and permission for Turbopack worker ports;
Playwright also needs permission to launch local servers and Chromium.

Final verified results: 74 pytest cases and 7 Playwright scenarios pass, including
all 33 original backend cases and all 4 original browser scenarios. Standalone
TypeScript and ESLint checks pass. The isolated `.next-e2e` production build passes
and is the artifact used by Playwright. Earlier ordinary `.next` build attempts
were blocked by Google Fonts network access and then local worker-port sandbox
restrictions; no compiler or application failure remains in the isolated build.
Pytest retains the existing Starlette/httpx deprecation warning.

## Exact file manifest

Created:

- `PHASE1.md`
- `backend/app/adjustment_api.py`
- `backend/app/migrate.py`
- `backend/app/migrations/001_adjustments.sql`
- `backend/app/services/adjustment_service.py`
- `backend/run_e2e.py`
- `backend/tests/test_adjustments.py`
- `frontend/playwright.config.ts`
- `frontend/src/components/AdjustmentWorkspace.tsx`
- `frontend/src/components/workpaper-types.ts`
- `frontend/tests/adjustments.spec.ts`

Modified:

- `backend/app/main.py`
- `backend/data/reviews.db` (additive schema only; legacy rows unchanged)
- `frontend/.gitignore`
- `frontend/eslint.config.mjs` (ignore generated E2E output, retaining source rules)
- `frontend/next.config.ts`
- `frontend/package.json`
- `frontend/src/app/page.tsx`
- `frontend/tests/finding-evidence.spec.ts` (configurable URL only)
- `frontend/tests/review-persistence.spec.ts` (configurable URLs only)
- `frontend/tests/source-verification.spec.ts` (configurable URL only)
- `frontend/tests/workpaper.spec.ts` (configurable URL only)
- `frontend/tsconfig.json` (generated E2E types included by Next.js)

Packet SHA-256 remains
`ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`.
