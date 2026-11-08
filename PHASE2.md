# Phase 2 — Complete evidence resolution and document accountability

Phase 2 adds typed evidence navigation, reverse document tracing, evidence-based
accountability and persistent human field verification. The original packet is
immutable. Tax calculations, Phase 1 adjustment approval rules and the independent
validator are not replaced. No Phase 3 tax reconciliation or workflow is added.

## Architecture

`evidence_service.py` provides the shared version-aware resolver and finite evidence
graph. Each result contains the original reference, version, a typed kind, status,
label, value, location, related references and supporting document IDs. Unresolved
results contain explicit `unknown_format`, `invalid_reference`, `missing_reference`
or `unknown_version` reasons. Null and zero values are valid resolved values.

Supported formats:

| Format | Resolution |
|---|---|
| `ev-0016` | Extracted value and source document/page |
| `D08` | Whole document |
| `doc:D31#page32` | Specific printed page, including unextracted pages |
| `py:/carryovers_into_2025/capital_loss_short` | RFC 6901 pointer inside prior years |
| `agency:/irs_account_transcript_2025/0` | RFC 6901 pointer inside agency records |
| `qa-14`, `msg-07`, `call-01` | Questionnaire, message, call note |
| `asset:SAC-BLDG` | Selected-version asset, with prior-year fallback |
| `household:theo` | Household member |
| `ref:param.mileage_rate` | Engine parameter, including nested parameter paths |
| `ref:fx.SEK.2025_year_end` | Packet's engine FX rate |
| `timeline:extension-2026-04-14` | Timeline event |
| `F1040.11` | Selected-version return line and its dependencies |

Pointers support arrays, empty keys, nulls and `~0`/`~1` escaping. Invalid escapes,
noncanonical array indices, missing records and unknown references remain visible.
The graph retains unresolved nodes and records cycles. Explicit source fields,
prior-return `line_sources`, nearest ancestor provenance and printed structured-record
cross-references provide supporting document links. It does not infer tax relevance
from arbitrary narrative similarities. Existing lineage envelopes retain their fields
and gain a typed `resolution` object. Phase 1 evidence validation now accepts the
additional documented formats through the same resolver.

`document_accountability_service.py` follows those source links and computes the
transitive closure of calculation inputs. The existing destinations endpoint retains
its original fields and adds associated independent findings and engine diagnostics.
The frontend exposes direct calculations, indirect calculations, finding explanations
and extracted fields. Links navigate back into lineage or source verification.

The accountability dashboard covers every one of the 74 documents. Its dispositions
are deliberately nonexclusive, with a supporting reason and references for each:

- `used`: declared used by the engine or explicitly linked through provenance.
  This is not a statement that every extracted value was used or verified.
- `superseded`: explicitly marked superseded by the selected engine version.
- `duplicate`: explicit packet evidence identifies a second image of another document.
- `unextracted`: extraction is partial or absent; extraction status and unread pages
  remain separate fields.
- `unused`: neither declared use nor supported calculation provenance, excluding
  whole-document duplicates and superseded documents. This does not mean irrelevant.
- `requires_review`: unresolved use, conflicting metadata, partial extraction, or
  duplicated pages within an otherwise useful document.

D10's whole-document duplicate relationship is grounded in the engine's D09/D10 note.
D23 page 3 repeats page 2 and explicitly describes a second scan; the whole document
is not labelled duplicate. D30 remains both superseded and partially unextracted.
D31 remains used with an unread page 32. Counts can therefore exceed 74.

## Source matching and human verification

Automatic matching produces source candidates with character offsets, exact text,
context, field anchors and line/column locations. It requires a unique named box,
Box 12 subcode, brokerage lot/column or exact label attribution before reporting
`supported`. A single amount somewhere on a page is only a candidate. Multiple
unattributed matches are `ambiguous`; repeated amounts can be disambiguated by a
unique field anchor. Synthetic page coordinates are retained as packet metadata,
not treated as reliable physical locations.

The legacy automatic status values remain `supported`, `unverified`, `missing_source`.
Additional `assessment` values explain ambiguity, candidate-only matches and absent
matches. Automatic matching always reports `automatic=true`, `human_verified=false`.
It never creates a human attestation.

Human verification records include evidence ID and its field snapshot, return version,
verifier ID/name/role/credential, method, source reference, server timestamp, notes,
packet SHA-256, source snapshot, exact quote offsets where applicable and prior-event
link. Staff with a packet CPA credential receive `cpa_attestation`; others receive
`staff_attestation`. Outcomes are `confirmed`, `needs_review` or `revoked`.

Every event is append-only. Latest state is derived from the event stream; superseded
historical confirmations do not count as current. A changed packet fingerprint makes
the latest confirmation stale. Expected sequence numbers and `BEGIN IMMEDIATE`
prevent concurrent overwrites. Revocation requires an existing non-revoked record.
Document-page methods require an exact, nonempty, in-bounds source quote. Method/source
compatibility is checked server-side. Automatic match status and Phase 1 adjustment
approvals are not changed by human verification.

## Additive migration

Before changes, SQLite contained legacy reviews/history and the Phase 1 adjustment
ledger, revisions, events and migration registry. Migration
`backend/app/migrations/002_field_verifications.sql` creates only:

- `evidence_schema_migrations` with migration version 2 and application timestamp.
- `field_verification_events` with a unique `(version, evidence_id, sequence)` key.
- A field/version lookup index and triggers rejecting updates/deletes to history.

The runner applies numbered SQL files transactionally and idempotently. The Phase 1
migration registry remains unchanged. Existing review and adjustment tables, their
schemas and rows are preserved. Tests include a populated Phase 1 ledger/approval
before migration 2. The same `REVIEW_DB_PATH` override isolates test databases.

Run manually from `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m app.migrate
```

The new verification endpoints also migrate lazily when opening their database.

## API changes

New endpoints:

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/evidence-resolution?ref=...&version=v3` | Typed single resolution, including explicit unresolved results |
| GET | `/api/evidence-graph?ref=...&version=v3` | Typed graph, unresolved nodes, cycles and document provenance |
| GET | `/api/document-accountability?version=v3` | All 74 documents, nonexclusive dispositions and reasons |
| GET | `/api/documents/{id}/evidence` | Complete extracted-field inventory for a document |
| GET | `/api/verification-metadata` | Staff identities/credentials, methods, outcomes |
| GET | `/api/field-verifications/{evidence_id}?version=v3` | Current state and complete audit history |
| POST | `/api/field-verifications/{evidence_id}?version=v3` | Append a human attestation or revocation |

POST body:

```json
{
  "verifier_id": "st-02",
  "method": "agreed_to_source_document",
  "source_ref": "doc:D08#page1",
  "status": "confirmed",
  "notes": "Compared the extraction to the specific Box 1 source field.",
  "expected_sequence": 0,
  "quote": {"start": 144, "end": 154, "text": "104,600.00"}
}
```

The quote above uses the actual D08 Box 1 text location. Use the current sequence
when appending another attestation.
Supported methods are the packet's five starter verification types. Non-document
methods use `quote: null` and an appropriate resolved client, prior-year, calculation,
parameter, FX, asset or agency source. Invalid verifier permissions return 403,
missing evidence/version 404, stale sequences 409, invalid source/quote/method 400,
and malformed payloads 422. Resolver failures are explicit typed HTTP 200 results;
transport errors remain separate from unresolved evidence.

Additive changes to existing endpoints:

- `/api/lineage/{key}`: each source gains its typed resolution; existing envelopes stay.
- `/api/documents/{id}/destinations`: structured provenance links plus
  `associated_findings` and `trace_scope`, preserving all original fields.
- `/api/source-verification` and `/{id}`: candidates, field attribution, ambiguity
  and automatic/human distinction; existing status vocabulary and keys stay.
- Phase 1 adjustment references accept all valid documented source formats; approval
  states, tax methods, threshold checks and ledger contracts are preserved.

## Complete demonstration workflow

Start the API from `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/uvicorn app.main:app --reload --port 8000
```

Start the frontend in another terminal from `frontend`:

```sh
npm run dev
```

1. Open http://localhost:3000 and select v3.
2. Open **Document Accountability**. Confirm all 74 documents are listed. Filter
   `superseded`: D30 shows superseded plus incomplete extraction. Clear the filter,
   search D23, and inspect the page-3/page-2 duplicate explanation.
3. Search D09 and choose **Inspect D09 document**. Expand **Reverse document tracing**.
   Inspect direct wages calculations, indirect totals such as F1040.24, and associated
   findings. Select a calculation to open its lineage in the inspector.
4. Open **Evidence Resolver**. Resolve `ref:fx.SEK.2025_year_end` (9.71),
   `py:/carryovers_into_2025/capital_loss_short`, `agency:/irs_account_transcript_2025/0`,
   `asset:SAC-BLDG`, `msg-07`, and `doc:D31#page32`. Supporting links remain navigable.
   Enter `py:/missing-record` to see an explicit unresolved reason.
5. Open **Tax Return**, search F1040.1a, select wages, and open ev-0016.
   Confirm the automatic field anchor is Box 1, with exact source offsets. It is not
   human verification. Scroll to **Human field verification**.
6. Select Daniel Ortiz (st-02, CPA). Keep `agreed_to_source_document` and
   `doc:D08#page1`. Choose the specific source location for 104,600.00, enter notes,
   check **I reviewed the specific field and source**, then **Record field verification**.
   The independent human status becomes `confirmed · cpa_attestation · st-02`.
7. Refresh and repeat the ev-0016 navigation. The attestation, timestamp, selected
   source location and notes persist. Select the source location again, choose
   **Revoke previous attestation**, enter a reason, check the review box and record.
   Both events remain, and the latest state becomes revoked. Automatic matching is unchanged.
8. For ambiguity, open **Document Explorer**, search D23, select it and expand
   **Extracted fields**. Open ev-0169 (trip 6 miles). Automatic assessment is ambiguous,
   with no asserted single source highlight. Identical text occurs more than once.
   Choose a specific occurrence after reviewing context before recording any attestation.
   The save button stays disabled until that location, notes and review acknowledgement exist.
9. Reopen **Tax Adjustments** to demonstrate the Phase 1 receipts workflow. Its ledger
   and independent partner-approval controls operate as before; verification does not
   silently approve an adjustment or clear a tax finding.

## Tests and acceptance verification

Run from `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

Run from `frontend`:

```sh
./node_modules/.bin/tsc --noEmit --incremental false
npm run lint
npm run test:e2e
```

`test:e2e` executes `npm run build` into `.next-e2e`, starts that production artifact
on port 3100 and a disposable SQLite-backed API on 8100, then runs Playwright. The
application database and existing servers on 3000/8000 are not reused. Google Fonts
network access, local Turbopack worker ports and Chromium launch permissions are required.
No tests or source lint rules are disabled. All 74 Phase 1 pytest cases and all seven
Phase 1 browser scenarios remain unchanged.

Coverage includes every reference format, all engine source references in every version,
missing/invalid references, pointer escapes/nulls/arrays, graph cycles, nearest-record
provenance, duplicates and partial extraction, direct/indirect tracing and findings,
ambiguous amounts and lot columns, staff/CPA distinctions, exact quote validation,
method compatibility, persistence, revocation, concurrency, stale fingerprints,
append-only audit, migration preservation and packet immutability.

## Known limitations

- Staff identities are selected demo identities, without authenticated identity assurance.
- This is simulated text rendering, not PDF/image bounding-box verification. Conservative
  matching leaves unsupported fields unverified rather than guessing their locations.
- Human attestations record professional judgment; they do not automatically prove the
  selected source is relevant or correct a tax value. A needs-review outcome is available.
- Accountability is derived from packet facts, not editable disposition overrides. `Used`
  means declared or traceable use, not filing readiness, complete extraction or CPA sign-off.
- Reverse tracing follows supported packet references and calculation inputs. Missing
  source links are not fabricated. Broad explicit source pointers can lead to broad links.
- Narrative provenance such as `prior_preparer_depreciation_schedule`, a client worksheet
  description and timeline token `v2` has no documented reference identifier; these remain
  visible as unresolved graph nodes. Every documented direct engine source format resolves.
- No tax-error detection, filing gates, firm-policy administration, identity-provider
  integration, retention workflow or Phase 3 reconciliation was added.
- Audit triggers protect normal writes, not a database administrator who can alter schema.

## File manifest relative to Phase 1

Created:

- `PHASE2.md`
- `backend/app/evidence_api.py`
- `backend/app/migrations/002_field_verifications.sql`
- `backend/app/services/evidence_service.py`
- `backend/app/services/document_accountability_service.py`
- `backend/app/services/field_match_service.py`
- `backend/app/services/verification_service.py`
- `backend/tests/test_evidence_resolution.py`
- `backend/tests/test_document_accountability.py`
- `backend/tests/test_field_matching.py`
- `backend/tests/test_field_verifications.py`
- `frontend/src/components/evidence-types.ts`
- `frontend/src/components/EvidenceResolver.tsx`
- `frontend/src/components/DocumentAccountability.tsx`
- `frontend/src/components/DocumentInspector.tsx`
- `frontend/src/components/FieldVerification.tsx`
- `frontend/tests/evidence-phase2.spec.ts`

Modified:

- `backend/app/main.py` — register new router.
- `backend/app/migrate.py` — discover and apply numbered additive migrations.
- `backend/app/services/adjustment_service.py` — validate source references through resolver.
- `backend/app/services/lineage_service.py` — resolved sources and document tracing.
- `backend/app/services/source_verification_service.py` — field-aware automatic assessment.
- `backend/data/reviews.db` — additive migration 2 only, preserving existing data.
- `frontend/src/app/page.tsx` — new workspace tabs, document inspector and reference navigation.
- `frontend/src/components/SourceVerification.tsx` — locations, ambiguity and human verification.
- `frontend/src/components/workpaper-types.ts` — typed source-resolution extension.
- `frontend/src/components/ReviewWorkspace.tsx` — each finding reference is navigable.
- `frontend/src/components/AdjustmentWorkspace.tsx` — all supported adjustment evidence is navigable.

`Instructions.json`, the Phase 1 migration, all existing tests and PHASE1.md remain unchanged.

## Verified acceptance result

- Pytest: **163 passed**, including all 74 Phase 1 backend tests.
- Playwright: **11 passed**, including all seven Phase 1 browser scenarios.
- Standalone TypeScript: passed (`tsc --noEmit --incremental false`).
- ESLint: passed; source rules and existing test assertions are unchanged.
- Production build: passed in `.next-e2e` and served for the full browser suite.
- All **81 previously passing tests** are preserved; **174 tests** now pass in total.
- SQLite integrity check: `ok`. Legacy review rows are unchanged; migration 2
  preserves the Phase 1 schema and ledger. The application database contains no
  test adjustment or verification records.
- Original packet SHA-256 is unchanged:
  `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`.
- Initial sandbox-only browser startup was blocked from binding port 8100; the
  escalated isolated build and suite passed. The existing Starlette/httpx
  deprecation warning remains; no test failures remain.

Phase 2 acceptance criteria are verified. Phase 3 has not been started.
