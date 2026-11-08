# Phase 4 — Firm Workflow, Permissions, and Filing Readiness

## Scope and assurance

Phase 4 adds firm workflow over the existing immutable tax packet, evidence resolver, reconciliation catalog, and adjustment ledger. It does not rerun the tax engine, file a return, manufacture missing inputs, or implement Phase 5/6. The real packet remains **filing-blocked**.

Demonstration sessions select packet staff IDs; they do not authenticate the person operating the browser. All demonstration sign-offs are labeled accordingly. Every sign-off has `legal_signature=0`, enforced by SQLite. Configured-credential sessions prove possession of an operator-provisioned secret, not legal electronic-signature assurance.

Sources reviewed: the original case-study PDF in `docs`, `Instructions.json`, PHASE1.md, PHASE2.md, PHASE3.md, existing routes, services, SQLite schema, frontend, and tests. Packet staff roles, active dates, clearances, assignments, six deadlines, five verification methods, required engagement steps, and starting firm thresholds seed the workflow. Later scripted timeline events do not automatically complete any prerequisite.

`Instructions.json` remains unchanged: SHA-256 `ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19`.

## Architecture

- A shared ASGI security boundary covers existing and new endpoints, nested evidence, document text, histories, error responses, and API documentation. Defaults fail closed. Actor IDs supplied through legacy contracts must match the server session.
- Opaque HttpOnly session cookies and hashed CSRF tokens are stored server-side. Mutations require an allowed Origin and CSRF token. Identity switching revokes the previous session; in-flight responses are checked again before delivery.
- Packet-defined roles cannot be promoted through assignments. Engagement membership controls access; write authorization is scoped by tax area. Assigned practice staff may read engagement evidence in masked form. A firm administrator manages metadata and policies without receiving tax-evidence privileges.
- Workflow services maintain current projections in a consolidated entity table and preserve complete before/after events. Policies are immutable revisions. Existing financial states, finding IDs, and audit tables retain their contracts.
- A SQLite connection hook performs dependency validation and sign-off invalidation before the originating transaction commits. `BEGIN IMMEDIATE` serializes competing writes; optimistic revision/sequence/digest checks reject stale actions. Legacy-route writes recheck assignment and independence at commit.
- Sign-offs bind source graphs, independently reproduced checks, relevant adjustments, verification events, finding decisions/links, review projections, substantive authors, scoped assignments, policy, ownership, and prerequisite sign-offs. Immutable packet graph projections are cached by policy; mutable database dependencies are always read again.
- The frontend provides sessions, assignments/ownership, standards, diligence/elections/judgments/questions, blocking notes, sign-offs, readiness, tasks, notifications, sensitive-access controls, and audit views. Existing tax workspaces use the same session transport and server-selected identity. Cross-tab broadcasts clear stale workspaces; browser history restoration reloads the session.

## Exact Phase 4 file manifest

New files:

| File | Purpose |
|---|---|
| `backend/app/migrations/004_firm_workflow.sql` | Additive tables, indexes, immutable/append-only triggers |
| `backend/app/security.py` | Settings validation, sessions, CSRF, authorization boundary, redaction, access audit |
| `backend/app/security_context.py` | Request principal context shared with synchronous services |
| `backend/app/workflow_connection.py` | Transactional dependency invalidation hook |
| `backend/app/workflow_api.py` | Typed workflow request models and endpoints |
| `backend/app/services/workflow_service.py` | Workflow transitions, policy, assignments, dependencies, readiness |
| `backend/app/services/firm_policy.py` | Read committed strict-mode standards without nested write locks |
| `backend/run_secure.py` | Supported launcher with request access logging disabled |
| `backend/run_workflow_e2e.py` | Disposable strict-mode browser server |
| `backend/tests/conftest.py` | Explicit isolated legacy regression configuration |
| `backend/tests/test_firm_workflow.py` | Strict-mode acceptance/security/concurrency tests |
| `frontend/src/components/session.tsx` | Credentialed, no-store, CSRF-aware transport and session context |
| `frontend/src/components/FirmWorkflow.tsx` | Complete workflow UI and session gate |
| `frontend/playwright.workflow.config.ts` | Separate strict browser servers/build/database |
| `frontend/workflow-tests/firm-workflow.spec.ts` | Six strict browser acceptance scenarios |
| `PHASE4.md` | This architecture, verification, and demonstration record |

Modified files:

| File | Phase 4 change |
|---|---|
| `backend/app/main.py` | Shared boundary, workflow routes, explicit application factory, strict CORS |
| `backend/app/services/review_service.py` | Hooked SQLite connection and deterministic connection closure |
| `backend/app/services/adjustment_service.py` | Enforce active partner threshold without changing stored engine values; compare unrounded effects |
| `backend/app/services/verification_service.py` | Active verification-method policy; snapshot session assurance without altering legacy assurance enums |
| `backend/app/services/reconciliation_service.py` | Apply strict-mode versioned prior-year variance standards |
| `backend/run_e2e.py` | Explicit temporary legacy test mode and disabled URL access logs |
| `frontend/src/app/page.tsx` | Session gate, common transport, explicit document accessible labels; selecting the current version preserves loaded lines |
| `frontend/src/components/AdjustmentWorkspace.tsx` | Common transport and session-bound actor |
| `frontend/src/components/ReviewWorkspace.tsx` | Common transport and session-bound role/name |
| `frontend/src/components/SourceVerification.tsx` | Common transport |
| `frontend/src/components/FieldVerification.tsx` | Session-bound verifier |
| `frontend/src/components/ReconciliationDashboard.tsx` | Session-bound reviewer |
| `frontend/src/components/evidence-types.ts` | Common transport for all evidence clients |
| `frontend/playwright.config.ts` | Preserve all 14 assertions/scenarios; webpack production build for this environment |
| `frontend/.gitignore` | Ignore separate strict production build |
| `frontend/eslint.config.mjs` | Exclude generated strict build artifacts |
| `frontend/tsconfig.json` | Next-generated type directories for the strict production build |

Existing uncommitted Phase 1–3 changes were present before Phase 4. This manifest identifies Phase 4 work rather than attributing the entire worktree diff to this phase. No dependency additions or original test assertion changes were required.

## Additive database migration

Migration 004 creates eight tables and does not replace, rename, delete, or rewrite existing tax/review tables:

| Table | Contents / durability |
|---|---|
| `workflow_schema_migrations` | Additive migration marker |
| `workflow_entities` | Versioned projections for engagement, memberships, workflow records, blocking notes, tasks, notifications |
| `workflow_events` | Append-only actor/action/before-and-after history; update/delete triggers reject changes |
| `workflow_policies` | Immutable policy revisions; update/delete rejected |
| `workflow_sessions` | Hashed opaque tokens/CSRF, selected staff ID, assurance, expiry, revocation, credential epoch |
| `workflow_signoffs` | Immutable signed dependency manifest; only `valid → invalidated/revoked` permitted; never restored |
| `workflow_access_events` | Append-only access/reveal/denial metadata, purpose and outcome |
| `workflow_readiness_evaluations` | Append-only recorded readiness snapshots |

Migration verification used SQLite backup into a temporary database, ran every migration twice, and compared all original table rows. Existing counts remained: reviews 1, review_events 4, adjustment/evidence/reconciliation migration markers 1 each; all existing ledger/verification/reconciliation event tables remained empty. SQLite integrity was `ok`; foreign-key checks returned no errors. The existing working database was inspected read-only and left unchanged by Phase 4 verification. Normal configured startup/session initialization applies the migration additively when that database is used.

## Endpoints

All existing paths, parameters, IDs, and request bodies remain. Strict mode additionally requires a valid server session and matching identity, and masks sensitive content unless an authorized reveal is requested. Legacy unauthenticated behavior exists only in the isolated regression profile.

| Method | `/api/workflow` path | Purpose |
|---|---|---|
| GET | `/session` | Bootstrap/rotate session and return CSRF token, mode and assurance |
| POST | `/session` | Select demo identity / prove configured credential / end session |
| GET | `/session/staff` | Minimal packet identity choices for configured session provider |
| GET | `/overview` | Authorized engagement projections, policy, records, assignments, tasks, notifications, sign-offs |
| POST | `/engagement` | Confirm/transfer ownership to an assigned active packet partner |
| POST | `/assignments` | Activate/change/remove scoped assignment with revision check |
| POST | `/policies` | Administrator publishes immutable standards revision with rationale |
| POST | `/records` | Create/revise evidence-backed preparation, diligence, election, judgment, question, disposition or required-step record |
| POST | `/records/{id}/actions` | Submit, independently approve, or reopen record |
| POST | `/notes` | Create/respond/request resolution/independently resolve/reopen blocking note |
| GET | `/signoff-preview` | Current dependency digest for area and reviewer/partner level |
| POST | `/signoffs` | Record current independent workpaper approval with expected digest |
| POST | `/signoffs/{id}/revoke` | Permanently revoke an existing valid approval |
| POST | `/tasks` | Assign/update deadline or completion; acknowledge own notification |
| GET / POST | `/readiness` | Evaluate readiness / preserve append-only evaluation snapshot |
| GET | `/history` | Authorized workflow audit, optionally filtered by entity ID |
| GET | `/access-history` | Partner/administrator access-audit metadata |

`X-Sensitive-Access: reveal` plus `X-Access-Purpose` requests cleared access. Mutations require `X-CSRF-Token` and an allowed browser Origin. All strict data responses use `Cache-Control: no-store, private` and `Pragma: no-cache`; errors and session responses are also non-cacheable.

## Permission matrix

An active packet identity and assignment are required except for administrator metadata operations. Scope limits apply to writes; assignment alone does not grant clearance.

| Capability | Preparer | Reviewer | Partner | Firm administrator | Quality reviewer |
|---|---|---|---|---|---|
| Read assigned engagement evidence, masked | Yes | Yes | Yes | No | Read only when active and assigned |
| Prepare records / draft adjustments | In scope | In scope; becomes substantive author | In scope; becomes substantive author | No | No |
| Submit preparation / respond to notes | Yes | Yes | Yes | No | No |
| Resolve findings/notes, approve records | No | Independent only | Independent only | No | No |
| CPA source verification | No | Yes | Yes | No | No |
| Approve adjustments | No | Independent, below policy boundary | Independent, including material effects | No | No |
| Formal workpaper sign-off | No | Assigned reviewer, independent | Assigned partner, independent; distinct current reviewer required | No | No |
| Assign staff / ownership / tasks | Own task completion only | Own task completion only | Engagement management | Metadata management | No |
| Publish firm policy | No | No | No | Yes | No |
| Reveal sensitive data | Cleared only | Cleared only | Cleared only | No tax-data privilege | No |
| Access-audit metadata | No | No | Yes | Yes | No |

Initial packet assignments remain st-01 preparer, st-02 reviewer, st-03 partner/owner. st-04 is initially unassigned and lacks clearance; assigning it does not change clearance or role. st-05 is the administrator. st-06 remains inactive until its packet active date (2027-01-04).

## Firm standards and review records

- Policy revisions can tighten the partner threshold below the packet's $1,000 ceiling, configure prior-year variance amount/percentage, and restrict supported verification methods. Monetary approval effects use Decimal arithmetic and the original validated packet method; comparison occurs before rounding.
- Independence, mandatory blocking notes, and required review areas cannot be waived. Firm variance tolerances apply to prior-year comparisons, not invented blanket tax tolerances.
- Record revisions preserve all authors, authority/method, evidence references, applicability and conclusions. Unresolved references, unknown applicability and missing authority/evidence cannot be submitted as complete.
- Required checklist identities/labels cannot be repurposed. All substantive record authors are excluded from independently signing their own tax area. Records transition through draft/open, submitted, approved, and reopened. Editing approved work creates a new draft revision and invalidates affected sign-offs.
- Notes transition open → responded → resolution_requested → resolved; resolved notes may reopen. Every intermediate state blocks filing. The responder cannot close their own response; independent review is server-enforced.
- Deadlines and in-app notifications derive from packet facts or explicit assignments. No email, external notifications, or automatic filing actions are sent.

## Filing-readiness blocking rules

Readiness aggregates explicit resource lists rather than presenting a green label based on one subsystem. The real packet is blocked by any of:

1. Missing/inactive preparer, reviewer or partner assignment.
2. Incomplete required engagement steps or diligence assessments (CTC, ODC, AOTC, EIC, HOH), including unresolved applicability.
3. Unapproved elections, professional judgments or unresolved professional questions.
4. Any open/responded/resolution-requested/reopened blocking note.
5. Documents with requires-review, unused or unextracted dispositions lacking an independently approved evidence-backed disposition. Existing duplicate and superseded distinctions remain intact.
6. Unresolved unified findings and unsupported reconciliation calculations. Acknowledging unsupported work does not invent the missing computation.
7. Draft, submitted, rejected or stale adjustments; approvals insufficient under the active firm policy.
8. Low-confidence evidence (application review guard: extracted confidence below 0.90) without current confirmed verification, or stale/revoked/needs-review verification records. This is an evidence-quality guard, not a tax materiality threshold.
9. Missing current reviewer/partner sign-offs for required areas and the engagement.
10. **Unverified authoritative final return and actual return-bound client authorization.** Scripted timeline/signature events and demonstration approvals cannot clear this requirement. There is no API switch to force the real packet ready.

The pure readiness evaluator accepts synthetic complete facts only in tests. It is not exposed as an endpoint or fixture override for the real case.

## Sign-off invalidation examples

- Revise a business preparation statement: its reviewer and partner approvals invalidate in the same transaction. An unrelated payments approval remains valid unless it has an actual shared dependency.
- Create/revise/approve/reverse a business receipt adjustment through the original Phase 1 API: affected signed areas invalidate; engine values remain unchanged.
- Add a field verification or change a reconciliation decision/adjustment link: scopes that bind that evidence or finding invalidate.
- Tighten policy: all signatures containing the prior policy invalidate. Remove or change a scoped assignment: affected approvals invalidate.
- Revoke a reviewer approval: dependent partner/engagement approvals invalidate. Reverting the original data never restores an invalidated approval; a new sign-off ID is required.
- Concurrent sign-off and mutation: either the expected digest is rejected, or the earlier approval is invalidated by the mutation before commit. A transaction failure rolls back both the source change and invalidation.

## Sensitive-data protection and security limitations

Sensitive identifiers (SSNs, bank/routing/account identifiers, IP/ERO PINs, PTINs, EFINs and identified license/IBAN fields) are masked recursively, including packet snapshots, histories, extracted evidence, source text, snippets and source-match metadata. Known packet values and labeled free-text identifiers are covered. Identifier boundaries preserve opaque dependency digests, avoiding accidental PIN-substring masking of sign-off tokens. Matching a masked excerpt is not presented as field proof. Masking preserves string positions where possible; numeric sensitive fields become null.

Cleared reveals require engagement access and a meaningful purpose; an append-only access event commits before raw data delivery. The supported launcher disables URL access logging. Unhandled errors are generic, validation errors do not echo submitted bodies, and audit metadata excludes response payloads. Session changes and masking discard stale client responses; workspace remounts clear old source views and audit data.

Limits:

- Demo mode is local-only and forbidden in production. It provides **no authenticated identity assurance**. Selected staff IDs are demonstrations, not legal electronic signatures.
- Credential mode uses high-length provisioned secrets, server sessions, expiry, revocation, CSRF and production Secure cookies. It is not enterprise SSO, MFA, identity proofing or a certified signature system. Credential issuance/rotation, login throttling, operational monitoring and external penetration testing remain deployment responsibilities.
- Production rejects demo/legacy modes, short/missing credentials, and non-HTTPS allowed origins. The supported server binds loopback; a correctly configured HTTPS reverse proxy, secure host and restricted proxy logs are required for production use.
- SQLite contents/backups are not encrypted by this application. Database owners can bypass application controls/triggers; append-only means enforced through this application/database schema, not externally notarized or tamper-proof storage.
- Redaction is designed for the supplied structured packet and labeled text. New document formats and unexpected free-text sensitive-data patterns require classifier tests before ingestion. Original packet files must not be exposed by a separate static server.
- API no-store headers and client clearing reduce caching; an authorized person can still copy, photograph or inspect information already revealed. The application cannot recall copied data. Browser testing records no strict-mode traces, screenshots or video.
- Dependency tracking covers the immutable packet and supported database mutation paths. Future write paths must use the shared connection hook and extend dependency manifests for new resource kinds. Direct external SQL/file edits are outside the supported mutation contract; packet replacement requires process restart and review.
- The supplied engine cannot authoritatively regenerate a corrected return. Final return/real client authorization remain blocked prerequisites. This is deliberate Phase 4 scope, not a claim of filing readiness.

## Verification results

The following checks were run against the implemented Phase 4 workflow. No existing test assertions were weakened. The original suite consists of 260 pytest tests plus 14 Playwright tests (274 total).

- Pytest: **306 passing** (260 original + 46 strict/workflow tests).
- Original Playwright regression suite: **14 passing**.
- Strict Playwright suite: **6 passing**.
- TypeScript `tsc --noEmit`: passing.
- ESLint: passing.
- Production build: passing with `npm run build -- --webpack`, including builds used by both Playwright configurations. The default Turbopack build failed because its worker could not bind a port in the sandbox, including an escalated retry; webpack production builds succeeded with approved execution. No build checks were removed.
- SQLite original/copy integrity: `ok`; copy foreign-key checks empty; repeated additive migration preserved all original rows.
- One existing Starlette/httpx deprecation warning remains; no failing assertions in final runs.

Acceptance coverage includes all registered protected route methods without sessions; inactive/unknown identities; CSRF/Origin rejection; body identity forgery; revoked sessions and cross-tab switching; administrator metadata separation; scoped assignments; clearance; nested text/history/error redaction; no-store; access events; immutable policies/audit triggers; stale revisions and sign-off digests; simultaneous mutations; concurrent sign-off versus mutation; rollback atomicity; scoped permanent invalidation; original adjustment API integration; CPA evidence persistence; note resolution independence; task assignment/ownership; real-packet blockers and synthetic evaluator fixtures.

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

Both browser configurations use separate temporary databases and private ports. The legacy test profile is explicit and test-only; strict tests instantiate a separately configured application and do not inherit legacy authorization behavior.

## Complete demonstration workflow

### Start a persistent local demonstration

From `backend`:

```sh
WORKPAPER_ENV=development WORKPAPER_MODE=demo WORKPAPER_ORIGINS=http://localhost:3000 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_secure.py
```

From `frontend`, run `npm run dev`; the API URL must point to `http://localhost:8000`. The backend applies additive migrations to the configured review database. Set `REVIEW_DB_PATH` to a separate absolute path to keep demonstration data separate from existing records. Do not use `legacy_test` for this walkthrough.

1. Open the application. Confirm the demonstration warning and absence of tax data before session selection. Start st-01 Priya's preparer session.
2. Open **Readiness**. Confirm FILING BLOCKED and expand document, finding, unsupported calculation, diligence and sign-off resource lists. Record an assessment; actual authorization remains blocked.
3. Open **Diligence**. Create a `preparation` record in `business`, title “Business receipts source review,” describe the duplicated-receipts discrepancy, enter authority/method, and reference `D16` plus the exact receipts references inspected in the existing reconciliation dashboard. Do not assert a tax conclusion unsupported by those sources.
4. Open **Tax Workpaper → Reconciliation Dashboard**. Inspect `business.receipts`, compare independent expected/reported values, and navigate to the source evidence. Use the existing correction action to draft the linked Phase 1 adjustment; the actor is st-01 and cannot be changed in a local component selector.
5. Open **Tax Adjustments**, inspect the separate proposed value/effect and audit history, and submit. Switch the top-level session to st-02 Daniel. A material receipts adjustment cannot receive reviewer-only approval. Switch to st-03 Helen to approve independently. Confirm only approved, non-reversed adjustments contribute to the approved workpaper summary; engine values remain unchanged.
6. Switch to st-01. In **Diligence**, edit a required-step or diligence record; document applicability, answer, authority and valid source references. Save and submit. Switch to st-02 to approve. Inspect **History** to see both stable staff IDs and every revision/action. Use the same record flow for an election, tax judgment, document disposition or unresolved professional question.
7. As st-01, open **Notes** and create a business blocking note owned by st-01. Respond, then request resolution. Switch to st-02; independently resolve the note. Inspect its history. Filing remains blocked by all other outstanding prerequisites.
8. As st-02, open **Signoffs**, select `business`, and record a demonstration reviewer sign-off once scoped notes/records permit it. As st-03, add the partner sign-off. Confirm the demonstration/no-legal-signature labels.
9. Switch to st-01 and revise the business preparation record or revise/reverse the related adjustment using an authorized actor. Return to **Signoffs**: affected reviewer/partner sign-offs are invalidated. Reload to confirm persistence. Reverting text does not restore old approvals; a fresh review/sign-off is required.
10. Switch to st-05 Jo. In **Assignments**, assign st-04 Marcus to `business`. Confirm role and clearance cannot be promoted. Inspect/publish a tighter partner threshold or prior-year variance policy with rationale, optionally restrict verification methods, and inspect the immutable revision. Existing signatures bound to the previous policy invalidate. Confirm the administrator has no Tax Workpaper entry point and cannot fetch tax-evidence APIs directly.
11. Switch to st-04. Confirm assigned access works in masked form and **Security → Reveal sensitive information** is disabled. Attempting an out-of-scope write is rejected server-side.
12. Switch to st-03. In **Security**, enter a specific access purpose and reveal sensitive data. Inspect a source identity/PIN document in Tax Workpaper and then the sensitive access audit. Mask again: old source views/audit data clear immediately. Switch identity; reveal mode resets. Repeat with two tabs to observe the old tab lock when the other switches identity.
13. In **Tasks**, assign a packet deadline, optionally enter an explicit revised date, complete/reopen the task, and acknowledge the resulting notification as its recipient. Notifications stay in the application.
14. Return to **Readiness**, record another snapshot, and inspect remaining blockers. Completing a demonstration business review does not complete all tax areas, unsupported calculations, required approvals, the authoritative final return, or actual client authorization. The real engagement must still display FILING BLOCKED.
